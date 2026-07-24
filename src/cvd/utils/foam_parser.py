"""Data-Handshake A: OpenFOAM -> WarpX.

WarpX needs to initialize its macro-particles over a realistic gas density
baseline, but it doesn't read OpenFOAM raw mesh files. This module opens the
final time directory of a reactingFoam case, averages the rho / mass-fraction
fields immediately above the substrate, and writes a clean
terminal_fluid_state.json. `cvd warpx configure` reads that JSON file to
scale the neutral gas densities in the WarpX input template.

Real OpenFOAM field files (binary or ASCII internalField dumps) aren't
parsed yet -- `_mock_read_substrate_field` stands in for that until a real
reader is written, so the rest of the pipeline can be exercised end-to-end.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Mock substrate-adjacent field averages, standing in for a real parse of
# OpenFOAM's internalField dumps until foam_parser reads actual case output.
_MOCK_SUBSTRATE_FIELDS = {
    "rho": 0.85,    # kg/m^3, averaged neutral gas density near the substrate
    "T": 1080.0,    # K, boundary-layer temperature near the substrate
    "CH4": 0.035,   # mass fraction of CH4 near the substrate
    "H2": 0.965,    # mass fraction of H2 near the substrate
}


def _is_time_dir_name(name: str) -> bool:
    try:
        float(name)
    except ValueError:
        return False
    return True


def _find_latest_time_directory(case_dir: Path) -> Path:
    """Return the numerically-latest OpenFOAM time directory in `case_dir`.

    Falls back to a synthetic "0" directory when the case hasn't actually
    been run yet (mock mode).
    """
    if case_dir.is_dir():
        time_dirs = [p for p in case_dir.iterdir() if p.is_dir() and _is_time_dir_name(p.name)]
        if time_dirs:
            return max(time_dirs, key=lambda p: float(p.name))
    return case_dir / "0"


def _mock_read_substrate_field(field_name: str) -> float:
    """Stand in for reading `<time_dir>/<field_name>` and averaging the
    cell layer immediately above the substrate boundary patch."""
    return _MOCK_SUBSTRATE_FIELDS.get(field_name, 0.0)


def extract_terminal_fluid_state(case_dir: str | Path) -> dict[str, Any]:
    """Average the substrate-adjacent fluid fields from the final OpenFOAM time step."""
    case_dir = Path(case_dir)
    time_dir = _find_latest_time_directory(case_dir)

    return {
        "source_case": str(case_dir),
        "time_directory": time_dir.name,
        "substrate_boundary_layer": {
            "rho": _mock_read_substrate_field("rho"),
            "temperature": _mock_read_substrate_field("T"),
            "mass_fractions": {
                "CH4": _mock_read_substrate_field("CH4"),
                "H2": _mock_read_substrate_field("H2"),
            },
        },
    }


def write_terminal_fluid_state(case_dir: str | Path, output_dir: str | Path | None = None) -> Path:
    """Write terminal_fluid_state.json for the given OpenFOAM case.

    `output_dir` defaults to `case_dir`, matching the dvc.yaml stage output
    `openfoam_case/terminal_fluid_state.json`.
    """
    case_dir = Path(case_dir)
    output_dir = Path(output_dir) if output_dir is not None else case_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fluid_state = extract_terminal_fluid_state(case_dir)

    output_path = output_dir / "terminal_fluid_state.json"
    with open(output_path, "w") as f:
        json.dump(fluid_state, f, indent=2)

    return output_path
