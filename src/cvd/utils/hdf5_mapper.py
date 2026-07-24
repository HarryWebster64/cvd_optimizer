"""Data-Handshake B: WarpX -> Xolotl.

WarpX tracks continuous-time particle trajectories using high-performance
openPMD grid libraries. Xolotl expects a single boundary arrival-flux
vector to step its cluster-dynamics solver forward in time. This module
opens WarpX's openPMD HDF5 diagnostics, sums the physical particle weights
of each species scraped at the substrate (bottom-wall) boundary, integrates
that count over the steady-state iterations, and tallies the arrival flux
into surface_bombardment_flux.h5 for `cvd xolotl configure` to consume.

Requires real WarpX openPMD output: one HDF5 file per iteration under
`<warpx_case_dir>/diags/openpmd/`, with each species that WarpX absorbs at
the lower-z domain boundary written to a companion `<species>_zlo` particle
group (WarpX's boundary-scraping diagnostic, enabled per-species via
`<species>.save_particles_at_zlo = 1`). `cvd warpx run` does not yet
actually invoke WarpX, so this logic isn't exercised against real solver
output until that lands.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

# WarpX writes particles absorbed at the lower-z domain boundary (the
# substrate) into a dedicated per-species scraping buffer, named by
# appending this suffix to the source species (e.g. "electrons_zlo").
SUBSTRATE_SCRAPING_SUFFIX = "_zlo"

# Iterations before this index are treated as transient ramp-up and skipped
# when integrating the steady-state arrival flux.
STEADY_STATE_WARMUP_ITERATIONS = 2

# Substrate area (m^2) and steady-state sampling window (s) used to
# normalize summed particle weights into a flux. Real usage should derive
# these from params.chamber (substrate footprint) and
# params.warpx.n_steps / the PIC timestep instead of relying on these
# placeholders.
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


def _iteration_key(h5file: h5py.File) -> str:
    """WarpX writes one iteration per file in per-timestep mode -- there's
    exactly one group under /data/."""
    (iteration,) = h5file["data"].keys()
    return iteration


def _substrate_scraped_species(species_names: list[str]) -> list[str]:
    return [name for name in species_names if name.endswith(SUBSTRATE_SCRAPING_SUFFIX)]


def _scraped_weight_sum(particles_group: h5py.Group, scraped_species_name: str) -> float:
    """Sum the physical particle weights recorded in a substrate-scraping buffer."""
    weighting = particles_group[scraped_species_name]["weighting"][:]
    return float(np.sum(weighting))


def extract_surface_bombardment_flux(
    warpx_case_dir: str | Path,
    substrate_area_m2: float = DEFAULT_SUBSTRATE_AREA_M2,
    collection_window_s: float = DEFAULT_COLLECTION_WINDOW_S,
    mock: bool = False,
) -> dict[str, float]:
    """Tally the substrate arrival flux from WarpX's openPMD diagnostics.

    Opens each per-iteration openPMD HDF5 file under
    `warpx_case_dir/diags/openpmd/`, sums the physical particle weights in
    each species' `_zlo` boundary-scraping buffer, integrates that count
    over the steady-state iterations (skipping an initial warm-up window),
    and normalizes by `substrate_area_m2 * collection_window_s` to produce
    a mean arrival flux in particles / m^2 / s.

    If `mock` is True, skips HDF5 parsing entirely and returns fixed
    placeholder values -- used until `cvd warpx run` invokes a real PIC solve.
    """
    warpx_case_dir = Path(warpx_case_dir)

    if mock:
        return _mock_bottom_wall_species_flux()

    diags_dir = warpx_case_dir / "diags" / "openpmd"
    openpmd_files = _iter_openpmd_files(diags_dir)

    if len(openpmd_files) <= STEADY_STATE_WARMUP_ITERATIONS:
        raise ValueError(
            f"not enough openPMD iterations in {diags_dir} to isolate a steady-state window "
            f"(found {len(openpmd_files)}, need > {STEADY_STATE_WARMUP_ITERATIONS})"
        )
    steady_state_files = openpmd_files[STEADY_STATE_WARMUP_ITERATIONS:]

    species_weight_totals: dict[str, float] = {}

    for path in steady_state_files:
        with h5py.File(path, "r") as f:
            iteration = _iteration_key(f)
            particles_group = f[f"/data/{iteration}/particles"]
            scraped_species = _substrate_scraped_species(list(particles_group.keys()))

            for scraped_name in scraped_species:
                base_species = scraped_name.removesuffix(SUBSTRATE_SCRAPING_SUFFIX)
                weight_sum = _scraped_weight_sum(particles_group, scraped_name)
                species_weight_totals[base_species] = (
                    species_weight_totals.get(base_species, 0.0) + weight_sum
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
