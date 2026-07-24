"""Data-Handshake B: WarpX -> Xolotl.

WarpX tracks continuous-time particle trajectories using high-performance
openPMD grid libraries. Xolotl expects a single boundary arrival-flux
vector to step its cluster-dynamics solver forward in time. This module
opens WarpX's dedicated BoundaryScraping diagnostic output, sums the
physical particle weights of each species absorbed at the substrate
(bottom-wall, "zlo") boundary, and tallies the arrival flux into
surface_bombardment_flux.h5 for `cvd xolotl configure` to consume.

Requires real WarpX output: `<species>.save_particles_at_zlo = 1` per
species (workflows/_shared/warpx/inputs.jinja2) plus a second diagnostic
with `diag_type = BoundaryScraping`, which WarpX writes to
`<warpx_case_dir>/diags/<scraping_diag_name>/particles_at_zlo/*.h5`. Species
groups in that file are named directly (e.g. "electrons", "ions") -- the
"zlo" distinction is carried by the directory, not a name suffix. This was
determined empirically against a real WarpX 24.04 run (a `<species>_zlo`
suffix, guessed before that, does not exist); see git history for the
original guess this replaced.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

# WarpX's BoundaryScraping diagnostic writes each captured boundary's data
# to diags/<diag_name>/particles_at_<boundary>/ -- our inputs template names
# the diagnostic "boundary_scraping" and only enables the zlo (substrate)
# boundary per-species.
SCRAPING_DIAG_SUBDIR = Path("boundary_scraping") / "particles_at_zlo"

# Substrate area (m^2) and steady-state sampling window (s), used to
# normalize summed particle weights into a flux. Real usage should derive
# these from params.chamber (substrate footprint) and params.warpx.n_steps
# times the actual PIC timestep -- see cli.py's warpx_run, which computes
# and passes real values rather than relying on these placeholder defaults.
DEFAULT_SUBSTRATE_AREA_M2 = 0.0707  # ~30 cm diameter substrate, pi * r^2
DEFAULT_COLLECTION_WINDOW_S = 1.0e-9

# Mock steady-state arrival flux (particles / m^2 / s), used when mock=True
# (no real openPMD diagnostics available) so downstream stages can still run.
_MOCK_BOTTOM_WALL_SPECIES_FLUX = {
    "CH3_radical": 2.4e21,
    "H_atomic": 6.1e21,
    "electron": 1.8e18,
}


def _mock_bottom_wall_species_flux() -> dict[str, float]:
    return dict(_MOCK_BOTTOM_WALL_SPECIES_FLUX)


def _iter_openpmd_files(diags_dir: Path) -> list[Path]:
    """Return openPMD HDF5 diagnostic files in ascending iteration order."""
    return sorted(diags_dir.glob("*.h5"))


def _iteration_keys(h5file: h5py.File) -> list[str]:
    return list(h5file["data"].keys())


def _species_weight_sum(particles_group: h5py.Group, species_name: str) -> float:
    """Sum the physical particle weights recorded for a scraped species."""
    weighting = particles_group[species_name]["weighting"][:]
    return float(np.sum(weighting))


def extract_surface_bombardment_flux(
    warpx_case_dir: str | Path,
    substrate_area_m2: float = DEFAULT_SUBSTRATE_AREA_M2,
    collection_window_s: float = DEFAULT_COLLECTION_WINDOW_S,
    mock: bool = False,
) -> dict[str, float]:
    """Tally the substrate arrival flux from WarpX's BoundaryScraping diagnostic.

    Opens every openPMD HDF5 file under
    `warpx_case_dir/diags/boundary_scraping/particles_at_zlo/`, sums each
    species' physical particle weights across every file and iteration
    found, and normalizes by `substrate_area_m2 * collection_window_s` to
    produce a mean arrival flux in particles / m^2 / s.

    If `mock` is True, skips HDF5 parsing entirely and returns fixed
    placeholder values -- used until `cvd warpx run` invokes a real PIC solve.
    """
    warpx_case_dir = Path(warpx_case_dir)

    if mock:
        return _mock_bottom_wall_species_flux()

    diags_dir = warpx_case_dir / "diags" / SCRAPING_DIAG_SUBDIR
    openpmd_files = _iter_openpmd_files(diags_dir)

    if not openpmd_files:
        raise ValueError(f"no openPMD boundary-scraping files found in {diags_dir}")

    species_weight_totals: dict[str, float] = {}

    for path in openpmd_files:
        with h5py.File(path, "r") as f:
            for iteration in _iteration_keys(f):
                particles_group = f[f"/data/{iteration}/particles"]
                for species_name in particles_group.keys():
                    weight_sum = _species_weight_sum(particles_group, species_name)
                    species_weight_totals[species_name] = (
                        species_weight_totals.get(species_name, 0.0) + weight_sum
                    )

    normalization = substrate_area_m2 * collection_window_s
    return {species: total / normalization for species, total in species_weight_totals.items()}


def write_surface_bombardment_flux(
    warpx_case_dir: str | Path,
    output_dir: str | Path | None = None,
    substrate_area_m2: float = DEFAULT_SUBSTRATE_AREA_M2,
    collection_window_s: float = DEFAULT_COLLECTION_WINDOW_S,
    mock: bool = False,
) -> Path:
    """Write surface_bombardment_flux.h5 for the given WarpX case.

    `output_dir` defaults to `warpx_case_dir`, matching the dvc.yaml stage
    output `warpx_case/surface_bombardment_flux.h5`. See
    `extract_surface_bombardment_flux` for the `mock` flag.
    """
    warpx_case_dir = Path(warpx_case_dir)
    output_dir = Path(output_dir) if output_dir is not None else warpx_case_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    flux = extract_surface_bombardment_flux(
        warpx_case_dir,
        substrate_area_m2=substrate_area_m2,
        collection_window_s=collection_window_s,
        mock=mock,
    )

    output_path = output_dir / "surface_bombardment_flux.h5"
    with h5py.File(output_path, "w") as f:
        group = f.create_group("bottom_wall_flux")
        group.attrs["units"] = "particles / m^2 / s"
        for species, value in flux.items():
            group.attrs[species] = value

    return output_path
