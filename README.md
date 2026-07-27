# CVD Optimizer

A closed-loop simulation pipeline for optimizing Chemical Vapor Deposition
(CVD) chamber parameters — targeting lab-grown diamond and wide-bandgap
semiconductor (SiC, GaN) growth. It couples three open-source physics codes
across scales instead of trial-and-error tuning gas flow, microwave power,
and substrate temperature on real hardware:

```
[OpenFOAM] -> [WarpX] -> [Xolotl]
 chamber       microwave      surface
 fluid/heat -> plasma      -> crystal
 flux          ionization     growth
```

- **OpenFOAM** (`reactingFoam`) simulates gas flow, heat transfer, and
  species transport inside the reactor chamber.
- **WarpX** (Particle-In-Cell) simulates the microwave plasma and tracks
  ions arriving at the substrate.
- **Xolotl** (cluster dynamics) simulates atom-by-atom surface growth and
  defect accumulation from that arrival flux.

Each handoff between stages is a real data transformation, not just a file
copy — see `src/cvd/utils/foam_parser.py` (OpenFOAM → WarpX) and
`src/cvd/utils/hdf5_mapper.py` (WarpX → Xolotl) for exactly what's
extracted and how. Background/motivation is in `ARCHITECTURE.md`.

## Repository layout

```
src/cvd/                   Python package — the `cvd` CLI
  cli.py                   click entrypoint: openfoam / warpx / xolotl / visualize
  schemas.py                Pydantic models for params.yaml (pint-typed dimensional fields)
  utils/
    foam_parser.py          Data-Handshake A: OpenFOAM -> WarpX (PyVista)
    hdf5_mapper.py           Data-Handshake B: WarpX -> Xolotl (openPMD/HDF5)
    xolotl_parser.py         Xolotl retentionOut.txt -> crystal_growth_metrics.csv

workflows/
  _shared/                  Jinja2 templates for each solver's config files
    openfoam/                system/, constant/, 0/ -- a full OpenFOAM case skeleton
    warpx/inputs.jinja2       WarpX PIC input deck
    xolotl/params.jinja2      Xolotl parameter deck
  test/                      Coarse/fast pipeline (params.yaml + dvc.yaml)
  prod/                      High-fidelity pipeline (currently an empty placeholder)

docker/                     Reproducible image: OpenFOAM 13 (apt) + WarpX + Xolotl
                             (both built from source), all on PATH alongside uv
```

## Setup

