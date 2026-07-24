"""Data-Handshake A: OpenFOAM -> WarpX.

WarpX needs to initialize its macro-particles over a realistic gas density
baseline, but it doesn't read OpenFOAM raw mesh files. This module opens the
final time directory of a reactingFoam case with PyVista's OpenFOAMReader,
isolates the mesh cells immediately above the substrate boundary patch, and
averages the rho / mass-fraction fields there to produce a clean
terminal_fluid_state.json. `cvd warpx configure` reads that JSON file to
scale the neutral gas densities in the WarpX input template.

Requires a real OpenFOAM case: a `<case_dir>/case.foam` marker file (the
standard ParaView/VTK convention for pointing a reader at an OpenFOAM case
directory) plus at least one written time directory. `cvd openfoam run`
does not yet actually invoke reactingFoam, so this logic isn't exercised
against real solver output until that lands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pyvista as pv

# OpenFOAM boundary patch name for the substrate, as defined in the
# blockMeshDict template under workflows/_shared/openfoam/.
SUBSTRATE_PATCH_NAME = "substrate"

# Default thickness of the "immediately above the substrate" cell slab, in
# meters. Real usage should pass params.openfoam.mesh.cell_target (converted
# to meters) instead of relying on this default.
DEFAULT_SLAB_THICKNESS_M = 0.002

# Species mass-fraction fields to average over the substrate-adjacent slab.
SPECIES_FIELDS = ("CH4", "H2")

# Mock substrate-adjacent field averages, used when mock=True (no real
# OpenFOAM case/mesh available) so downstream stages can still run.
_MOCK_SUBSTRATE_FIELDS = {
    "rho": 0.85,   # kg/m^3
    "T": 1080.0,   # K
    "CH4": 0.035,  # mass fraction
    "H2": 0.965,   # mass fraction
}


def _mock_terminal_fluid_state(case_dir: Path) -> dict[str, Any]:
    return {
        "source_case": str(case_dir),
        "time_directory": "0",
        "substrate_boundary_layer": {
            "rho": _MOCK_SUBSTRATE_FIELDS["rho"],
            "temperature": _MOCK_SUBSTRATE_FIELDS["T"],
            "mass_fractions": {
                "CH4": _MOCK_SUBSTRATE_FIELDS["CH4"],
                "H2": _MOCK_SUBSTRATE_FIELDS["H2"],
            },
        },
    }


def _open_case(case_dir: Path) -> pv.OpenFOAMReader:
    """Point PyVista's OpenFOAMReader at `<case_dir>/case.foam` and seek to
    the final available time step, with all cell and patch data enabled."""
    foam_file = case_dir / "case.foam"
    reader = pv.OpenFOAMReader(str(foam_file))
    reader.enable_all_cell_arrays()
    reader.enable_all_patch_arrays()
    reader.set_active_time_value(reader.time_values[-1])
    return reader


def _find_normal_axis(bounds: tuple[float, ...]) -> int:
    """Return which axis (0=x, 1=y, 2=z) the patch surface lies flat
    against, i.e. the axis with the smallest bounding-box extent."""
    extents = (bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
    return min(range(3), key=lambda i: extents[i])


def _substrate_adjacent_slab_bounds(
    patch_bounds: tuple[float, ...],
    internal_bounds: tuple[float, ...],
    slab_thickness_m: float,
) -> tuple[float, ...]:
    """Build a thin bounding box spanning the substrate patch's footprint,
    extended one slab-thickness into the gas volume above it.

    The direction to extend is inferred by comparing the patch's position
    along its normal axis to the internal mesh's midpoint on that axis --
    this is a bounding-box comparison, not per-cell adjacency math.
    """
    bounds = list(patch_bounds)
    axis = _find_normal_axis(patch_bounds)
    lo, hi = axis * 2, axis * 2 + 1

    patch_pos = (bounds[lo] + bounds[hi]) / 2.0
    domain_mid = (internal_bounds[lo] + internal_bounds[hi]) / 2.0

    if patch_pos <= domain_mid:
        # Substrate sits at the low end of the domain along this axis;
        # the gas volume is above it, so grow the slab upward.
        bounds[hi] = bounds[lo] + slab_thickness_m
    else:
        # Substrate sits at the high end; the gas volume is below it.
        bounds[lo] = bounds[hi] - slab_thickness_m

    return tuple(bounds)


def extract_terminal_fluid_state(
    case_dir: str | Path,
    slab_thickness_m: float = DEFAULT_SLAB_THICKNESS_M,
    mock: bool = False,
) -> dict[str, Any]:
    """Average the substrate-adjacent fluid fields from the final OpenFOAM time step.

    Loads the case with PyVista's OpenFOAMReader, isolates the substrate
    boundary patch, clips a thin slab of internal-mesh cells immediately
    above it via `UnstructuredGrid.clip_box` (PyVista's built-in
    mesh-filtering -- no manual face/cell adjacency math), and averages
    `rho`, `T`, and the species mass-fraction fields over that slab.

    If `mock` is True, skips PyVista/OpenFOAM entirely and returns fixed
    placeholder values -- used until `cvd openfoam run` invokes a real
    reactingFoam solve.
    """
    case_dir = Path(case_dir)

    if mock:
        return _mock_terminal_fluid_state(case_dir)

    reader = _open_case(case_dir)
    blocks = reader.read()

    internal_mesh = blocks["internalMesh"]
    boundary = blocks["boundary"]
    substrate_patch = boundary[SUBSTRATE_PATCH_NAME]

    slab_bounds = _substrate_adjacent_slab_bounds(
        substrate_patch.bounds, internal_mesh.bounds, slab_thickness_m
    )
    substrate_slab = internal_mesh.clip_box(slab_bounds, invert=False)

    rho_avg = float(np.mean(substrate_slab.cell_data["rho"]))
    temperature_avg = float(np.mean(substrate_slab.cell_data["T"]))
    mass_fractions = {
        species: float(np.mean(substrate_slab.cell_data[species])) for species in SPECIES_FIELDS
    }

    return {
        "source_case": str(case_dir),
        "time_directory": float(reader.active_time_value),
        "substrate_boundary_layer": {
            "rho": rho_avg,
            "temperature": temperature_avg,
            "mass_fractions": mass_fractions,
        },
    }


def write_terminal_fluid_state(
    case_dir: str | Path,
    output_dir: str | Path | None = None,
    slab_thickness_m: float = DEFAULT_SLAB_THICKNESS_M,
    mock: bool = False,
) -> Path:
    """Write terminal_fluid_state.json for the given OpenFOAM case.

    `output_dir` defaults to `case_dir`, matching the dvc.yaml stage output
    `openfoam_case/terminal_fluid_state.json`. See `extract_terminal_fluid_state`
    for the `mock` flag.
    """
    case_dir = Path(case_dir)
    output_dir = Path(output_dir) if output_dir is not None else case_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fluid_state = extract_terminal_fluid_state(case_dir, slab_thickness_m=slab_thickness_m, mock=mock)

    output_path = output_dir / "terminal_fluid_state.json"
    with open(output_path, "w") as f:
        json.dump(fluid_state, f, indent=2)

    return output_path
