"""Main click entrypoint for the CVD Optimizer (groups: openfoam, warpx, xolotl)."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path

import click
import h5py
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from cvd.schemas import CVDParameters
from cvd.utils.foam_parser import write_terminal_fluid_state
from cvd.utils.hdf5_mapper import write_surface_bombardment_flux
from cvd.utils.xolotl_parser import write_crystal_growth_metrics

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OPENFOAM_TEMPLATE_DIR = _REPO_ROOT / "workflows" / "_shared" / "openfoam"
_WARPX_TEMPLATE_DIR = _REPO_ROOT / "workflows" / "_shared" / "warpx"
_WARPX_TEMPLATE_NAME = "inputs.jinja2"
_XOLOTL_TEMPLATE_DIR = _REPO_ROOT / "workflows" / "_shared" / "xolotl"
_XOLOTL_TEMPLATE_NAME = "params.jinja2"

# Coarse axisymmetric-wedge mesh settings (see blockMeshDict.jinja2).
_OPENFOAM_WEDGE_HALF_ANGLE_DEG = 2.5
_OPENFOAM_N_R = 6
_OPENFOAM_N_Z = 10

# Coarse PIC grid + pre-ionized plasma initialization (see inputs.jinja2).
# amr.n_cell is hardcoded small for a smoke test rather than using
# params.warpx.scoring_mesh directly (128x128x64 = 1M+ cells, impractical
# to validate against); wiring up real resolution is a follow-up, same as
# openfoam.mesh.cell_target above.
_WARPX_N_CELL = (8, 8, 8)
_WARPX_CFL = 1.0
_WARPX_PARTICLES_PER_CELL = 2
_WARPX_IONIZATION_FRACTION = 1e-4
_WARPX_ELECTRON_MASS_KG = 9.1093837015e-31
_WARPX_CARBON_ION_MASS_KG = 12.011 * 1.66053906660e-27  # representative C+ ion
_WARPX_MOLAR_MASS_KG_PER_MOL = {"CH4": 0.01604, "H2": 0.002016}
_BOLTZMANN_J_PER_K = 1.380649e-23
_AVOGADRO_PER_MOL = 6.02214076e23
_SPEED_OF_LIGHT_M_S = 2.99792458e8


def _load_params(params_path: Path) -> CVDParameters:
    try:
        return CVDParameters.from_yaml(params_path)
    except FileNotFoundError as exc:
        raise click.ClickException(f"parameter file not found: {params_path}") from exc
    except ValidationError as exc:
        raise click.ClickException(f"invalid parameters in {params_path}:\n{exc}") from exc


def _load_fluid_state(fluid_state_path: Path) -> dict:
    if not fluid_state_path.exists():
        raise click.ClickException(f"fluid state file not found: {fluid_state_path}")
    with open(fluid_state_path) as f:
        return json.load(f)


def _openfoam_wedge_vertices(
    radius_m: float, height_m: float, half_angle_deg: float
) -> list[tuple[float, float, float]]:
    """Build the 8 vertices of a thin axisymmetric wedge hex block representing
    a full cylinder -- OpenFOAM's standard technique for meshing cylindrical
    geometry without an O-grid. Two vertex pairs sit on the z-axis (r=0),
    collapsing the hex into a pie-slice; the two flat faces get the `wedge`
    boundary type.
    """
    half_angle_rad = math.radians(half_angle_deg)
    x = radius_m * math.cos(half_angle_rad)
    y_neg = -radius_m * math.sin(half_angle_rad)
    y_pos = radius_m * math.sin(half_angle_rad)

    return [
        (0.0, 0.0, 0.0),
        (x, y_neg, 0.0),
        (x, y_pos, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, height_m),
        (x, y_neg, height_m),
        (x, y_pos, height_m),
        (0.0, 0.0, height_m),
    ]


def _openfoam_render_context(params: CVDParameters) -> dict:
    radius_m = params.chamber.diameter.to("meter").magnitude / 2
    height_m = params.chamber.height.to("meter").magnitude

    return {
        "params": params,
        "vertices": _openfoam_wedge_vertices(radius_m, height_m, _OPENFOAM_WEDGE_HALF_ANGLE_DEG),
        "wedge_half_angle_deg": _OPENFOAM_WEDGE_HALF_ANGLE_DEG,
        "n_r": _OPENFOAM_N_R,
        "n_z": _OPENFOAM_N_Z,
        "n_procs": params.openfoam.n_procs,
        "chamber_pressure_pa": params.feedstock_gas.pressure.to("pascal").magnitude,
        "inlet_velocity_mps": params.feedstock_gas.inlet_velocity.to("meter/second").magnitude,
        "inlet_temperature_k": 300.0,
        "substrate_temperature_k": params.chamber.substrate_temperature.to("kelvin").magnitude,
        "mass_fractions": params.feedstock_gas.mass_fractions,
        "initial_delta_t": 1e-7,
        "max_delta_t": 1e-3,
        "end_time": 1e-3,
        "write_interval": 5e-4,
    }


def _render_openfoam_case(params: CVDParameters, output_dir: Path) -> list[Path]:
    """Render every *.jinja2 file under workflows/_shared/openfoam/ into
    output_dir, preserving the system/ constant/ 0/ directory structure."""
    env = Environment(loader=FileSystemLoader(_OPENFOAM_TEMPLATE_DIR))
    context = _openfoam_render_context(params)

    written_paths = []
    for template_path in sorted(_OPENFOAM_TEMPLATE_DIR.rglob("*.jinja2")):
        relative_path = template_path.relative_to(_OPENFOAM_TEMPLATE_DIR)
        template = env.get_template(relative_path.as_posix())
        rendered = template.render(**context)

        target_path = output_dir / relative_path.with_suffix("")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(rendered)
        written_paths.append(target_path)

    return written_paths


def _warpx_render_context(params: CVDParameters, fluid_state: dict) -> dict:
    """Build the WarpX inputs-deck context, including a coarse pre-ionized
    plasma initialization derived from the Data-Handshake A fluid state.

    Physics simplification: rather than self-consistently driving
    ionization from an oscillating microwave antenna, this initializes an
    already-ionized quasi-neutral plasma (electrons + a representative C+
    ion) at a density derived from the neutral gas density times an
    assumed weak-ionization fraction, and lets space-charge dynamics plus
    a thermal spread carry particles to the absorbing boundaries.
    """
    boundary_layer = fluid_state["substrate_boundary_layer"]
    rho_kg_m3 = boundary_layer["rho"]
    temperature_k = boundary_layer["temperature"]
    mass_fractions = boundary_layer["mass_fractions"]

    mean_molar_mass_kg_per_mol = sum(
        mass_fractions.get(species, 0.0) * molar_mass
        for species, molar_mass in _WARPX_MOLAR_MASS_KG_PER_MOL.items()
    )
    neutral_number_density_per_m3 = rho_kg_m3 / mean_molar_mass_kg_per_mol * _AVOGADRO_PER_MOL
    plasma_density_per_m3 = neutral_number_density_per_m3 * _WARPX_IONIZATION_FRACTION

    def thermal_beta(mass_kg: float) -> float:
        v_thermal_m_s = math.sqrt(_BOLTZMANN_J_PER_K * temperature_k / mass_kg)
        return v_thermal_m_s / _SPEED_OF_LIGHT_M_S

    diag_intervals = max(1, params.warpx.n_steps // 10)

    return {
        "params": params,
        "n_cell_x": _WARPX_N_CELL[0],
        "n_cell_y": _WARPX_N_CELL[1],
        "n_cell_z": _WARPX_N_CELL[2],
        "particles_per_cell": _WARPX_PARTICLES_PER_CELL,
        "plasma_density_per_m3": plasma_density_per_m3,
        "ion_mass_kg": _WARPX_CARBON_ION_MASS_KG,
        "electron_thermal_beta": thermal_beta(_WARPX_ELECTRON_MASS_KG),
        "ion_thermal_beta": thermal_beta(_WARPX_CARBON_ION_MASS_KG),
        "diag_intervals": diag_intervals,
    }


def _render_warpx_inputs(params: CVDParameters, fluid_state: dict) -> str:
    env = Environment(loader=FileSystemLoader(_WARPX_TEMPLATE_DIR))
    template = env.get_template(_WARPX_TEMPLATE_NAME)
    return template.render(**_warpx_render_context(params, fluid_state))


def _warpx_flux_normalization(params: CVDParameters) -> tuple[float, float]:
    """Compute the real substrate area and total simulated duration for
    Data-Handshake B's flux normalization, matching the grid/CFL settings
    `_warpx_render_context` puts in the rendered inputs deck.

    WarpX's Yee-solver timestep isn't a free parameter -- it's set by the
    CFL condition from the cell size, so it's derived here with the same
    formula WarpX itself uses, rather than guessed at.
    """
    radius_m = params.chamber.diameter.to("meter").magnitude / 2
    height_m = params.chamber.height.to("meter").magnitude
    substrate_area_m2 = math.pi * radius_m**2

    dx = params.chamber.diameter.to("meter").magnitude / _WARPX_N_CELL[0]
    dy = params.chamber.diameter.to("meter").magnitude / _WARPX_N_CELL[1]
    dz = height_m / _WARPX_N_CELL[2]
    dt_s = _WARPX_CFL / (
        _SPEED_OF_LIGHT_M_S * math.sqrt(1 / dx**2 + 1 / dy**2 + 1 / dz**2)
    )
    collection_window_s = params.warpx.n_steps * dt_s

    return substrate_area_m2, collection_window_s


def _load_warpx_flux(flux_path: Path) -> dict[str, float]:
    """Read the per-species substrate arrival flux written by
    `cvd warpx run` (Data-Handshake B, src/cvd/utils/hdf5_mapper.py)."""
    with h5py.File(flux_path, "r") as f:
        return dict(f["bottom_wall_flux"].attrs)


# 1 m^2 = (1e9 nm)^2 -- Xolotl's flux option is documented in #/nm^2/s
# (ConfOptions.cpp), not SI #/m^2/s.
_SQUARE_METERS_PER_SQUARE_NM = 1e-18


def _render_xolotl_params(params: CVDParameters, flux_path: Path) -> str:
    flux_by_species = _load_warpx_flux(flux_path)
    # Xolotl's `flux` is a single scalar driving cluster nucleation, not a
    # per-species map. Ions are what actually deposit into the growing
    # lattice (electrons don't), so that's the value that maps onto it.
    ion_flux_per_m2_per_s = flux_by_species.get("ions", 0.0)
    ion_flux_per_nm2_per_s = ion_flux_per_m2_per_s * _SQUARE_METERS_PER_SQUARE_NM

    env = Environment(loader=FileSystemLoader(_XOLOTL_TEMPLATE_DIR))
    template = env.get_template(_XOLOTL_TEMPLATE_NAME)
    return template.render(
        params=params,
        ion_flux_per_nm2_per_s=ion_flux_per_nm2_per_s,
        substrate_temperature_k=params.chamber.substrate_temperature.to("kelvin").magnitude,
        runtime_s=params.xolotl.runtime.to("second").magnitude,
    )


def _run_solver(cmd: list[str], cwd: Path, solver_name: str) -> None:
    """Run a solver executable with its stdout/stderr streamed live to the
    terminal (subprocess.run inherits the parent's file descriptors by
    default), raising a clean ClickException if it fails to start or exits
    non-zero."""
    click.echo(f"[{solver_name}] running: {' '.join(cmd)} (cwd={cwd})")
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise click.ClickException(f"{solver_name} executable not found: {cmd[0]!r}") from exc
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(f"{solver_name} crashed (exit code {exc.returncode})") from exc


# Mock crystal growth trajectory, standing in for real Xolotl cluster-dynamics
# output until a real KMC solver is wired up.
_MOCK_CRYSTAL_GROWTH_METRICS = [
    {"time": 0, "thickness": 0.0, "defect_density": 1.0e15},
    {"time": 10800, "thickness": 4.2, "defect_density": 8.5e14},
    {"time": 21600, "thickness": 8.6, "defect_density": 6.1e14},
    {"time": 32400, "thickness": 13.1, "defect_density": 4.7e14},
    {"time": 43200, "thickness": 17.9, "defect_density": 3.9e14},
]


def _write_crystal_growth_metrics(case_dir: Path) -> Path:
    output_path = case_dir / "crystal_growth_metrics.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "thickness", "defect_density"])
        writer.writeheader()
        writer.writerows(_MOCK_CRYSTAL_GROWTH_METRICS)
    return output_path


@click.group()
@click.version_option()
def main() -> None:
    """CVD Optimizer: closed-loop OpenFOAM -> WarpX -> Xolotl epitaxial growth pipeline."""


# ---------------------------------------------------------------------------
# openfoam: chamber fluid & heat flux
# ---------------------------------------------------------------------------


@main.group()
def openfoam() -> None:
    """Macro-scale chamber fluid & heat flux (reactingFoam)."""


@openfoam.command("configure")
@click.option("--params", "params_path", required=True, type=click.Path(path_type=Path), help="Path to params.yaml")
@click.option("--output-dir", "output_dir", required=True, type=click.Path(path_type=Path), help="Directory to write the OpenFOAM case into")
def openfoam_configure(params_path: Path, output_dir: Path) -> None:
    """Validate params.yaml and render the OpenFOAM case (blockMeshDict,
    controlDict, fvSchemes/fvSolution, thermophysicalProperties, 0/ fields, etc.)."""
    params = _load_params(params_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths = _render_openfoam_case(params, output_dir)

    click.echo(f"[openfoam configure] validated {params_path}")
    click.echo(f"[openfoam configure] wrote {len(written_paths)} OpenFOAM case files to {output_dir}")


@openfoam.command("run")
@click.option("--case", "case_dir", required=True, type=click.Path(path_type=Path), help="OpenFOAM case directory")
@click.option("--params", "params_path", required=True, type=click.Path(path_type=Path), help="Path to params.yaml (used for openfoam.n_procs when not mocking)")
@click.option("--mock", is_flag=True, default=False, help="Skip the real blockMesh/reactingFoam solve and PyVista handshake, and write placeholder outputs")
def openfoam_run(case_dir: Path, params_path: Path, mock: bool) -> None:
    """Run blockMesh + reactingFoam (parallel via decomposePar/mpirun when n_procs > 1) on the configured case, then extract the terminal fluid state."""
    if mock:
        click.echo(f"[openfoam run] --mock: skipping blockMesh/reactingFoam in {case_dir}")
        # Stand in for reactingFoam's parallel-decomposition output directory
        # until a real (parallel) solver run is wired up.
        processor_dir = case_dir / "processor0"
        processor_dir.mkdir(parents=True, exist_ok=True)
        (processor_dir / "MOCK_OUTPUT.txt").write_text("placeholder reactingFoam processor0 output\n")
    else:
        params = _load_params(params_path)
        n_procs = params.openfoam.n_procs

        _run_solver(["blockMesh"], cwd=case_dir, solver_name="blockMesh")

        if n_procs > 1:
            # decomposePar creates the processorN/ subdirectories dvc.yaml
            # declares as this stage's output -- no separate mock stand-in
            # needed for a real parallel run.
            _run_solver(["decomposePar"], cwd=case_dir, solver_name="decomposePar")
            _run_solver(
                # --allow-run-as-root: our Docker image has no non-root
                # USER, and OpenMPI refuses to launch as root by default.
                ["mpirun", "--allow-run-as-root", "-np", str(n_procs), "reactingFoam", "-parallel"],
                cwd=case_dir,
                solver_name="reactingFoam",
            )
            # PyVista's OpenFOAMReader reads a single reconstructed case, not
            # per-processor decomposed output.
            _run_solver(["reconstructPar"], cwd=case_dir, solver_name="reconstructPar")
        else:
            _run_solver(["reactingFoam"], cwd=case_dir, solver_name="reactingFoam")

        # ParaView/PyVista convention: an empty marker file naming the case
        # for OpenFOAMReader to pick up.
        (case_dir / "case.foam").touch()

    try:
        fluid_state_path = write_terminal_fluid_state(case_dir, mock=mock)
    except FileNotFoundError as exc:
        raise click.ClickException(f"{exc}; pass --mock to write placeholder fluid state") from exc
    click.echo(f"[openfoam run] wrote terminal fluid state to {fluid_state_path}")


# ---------------------------------------------------------------------------
# warpx: microwave plasma ionization
# ---------------------------------------------------------------------------


@main.group()
def warpx() -> None:
    """Microwave plasma ionization rates via Particle-in-Cell (WarpX)."""


@warpx.command("configure")
@click.option("--params", "params_path", required=True, type=click.Path(path_type=Path), help="Path to params.yaml")
@click.option("--fluid-state", "fluid_state_path", required=True, type=click.Path(path_type=Path), help="terminal_fluid_state.json produced by openfoam run")
@click.option("--output-dir", "output_dir", required=True, type=click.Path(path_type=Path), help="Directory to write the WarpX case into")
def warpx_configure(params_path: Path, fluid_state_path: Path, output_dir: Path) -> None:
    """Validate params.yaml, ingest the OpenFOAM fluid state, and render the WarpX input deck."""
    params = _load_params(params_path)
    fluid_state = _load_fluid_state(fluid_state_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_path = output_dir / "inputs"
    inputs_path.write_text(_render_warpx_inputs(params, fluid_state))

    click.echo(f"[warpx configure] validated {params_path}; folded in {fluid_state_path}")
    click.echo(f"[warpx configure] wrote WarpX input deck to {inputs_path}")


@warpx.command("run")
@click.option("--case", "case_dir", required=True, type=click.Path(path_type=Path), help="WarpX case directory")
@click.option("--params", "params_path", required=True, type=click.Path(path_type=Path), help="Path to params.yaml (used to derive substrate area and collection window when not mocking)")
@click.option("--mock", is_flag=True, default=False, help="Skip the real WarpX solve and openPMD/HDF5 handshake, and write placeholder outputs")
def warpx_run(case_dir: Path, params_path: Path, mock: bool) -> None:
    """Run the WarpX PIC solver on the configured case, then tally the substrate arrival flux."""
    if mock:
        click.echo(f"[warpx run] --mock: skipping WarpX in {case_dir}")
        # Stand in for WarpX's openPMD diagnostics output directory until a
        # real PIC solver run is wired up.
        openpmd_dir = case_dir / "diags" / "openpmd"
        openpmd_dir.mkdir(parents=True, exist_ok=True)
        (openpmd_dir / "MOCK_OUTPUT.txt").write_text("placeholder WarpX openPMD diagnostics output\n")
        flux_kwargs = {}
    else:
        _run_solver(["warpx", "inputs"], cwd=case_dir, solver_name="warpx")
        params = _load_params(params_path)
        substrate_area_m2, collection_window_s = _warpx_flux_normalization(params)
        flux_kwargs = {
            "substrate_area_m2": substrate_area_m2,
            "collection_window_s": collection_window_s,
        }

    try:
        flux_path = write_surface_bombardment_flux(case_dir, mock=mock, **flux_kwargs)
    except ValueError as exc:
        raise click.ClickException(f"{exc}; pass --mock to write placeholder flux data") from exc
    click.echo(f"[warpx run] wrote surface bombardment flux to {flux_path}")


# ---------------------------------------------------------------------------
# xolotl: surface atomic crystal growth
# ---------------------------------------------------------------------------


@main.group()
def xolotl() -> None:
    """Atom-by-atom surface crystal growth (Xolotl / KMC solver)."""


@xolotl.command("configure")
@click.option("--params", "params_path", required=True, type=click.Path(path_type=Path), help="Path to params.yaml")
@click.option("--flux-file", "flux_path", required=True, type=click.Path(path_type=Path), help="surface_bombardment_flux.h5 produced by warpx run")
@click.option("--output-dir", "output_dir", required=True, type=click.Path(path_type=Path), help="Directory to write the Xolotl case into")
def xolotl_configure(params_path: Path, flux_path: Path, output_dir: Path) -> None:
    """Validate params.yaml, verify the WarpX flux file, and render the Xolotl parameter deck."""
    params = _load_params(params_path)

    if not flux_path.exists():
        raise click.ClickException(f"flux file not found: {flux_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    params_txt_path = output_dir / "params.txt"
    params_txt_path.write_text(_render_xolotl_params(params, flux_path))

    click.echo(f"[xolotl configure] validated {params_path}; verified {flux_path}")
    click.echo(f"[xolotl configure] wrote Xolotl parameter deck to {params_txt_path}")


@xolotl.command("run")
@click.option("--case", "case_dir", required=True, type=click.Path(path_type=Path), help="Xolotl case directory")
@click.option("--mock", is_flag=True, default=False, help="Write placeholder growth metrics instead of running the real Xolotl KMC solver")
def xolotl_run(case_dir: Path, mock: bool) -> None:
    """Run the Xolotl cluster-dynamics/KMC solver on the configured case, then write growth metrics."""
    if mock:
        click.echo(f"[xolotl run] --mock: skipping Xolotl in {case_dir}")
        case_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = _write_crystal_growth_metrics(case_dir)
        click.echo(f"[xolotl run] wrote crystal growth metrics to {metrics_path}")
        return

    _run_solver(["xolotl", "params.txt"], cwd=case_dir, solver_name="xolotl")

    try:
        metrics_path = write_crystal_growth_metrics(case_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(f"{exc}; pass --mock to write placeholder growth metrics") from exc
    click.echo(f"[xolotl run] wrote crystal growth metrics to {metrics_path}")


if __name__ == "__main__":
    main()