The `cvd` CLI itself only needs Python + [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run cvd --help
```

The real physics solvers (`blockMesh`, `reactingFoam`, `warpx`, `xolotl`)
are heavy compiled binaries that only exist inside the project's Docker
image — you don't need them to explore the CLI or run the pipeline in
`--mock` mode (see below), but any *real* solve has to happen inside the
container:

```bash
docker/build.sh                     # build the image (compiles WarpX + Xolotl from source -- slow, one-time)
docker/run.sh                       # drop into a shell with the repo mounted at /workspace
```

## Quick start: run the pipeline

The pipeline is orchestrated with [DVC](https://dvc.org/), which tracks
each stage's command, dependencies, and outputs, and only re-runs stages
whose inputs actually changed.

```bash
cd workflows/test
uv run dvc repro          # runs stale/all stages
uv run dvc dag            # see the stage graph
```

This drives the same three `cvd` commands described below, reading
parameters from `params.yaml` and passing each stage's real output forward
to the next (`terminal_fluid_state.json` → WarpX, `surface_bombardment_flux.h5`
→ Xolotl). Run it from inside `docker/run.sh` for a real solve, or see
`--mock` below for a fast dependency-free smoke test.

## The `cvd` CLI

Each solver has a `configure` (render config from `params.yaml`) and `run`
(execute the solver, then hand data to the next stage) command:

```bash
cvd openfoam configure --params params.yaml --output-dir openfoam_case
cvd openfoam run       --case openfoam_case --params params.yaml

cvd warpx configure --params params.yaml --fluid-state openfoam_case/terminal_fluid_state.json --output-dir warpx_case
cvd warpx run       --case warpx_case --params params.yaml

cvd xolotl configure --params params.yaml --flux-file warpx_case/surface_bombardment_flux.h5 --output-dir xolotl_case
cvd xolotl run       --case xolotl_case
```

Every `run` command takes `--mock`, which skips the real solver binary
entirely and writes placeholder outputs in its place — useful for testing
the pipeline's wiring (or developing without Docker) without needing
`blockMesh`/`warpx`/`xolotl` on `PATH`:

```bash
cvd openfoam run --case openfoam_case --params params.yaml --mock
```

`workflows/test/dvc.yaml` currently runs all three stages for real
(no `--mock`); drop `--mock` back in per-stage if you need a faster
iteration loop while working outside Docker.

Full option list for any command: `cvd <group> <command> --help`.

### `cvd visualize`

Once the pipeline has run, generate a results chart, a terminal summary,
and — for every stage — a real file you can open directly in
[ParaView](https://www.paraview.org/) for interactive 3D exploration:

```bash
cvd visualize
```

- **`growth_plot.png`** — thickness and defect density vs. time, plotted
  from `xolotl_case/crystal_growth_metrics.csv`.
- **Terminal summary** — final substrate temperature and gas mass
  fractions from `openfoam_case/terminal_fluid_state.json`.
- **ParaView files** — printed at the end of the command:
  - OpenFOAM: `openfoam_case/case.foam` (mesh + fields — OpenFOAM writes
    this natively).
  - WarpX: `warpx_case/diags/*/paraview.pmd` (plasma particles and
    substrate-impact events — WarpX writes these natively too).
  - Xolotl: `xolotl_case/paraview/crystal_growth.pvd` — Xolotl has no
    native 3D output, so `cvd visualize` builds one: a time series of the
    crystal's growth, colored by the real defect density at each layer's
    deposition time. Open the `.pvd` file in ParaView and press play.

## Parameters (`params.yaml`)

Every stage reads the same file, validated by `src/cvd/schemas.py`
(`CVDParameters`). Dimensional fields are [pint](https://pint.readthedocs.io/)
quantities — units are mandatory and checked (`"30 cm"` and `"0.3 m"` both
work; a bare `0.3` doesn't):

```yaml
chamber:
  type: cylinder
  diameter: "30 cm"
  height: "40 cm"
  substrate_temperature: "1100 K"

feedstock_gas:
  pressure: "40 torr"
  inlet_velocity: "50 cm/s"
  mass_fractions:
    CH4: 0.04
    H2: 0.96

microwave_source:
  frequency: "2.45 GHz"
  power: "3.5 kW"

openfoam:
  version: "13"
  solver: "reactingFoam"
  n_procs: 4                # >1 runs decomposePar + mpirun
  mesh:
    cell_target: "2 mm"

warpx:
  n_steps: 50000
  scoring_mesh:
    n_bins_xyz: [128, 128, 64]

xolotl:
  dimensions: 1
  runtime: "12 h"
  interstitial_traps: true
```

## Known limitations

This pipeline runs real solvers end-to-end, but several pieces are
deliberately coarse or stand-ins, each documented in code where it matters:

- **Mesh/grid resolution is hardcoded small** for fast validation
  (OpenFOAM's wedge mesh, WarpX's PIC grid) rather than driven by
  `openfoam.mesh.cell_target` / `warpx.scoring_mesh` — those params exist
  in the schema but aren't wired to real resolution yet.
- **WarpX doesn't self-consistently drive ionization** from the microwave
  source; it initializes an already-ionized plasma at an assumed weak
  ionization fraction instead (see `_warpx_render_context` in `cli.py`).
- **Xolotl has no diamond/CVD material** — it's fusion/nuclear-materials
  code repurposed here. `workflows/_shared/xolotl/params.jinja2` uses
  `W100` (tungsten) as the closest real semantic fit (a genuine surface-flux
  material, unlike the simpler "Fuel" tutorial config, which reinterprets
  flux as an internal fission rate). `thickness` in the growth metrics is a
  fluence-based proxy, not literal nanometers.
- **`workflows/prod/`** is still an empty placeholder.

## Development notes

- `docker/run.sh` bind-mounts the repo, so `.venv` gets rebuilt Linux-native
  if you run `uv` inside the container — if you hit venv errors switching
  back to the host, `rm -rf .venv && uv sync` fixes it.
- DVC output directories (`openfoam_case/`, `warpx_case/`, `xolotl_case/`)
  are git-ignored (see `workflows/test/.gitignore`) — DVC, not git, tracks
  their content hashes via `dvc.lock`.
