CVD Diamond/Semiconductor Production

Lab grown diamond is a fast growing industry and CVD (Chemical Vapor Deposition) machine optimization is a top priority and struggle. Companies are largely doing trial and error tuning of parameters like microwave power, gas ratios, pressure, and substrate temperature. Diamond growth is fundamentally a plasma physics and fluid dynamics problem. Inside a CVD chamber, you have the exact same physics domains as a fusion reactor or an advanced aerospace vehicle: fluid dynamics, plasma physics, high-temperature thermodynamics, and surface chemistry. High-purity diamond layers and advanced semiconductor wafers (such as Silicon Carbide and Gallium Nitride) are the foundational materials driving modern power electronics and quantum devices. Alongside the rapid rise of lab-grown diamonds, the semiconductor industry is increasingly relying on CVD architectures to manufacture advanced wide-bandgap wafers. Currently, fabrication facilities face staggering financial losses due to trial-and-error tuning of parameters like microwave power, gas ratios, pressure, and substrate temperature to grow these complex crystal structures without catastrophic atomic defects.
How Our Existing Code Inventory Models a CVD Machine
To simulate a CVD machine, a company needs to look at the process at two distinct scales: the Macro-scale Reactor (how gas and heat flow through the machine) and the Micro-scale Surface (how carbon or silicon atoms actually bind together to grow the crystal). 
The Macro-Scale (Gas Flow, Plasma, & Heat)
OpenFOAM: This is the industry-standard tool for modeling macro-scale CVD chambers. Engineers use it to track how gases like methane and hydrogen flow through the nozzles, how the gas distributes across the substrate, and how temperature gradients form.
WarpX / Chi-Tech (: Many diamond or semiconductor CVD systems use Microwave Plasma-Enhanced CVD (PECVD). You need plasma codes to simulate how the microwave radiation physically ionizes the gas mixture into a high-energy plasma.
The Micro-Scale (Atom-by-Atom Crystal Growth)
Xolotl (New Candidate): While Xolotl was built at Oak Ridge National Laboratory to model how helium gas damages fusion walls, its underlying mathematical solver (spatially dependent cluster dynamics) is precisely what is used to simulate how chemical species diffuse, migrate, and cluster on a substrate to grow a flat diamond or silicon lattice.
To capture this market, we could offer a specialized "CVD Optimizer" loop. This loop eliminates the trial-and-error process where hardware companies accidentally ruin millions of dollars in wafer or diamond batches trying to calibrate gas flows manually.
The Closed-Loop Epitaxial Growth Pipeline: This multi-scale workflow matches fluid gas dynamics with surface atomic chemistry, allowing engineers to predict wafer thickness uniformity and crystal defect rates based on chamber inputs.
[OpenFOAM] -> [WarpX] -> [Xolotl / KMC Solver]
(Chamber Fluid & Heat Flux)     (Plasma Gas Ionization Rates)   (Surface Atomic Crystal Growth)
How it Works:
OpenFOAM simulates the mass transfer, velocity profiles, and temperature fields of the raw precursor gases inside the chamber geometry.
WarpX uses those local gas densities to simulate the microwave electromagnetic fields, determining exactly where the plasma forms and the chemical dissociation rates (e.g., how fast CH4 cracks into reactive CH3 radicals).
Xolotl (or an integrated on-lattice Kinetic Monte Carlo solver) ingests those radical fluxes as a surface arrival rate to track the atom-by-atom deposition, surface migration, and potential defect formation on the diamond or semiconductor wafer substrate.
High-Value Targeting 
The Power Electronics & Semiconductor Boom
Next-generation chips (for EV inverters, AI data centers, and defense radar) are moving away from silicon and moving toward Wide-Bandgap Semiconductors like Silicon Carbide (SiC) and Gallium Nitride (GaN). Growing these crystals requires highly precise CVD recipes to prevent atomic dislocations. We can help chip designers optimize their growth configurations to eliminate these structural defects before running physical manufacturing lots.
Lab-Grown Diamonds for Quantum Hardware
Along with jewelry, companies are growing synthetic diamonds via CVD to act as the base material for Quantum Computing hardware (using Nitrogen-Vacancy, or NV-center, diamond hubs). The diamonds must be extremely defect free and high quality while also being n and p doped similarly to the functionality of a transistor. 
Their Problem: If a diamond grows too quickly, it traps unwanted hydrogen atoms, destroying its quantum coherence.
The Solution: Our software could help them simulate how to tune their CVD microwave plasma to drop the density of unwanted atomic defects. 
—-----------------------------------------------------------------------------------
Market: 
Semiconductors and Electronics:
-Coherent
-Element Six (De Beers Group)
-Diamond Semicon
-Mitsubishi Electric

Companies like Coherent or Mitsubishi Electric are trying to grow Silicon Carbide and Gallium Nitride wafers for EV inverters and AI data centers. Because you cannot easily place physical sensors inside a 1000 degree microwave plasma storm, finding the correct balance of parameters is blind guesswork. A single failed CVD production run can ruin a batch of wafers worth upwards of $50,000 to 100,000. 

Quantum Computing: 
-Element Six
-Quantum Diamond Technologies (QDT)
-PPPL

Jewelry:
-De Beers (Lightbox)
-Diamond Foundry
-WD Lab Grown Diamonds

Potential Partners (CVD Equipment Manufacturers):
-Seki Diamond Systems
-Carat Systems
-Plassys
-Aixtron

Existing Softwares:
-CVDSim3D: CVDSim3D - STR Software for Modeling of Crystal Growth, Epitaxy, and Semiconductor Devices 
What they do: Specialized software like CVDSim3D (by STR Software) or PIC-PLASMA 3D are used by equipment designers to model showerhead gas injectors and calculate plasma uniformity over a flat plate.
Where they fail: These tools are incredibly rigid, closed-source, and rarely updated. They do not leverage modern exascale, GPU-accelerated codebases. They are designed exclusively to help build the hardware reactor box, not to help a quantum computing or semiconductor startup perfect an atomic-scale crystal recipe.


-COMSOL (Customized for CVD)
What they do: COMSOL and ANSYS can model fluid flow, heat transfer, and basic plasma chemistry using traditional fluid-based (fluid-continuity) approximations.
Where they fail: They treat the plasma as a simplified liquid or continuous gas field. They completely fail at high-fidelity particle tracking (like tracking individual electrons hitting methane molecules), and their surface models are purely mathematical equations (e.g., "multiply the gas concentration by a flat growth rate constant"). They cannot simulate the atomistic crystal structure, defects, or how individual carbon atoms migrate on a seed wafer to grow a lattice.


The fundamental flaw in all existing software is scale isolation. Companies can either model the big reactor chamber gas flow (Macro) or run a separate atomistic script of crystal lattice growth (Micro), but no commercial platform binds them seamlessly. What we could do is automate a staggered partitioned black-box coupling that continuously passes three-dimensional spatial data fields between the codes without user coding. Instead of approximating the plasma as a uniform gas, our engine extracts the spatial chemical species fields from OpenFOAM and hands them to WarpX. WarpX uses a Particle-in-Cell (PIC) method—simulating actual physical macro-particles colliding at extreme velocities. This is far more accurate for high-power microwave systems (PECVD) than anything COMSOL can achieve. Semiconductor and quantum hardware startups don't just care if a diamond grows; they care if it traps a hydrogen atom or develops a structural tilt (dislocation). COMSOL simply outputs a "thickness map." By feeding WarpX outputs into Xolotl, our platform uses cluster dynamics to simulate the actual atom-by-atom crystallization. We can show a semiconductor engineer exactly where a wafer will form a microscopic crystal crack before they ever run a physical batch. Legacy tools are anchored to expensive, localized desktop node licenses. Because OpenFOAM, WarpX, and Xolotl are open-source and natively parallelized, our platform can run massive multi-threaded iterations across cloud infrastructure (AWS/Azure) simultaneously. 



CVD Coupling Proposal 

The Closed-Loop Epitaxial Growth Pipeline: 
[OpenFOAM] -> [WarpX] -> [Xolotl / KMC Solver]
(Chamber Fluid & Heat Flux)     (Plasma Gas Ionization Rates)   (Surface Atomic Crystal Growth)
How it Works:
OpenFOAM simulates the mass transfer, velocity profiles, and temperature fields of the raw precursor gases inside the chamber geometry.
WarpX uses those local gas densities to simulate the microwave electromagnetic fields, determining exactly where the plasma forms and the chemical dissociation rates (e.g., how fast CH4 cracks into reactive CH3 radicals).
Xolotl (or an integrated on-lattice Kinetic Monte Carlo solver) ingests those radical fluxes as a surface arrival rate to track the atom-by-atom deposition, surface migration, and potential defect formation on the diamond or semiconductor wafer substrate.

Repository Architecture Layout 

cvd_optimizer/
├── src/
│   └── cvd/                         # Python package (the CLI tool)
│       ├── __init__.py
│       ├── cli.py                   # Main click entrypoint (groups: openfoam, warpx, xolotl)
│       ├── schemas.py               # Pydantic validation models (using Pint)
│       └── utils/
│           ├── foam_parser.py       # Extracts fields from OpenFOAM time directories
│           └── hdf5_mapper.py       # Maps WarpX openPMD outputs to Xolotl HDF5 boundaries
├── workflows/
│   ├── _shared/                     # Base configuration skeletons
│   │   ├── openfoam/                # blockMeshDict, reactingFoam settings
│   │   ├── warpx/                   # inputs template file for PIC plasma
│   │   └── xolotl/                  # param.txt template file for cluster dynamics
│   ├── test/                        # Coarse grid fast-run test pipeline
│   │   ├── dvc.yaml                 # DVC pipeline stages definition
│   │   └── params.yaml              # Parameter file for test case
│   └── prod/                        # High-fidelity production execution
│       ├── dvc.yaml
│       └── params.yaml
└── docker/                          # Reproducible base container (OpenFOAM + WarpX + Xolotl)



Parameter Specification 
(YAML)

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


DVC Pipeline Configuration 
(dvc.yaml)

stages:
  # Stage 1: Configure & Run OpenFOAM Fluid Mechanics
  run_fluid_cfd:
    cmd: >
      cvd openfoam configure --params params.yaml --output-dir openfoam_case &&
      cvd openfoam run --case openfoam_case
    deps:
      - params.yaml
      - ../_shared/openfoam/
    outs:
      - openfoam_case/processor0/
      - openfoam_case/terminal_fluid_state.json

  # Stage 2: Ingest Fluid Profile, Configure & Run WarpX Plasma Physics
  run_plasma_pic:
    cmd: >
      cvd warpx configure --params params.yaml --fluid-state openfoam_case/terminal_fluid_state.json --output-dir warpx_case &&
      cvd warpx run --case warpx_case
    deps:
      - params.yaml
      - ../_shared/warpx/
      - openfoam_case/terminal_fluid_state.json
    outs:
      - warpx_case/diags/openpmd/
      - warpx_case/surface_bombardment_flux.h5

  # Stage 3: Ingest Plasma Fluence, Configure & Run Xolotl Surface Deposition
  run_surface_growth:
    cmd: >
      cvd xolotl configure --params params.yaml --flux-file warpx_case/surface_bombardment_flux.h5 --output-dir xolotl_case &&
      cvd xolotl run --case xolotl_case
    deps:
      - params.yaml
      - ../_shared/xolotl/
      - warpx_case/surface_bombardment_flux.h5
    outs:
      - xolotl_case/crystal_growth_metrics.csv


Plan:

Data-Handshake A: OpenFOAM -> WarpX
WarpX needs to initialize its macro-particles over a realistic gas density baseline, but it doesn't read OpenFOAM raw mesh files.
Code Solution: (foam_parser.py): Write a script that executes immediately after reactingFoam finishes. It will open the final time directory, read the rho or mass fraction arrays, average the values immediately above the substrate position, and output a clean terminal_fluid_state.json. The cvd warpx configure command reads this JSON file to scale the dynamic neutral gas densities inside the WarpX input file template using a Jinja2 context parser.
Data-Handshake B: WarpX -> Xolotl
WarpX tracks continuous-time particle trajectories using high-performance openPMD grid libraries. Xolotl expects a single boundary flux vector inside a PETSc matrix format or an input file parameter to step forward in time.
Code Solution: (hdf5_mapper.py): Write a parsing routine that opens WarpX’s openPMD HDF5 diagnostics files. It filters out the species boundaries hitting the bottom wall layer, integrates the particle weights over the steady-state time steps, and tallies the arrival flux. The script then writes these values into the Xolotl parameter deck (params.txt), configuring Xolotl’s interstitial source generation rates automatically.

Here is mortons previous implentation for inertia. We are going to make this tool similarly. Inertia x Morton - Pilot Project
Proof-of-concept simulation pipeline for inertial fusion energy (IFE) reactor chambers.

Just want to learn the pipeline pattern? Start in tutorial/ — a stripped-down ballistic-trajectory Monte Carlo built on the same DVC + Pydantic + Pint + Jinja bones, no Geant4 / OpenFOAM dependencies, runs in seconds.

The pilot project couples Geant4 ion transport through a parametric chamber filled with low-density xenon to an OpenFOAM CFD case:

The Python package generates Geant4 and OpenFOAM inputs from YAML
Geant4 tallies volumetric energy deposition
The result is mapped onto a body-fitted CFD mesh as a volumetric heating source term.
Python generates OpenFOAM CFD configuration and manages the run process
Postprocessing and visualization
Consolidate results to a static HTML dashboard report
Dashboard screenshot

The goal is a working end-to-end demonstration of the toolchain (geometry → transport → CFD source term), not a validated physics package. In particular, all parameters, geometry, and simulation configuration in this project should be considered "representative" and has not been validated against any published data or simulation benchmarks.


Features:

Example pipeline from ion products to gas dynamics simulation (OpenFOAM) via Geant4 transport
Energy-conserving mesh mapping between axis-aligned Cartesian grids
Version-controlled workflow automation with DVC
Automated generation of a final HTML report (see above)
Quick OpenFOAM field visualization in static HTML with PyVista (via pilot openfoam render-field)
Dimensional quantities with pint
Docker containerization for build reproducibility
Local documentation of all configuration options with Pydantic-managed schemas
DVC Dash

Quickstart
Inside the Docker container (or a host with Geant4 11.x + OpenFOAM v13 at the hardcoded paths — see External Dependencies):

One time setup:

uv venv && source .venv/bin/activate   # Create a virtual environment
uv sync --all-extras --dev        # install the Python package
DVC orchestrates pipeline stages, including tracking when a stage needs to be re-run because its inputs changed. To run an example workflow:

cd workflows/prod                 # or workflows/test
dvc repro                         # build Geant4, run transport, map to CFD, run CFD
dvc metrics show                  # summary statistics
workflows/prod/outputs/edep.html is a standalone PyVista render of the mapped field — open it in a browser or VS Code's Live Preview extension. The same folder includes various interactive HTMLs, static PNGs, and CFD animations.

Documentation
The documentation can be generated locally using mkdocs, which automatically pulls from docstrings in the Python package.

To build the documentation, run

mkdocs build
Then open site/index.html in any web browser (or the VS Code Live Preview extension) to browse the pages.

Repository layout
src/pilot/              Python package — CLI and templated config generation
workflows/
  _shared/              Static Geant4 C++ and OpenFOAM case skeletons
  test/                 Quick test pipeline (10k primaries, coarse CFD mesh)
  prod/                 Full pipeline + visualizations (10M primaries)
  sweep/                Parametric radius sweep using DVC `foreach`
docker/                 Containerization (base image + devcontainer)
tests/                  Unit tests for the Python package
Each workflow folder is its own DVC root: run dvc repro from inside it.

Inputs
Parameters
Most "scalar" inputs are specified in the DVC params.yaml file. The values in this file are used by different stages of the pipeline in dvc.yaml, so changing a parameter here automatically invalidates dependent stages.

For example, an excerpt from the "prod" workflow params.yaml looks like the following:

chamber:
  type: sphere
  outer_radius: "20 m"
  polar_cone_half_angle: "45 degree"
  blanket:
    inner_radius: "10 m"
    thickness: "1 m"

fill_gas:
  properties:
    material: Xe
    molar_mass: "131.29 g/mol"
    gamma: 1.6667
  density: "8 ug/cm^3"
  temperature: "1000 K"

fusion:
  ions:
    - name: alpha
      Z: 2
      A: 4
      spectrum:
        type: maxwellian
        mean_energy: "58 keV"
      yield_per_shot: 2.3e21

geant4:
  version: "11.4.1"
  n_primaries: 10000000
  scoring_mesh:
    half_extent: "100 cm"
    n_bins: 100

openfoam:
  version: "13"

  mesh:
    bulk_cell_target: "80 cm"
    wall_cell_target: "20 cm"
    # Per-patch overrides for tighter resolution on internal walls.
    patch_wall_targets:
      firstWall: "10 cm"

  transient:
    end_time: "10 ms"
    delta_t_initial: "10 ns"
    max_co: 0.2
    write_interval: "500 us"
    n_procs: 8

    adaptive_refinement:
      enabled: true

    # Axial probes along the to monitor shock propagation
    probes:
      - name: axial
        type: line
        start: ["9.9 m", "0 m", "0 m"]
        end: ["9.9 m", "0 m", "10 m"]
        num_points: 20
        fields: ["p", "T", "U"]
This file follows the schema defined by PipelineParams and its nested submodels. This is used for validation and documentation - refer to the PipelineParams class for details on structure and allowed values.

Dimensional fields (radius, length, energy) are parsed by pint, so units are mandatory but flexible; "10 cm" and "0.1 m" are both valid, but 0.1 is not. Dimensionless counts (Z, A, yield_per_shot) do not have unit strings.

OpenFOAM templates
The OpenFOAM configuration is a mix of auto-generated files (initial condition files, probe files, snappyHexMeshDict) and copied files from a template case with overrides defined by params.yaml.

To work on developing the OpenFOAM configuration, the template case can be hand-edited directly, which will trigger re-running the CFD stages of the DVC pipeline. If needed, additional configurable parameters can be added to the appropriate schema and added to the overrides in the CLI command so that they can be tracked in params.yaml.

Python CLI
The main work is done via the DVC workflow configurations in workflows/, but each DVC stage invokes a subcommand of the pilot CLI. The subcommands are atomic building blocks — useful standalone for quick postprocessing or debugging, but normally driven by dvc repro. Run pilot --help or pilot <command> --help for CLI command documentation:

# Top-level CLI: groups by function
$ pilot --help
Usage: pilot [OPTIONS] COMMAND [ARGS]...

  Parametric IFE chamber simulation pipeline.

Options:
  --help  Show this message and exit.

Commands:
  geant4    Generate Geant4 inputs and postprocess scoring output.
  geometry  Chamber geometry export + visualization.
  openfoam  Generate, initialize, run, and visualize OpenFOAM cases.
  params    Edit, show, or validate params.yaml files

# Groups have commands for configuration, running, visualization, etc.
$ pilot geant4 --help
Usage: pilot geant4 [OPTIONS] COMMAND [ARGS]...

  Generate Geant4 inputs and postprocess scoring output.

Options:
  --help  Show this message and exit.

Commands:
  configure    Generate Geant4 input files (source and macros).
  postprocess  Postprocess Geant4 energy deposition statistics.

# <command> --help gives info on options and command structure
$ pilot geant4 configure --help
Usage: pilot geant4 configure [OPTIONS]

  Generate Geant4 input files (source and macros).

Options:
  --params FILE      YAML parameter file (params.yaml).  [required]
  --output-dir PATH  Root of the Geant4 case directory.  [default: geant4]
  --help             Show this message and exit
DVC (Data Version Control)
DVC tracks large files and pipeline outputs alongside git. Each workflow's dvc.yaml declares stages with their commands, dependencies, and outputs; dvc repro walks the DAG and re-runs only stages whose inputs have changed since the last run. Stage outputs are content-addressed into .dvc/cache/ and pushed to a remote so collaborators can dvc pull results without re-running the pipeline.

The remote is currently a "local remote" proof-of-concept at .dvc/dvcstore. For real usage this should be a NAS, S3 bucket, etc.

Useful DVC Commands
Managing the pipeline with DVC:

cd workflows/test  # Or different pipeline folder
dvc status         # Report on pipeline status
dvc repro          # Refresh entire pipeline, running only invalidated stages
dvc repro [stage-name]  # Refresh pipeline only up to specified stage
DVC works naturally with git, just adds an extra command after git, specifically anything that would change files, e.g.

# push changes
git push  # Upload only MD5 checksums
dvc push  # Upload actual data files to remote

# checkout a git branch/hash/etc
git checkout <...>
dvc checkout

# pull from remote
git pull
dvc pull
To show key metrics (e.g. energy conservation)

dvc metrics show
For a visualization of the DAG run dvc dag, e.g. to generate the Mermaid diagram shown above:

dvc dag --md
Running "experiments"
To explore parametric changes varying a baseline configuration, DVC supports "experiment" management.

For example, to run a sweep of first wall radius against the "test" workflow,

cd workflows/test
for r in 5 6 7 8; do
  dvc exp run -S "chamber.radius=${r} m" -n "radius-${r}m"
done
The -S flag allows overriding any entry in params.yaml, and -n applies a name to the experiment. Each experiment reproduces only the stages whose dependencies actually changed (though that would be all of them in this case).

The experiment results can be compared in the DVC extension for VS Code, or stored and recalled later:

dvc exp apply radius-7m              # restore a named run's params/outs to the workspace
dvc exp branch radius-7m sweep/r7m   # promote to a real git branch
By default these experiments are local unless promoted to a git branch, but one-off experiments can be pushed to remote storage:

dvc exp push origin radius-7m
Then on a fresh checkout or a different machine:

dvc exp pull origin radius-7m  # Fetch the params/results
dvc exp apply radius-7m        # Apply to current workspace
External Dependencies
Geant4 11.x with G4NDL data libraries (QGSP_BIC_HP or FTFP_BERT_HP)
OpenFOAM v13 (blockMesh, snappyHexMesh, postProcess)
Tool paths are hardcoded in src/pilot/cli.py and the workflow dvc.yaml files:

Geant4: /morton/geant4-11.4.1/install
OpenFOAM: /morton/OpenFOAM/OpenFOAM-13/etc/bashrc
The Docker image provides both at these paths; host runs need matching installs or code edits.

Docker containerization
The project is containerized for reproducibility and development. There is a base image that can run the example pipeline, and optionally a VS Code devcontainer configuration for development work. The image contains Geant4 and OpenFOAM builds along with other environment configuration.

It assumes the GitHub CLI is installed and authorized locally to load GitHub credentials into the container - this isn't necessary for basic functionality, but since DVC builds on git it is recommended to do this to do the full DVC workflow.

To build/run the base image:

./docker/build.sh
./docker/run.sh
Building on the Pilot
The workflows in this project are intended as a starting point and to demonstrate things like parameter sweeps, visualization artifacts, etc. As noted above, these are not validated simulations or meshes.

Recommendations for next steps for moving towards production usage include:

Replacing the notional fusion products with actual data
Careful review of Geant4 configuration and source and detector templates
Similar review of OpenFOAMconfiguration and mesh generation