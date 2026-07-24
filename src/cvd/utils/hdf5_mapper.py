"""Data-Handshake B: WarpX -> Xolotl.

WarpX tracks continuous-time particle trajectories using high-performance
openPMD grid libraries. Xolotl expects a single boundary arrival-flux
vector to step its cluster-dynamics solver forward in time. This module
opens WarpX's openPMD HDF5 diagnostics, filters the species boundaries
hitting the bottom (substrate) wall layer, integrates the particle weights
over the steady-state time steps, and tallies the arrival flux into
surface_bombardment_flux.h5 for `cvd xolotl configure` to consume.

Real openPMD/HDF5 diagnostics parsing isn't wired up yet --
`_mock_bottom_wall_species_flux` stands in for that until a real
openPMD reader is written.
"""

from __future__ import annotations

from pathlib import Path

import h5py

# Mock steady-state arrival flux (particles / m^2 / s) tallied at the
# substrate-facing (bottom) wall boundary, standing in for a real
# integration of WarpX's openPMD particle weights until hdf5_mapper reads
# actual diagnostics.
_MOCK_BOTTOM_WALL_SPECIES_FLUX = {
    "CH3_radical": 2.4e21,
    "H_atomic": 6.1e21,
    "electron": 1.8e18,
}


def _mock_bottom_wall_species_flux() -> dict[str, float]:
    """Stand in for integrating WarpX openPMD particle weights hitting the
    bottom (substrate) wall over the steady-state time steps."""
    return dict(_MOCK_BOTTOM_WALL_SPECIES_FLUX)


def extract_surface_bombardment_flux(warpx_case_dir: str | Path) -> dict[str, float]:
    """Tally the substrate arrival flux from WarpX's openPMD diagnostics.

    A real implementation would glob `warpx_case_dir/diags/openpmd/*.h5`,
    open each file, and integrate the particle weights of species crossing
    the bottom wall boundary over the steady-state time steps.
    """
    warpx_case_dir = Path(warpx_case_dir)
    return _mock_bottom_wall_species_flux()


def write_surface_bombardment_flux(warpx_case_dir: str | Path, output_dir: str | Path | None = None) -> Path:
    """Write surface_bombardment_flux.h5 for the given WarpX case.

    `output_dir` defaults to `warpx_case_dir`, matching the dvc.yaml stage
    output `warpx_case/surface_bombardment_flux.h5`.
    """
    warpx_case_dir = Path(warpx_case_dir)
    output_dir = Path(output_dir) if output_dir is not None else warpx_case_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    flux = extract_surface_bombardment_flux(warpx_case_dir)

    output_path = output_dir / "surface_bombardment_flux.h5"
    with h5py.File(output_path, "w") as f:
        group = f.create_group("bottom_wall_flux")
        group.attrs["units"] = "particles / m^2 / s"
        for species, value in flux.items():
            group.attrs[species] = value

    return output_path
