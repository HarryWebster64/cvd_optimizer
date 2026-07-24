"""Main click entrypoint for the CVD Optimizer (groups: openfoam, warpx, xolotl)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from cvd.schemas import CVDParameters
from cvd.utils.foam_parser import write_terminal_fluid_state
from cvd.utils.hdf5_mapper import write_surface_bombardment_flux

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WARPX_TEMPLATE_DIR = _REPO_ROOT / "workflows" / "_shared" / "warpx"
_WARPX_TEMPLATE_NAME = "inputs.jinja2"
_XOLOTL_TEMPLATE_DIR = _REPO_ROOT / "workflows" / "_shared" / "xolotl"
_XOLOTL_TEMPLATE_NAME = "params.jinja2"


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


def _render_warpx_inputs(params: CVDParameters, fluid_state: dict) -> str:
    env = Environment(loader=FileSystemLoader(_WARPX_TEMPLATE_DIR))
    template = env.get_template(_WARPX_TEMPLATE_NAME)
    return template.render(params=params, fluid_state=fluid_state)


def _render_xolotl_params(params: CVDParameters, flux_path: Path) -> str:
    env = Environment(loader=FileSystemLoader(_XOLOTL_TEMPLATE_DIR))
    template = env.get_template(_XOLOTL_TEMPLATE_NAME)
    return template.render(params=params, flux_path=flux_path)


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
    """Validate params.yaml and render the OpenFOAM case."""
    _load_params(params_path)
    click.echo(f"[openfoam configure] validated {params_path}; would write case to {output_dir}")


@openfoam.command("run")
@click.option("--case", "case_dir", required=True, type=click.Path(path_type=Path), help="OpenFOAM case directory")
@click.option("--mock", is_flag=True, default=False, help="Skip the real reactingFoam/PyVista handshake and write placeholder outputs")
def openfoam_run(case_dir: Path, mock: bool) -> None:
    """Run reactingFoam on the configured case, then extract the terminal fluid state."""
    click.echo(f"[openfoam run] would execute reactingFoam in {case_dir}")

    # Stand in for reactingFoam's parallel-decomposition output directory
    # until a real solver run is wired up.
    processor_dir = case_dir / "processor0"
    processor_dir.mkdir(parents=True, exist_ok=True)
    (processor_dir / "MOCK_OUTPUT.txt").write_text("placeholder reactingFoam processor0 output\n")

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
@click.option("--mock", is_flag=True, default=False, help="Skip the real openPMD/HDF5 handshake and write placeholder outputs")
def warpx_run(case_dir: Path, mock: bool) -> None:
    """Run the WarpX PIC solver on the configured case, then tally the substrate arrival flux."""
    click.echo(f"[warpx run] would execute WarpX in {case_dir}")

    # Stand in for WarpX's openPMD diagnostics output directory until a
    # real PIC solver run is wired up.
    openpmd_dir = case_dir / "diags" / "openpmd"
    openpmd_dir.mkdir(parents=True, exist_ok=True)
    (openpmd_dir / "MOCK_OUTPUT.txt").write_text("placeholder WarpX openPMD diagnostics output\n")

    try:
        flux_path = write_surface_bombardment_flux(case_dir, mock=mock)
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
    click.echo(f"[xolotl run] would execute Xolotl in {case_dir}")

    if not mock:
        raise click.ClickException(
            "real Xolotl KMC solver integration is not implemented yet; pass --mock to write placeholder growth metrics"
        )

    case_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = _write_crystal_growth_metrics(case_dir)
    click.echo(f"[xolotl run] wrote crystal growth metrics to {metrics_path}")


if __name__ == "__main__":
    main()
