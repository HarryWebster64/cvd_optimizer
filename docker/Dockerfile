# Reproducible base image for the CVD Optimizer: OpenFOAM, WarpX, and Xolotl,
# plus uv for the Python CLI. OpenFOAM is installed from prebuilt packages
# (compiling it from source takes hours); WarpX and Xolotl have no apt
# packages, so both are compiled from source below. HDF5 is the *parallel*
# (openmpi) build -- WarpX's openPMD diagnostics and Xolotl both do
# MPI-collective I/O, and the plain serial libhdf5-dev can't do that.

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    mpi-default-dev \
    libhdf5-openmpi-dev \
    git \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Install OpenFOAM (openfoam.org build) from its official prebuilt apt
# repository. "jammy" matches the ubuntu:22.04 base above.
RUN curl -fsSL https://dl.openfoam.org/gpg.key | gpg --dearmor -o /usr/share/keyrings/openfoam-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/openfoam-archive-keyring.gpg] http://dl.openfoam.org/ubuntu jammy main" > /etc/apt/sources.list.d/openfoam.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends openfoam13 \
    && rm -rf /var/lib/apt/lists/*

# OpenFOAM's environment (PATH, LD_LIBRARY_PATH, WM_* variables, etc.) is
# computed by sourcing its bashrc script -- it can't be flattened into a
# single static ENV PATH, since reactingFoam also needs OpenFOAM's shared
# libraries and internal variables that bashrc sets up. BASH_ENV makes
# non-interactive `bash -c "..."` invocations (e.g. CI) pick it up too;
# the .bashrc line covers interactive shells (`docker run -it`, our
# docker/run.sh). Neither of these touches uv/Python -- separate PATH
# entries, no shared files.
ENV BASH_ENV=/opt/openfoam13/etc/bashrc
RUN echo "source /opt/openfoam13/etc/bashrc" >> /root/.bashrc

# Install WarpX from source (no apt package exists). Split into separate
# clone / configure / build layers so an unrelated later edit to this
# Dockerfile doesn't force Docker to re-run the whole (long) compile from
# cache. CPU-only (OMP) build, 3D, with MPI and openPMD/HDF5 diagnostics --
# AMReX and openPMD-api are fetched automatically by WarpX's CMake build.
RUN git clone --branch 24.04 --depth 1 https://github.com/ECP-WarpX/WarpX.git /opt/WarpX

RUN cmake -S /opt/WarpX -B /opt/WarpX/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DWarpX_DIMS=3 \
    -DWarpX_COMPUTE=OMP \
    -DWarpX_MPI=ON \
    -DWarpX_OPENPMD=ON

# The built executable is named after its enabled options (e.g.
# warpx.3d.MPI.OMP.DP.OPMD.QED) -- glob for it rather than hardcoding the
# exact suffix, since option ordering/composition can shift between
# versions, then symlink it as `warpx` onto the existing PATH.
RUN cmake --build /opt/WarpX/build -j"$(nproc)" \
    && WARPX_BIN=$(find /opt/WarpX/build/bin -maxdepth 1 -type f -name 'warpx.3d.*' | head -n 1) \
    && test -n "$WARPX_BIN" \
    && ln -s "$WARPX_BIN" /usr/local/bin/warpx \
    && echo "Symlinked $WARPX_BIN -> /usr/local/bin/warpx"

# Xolotl-specific OS dependencies, kept in their own layer (rather than the
# shared apt list above) so further Xolotl dependency fixes don't force
# Docker to redo the OpenFOAM/WarpX layers, which don't need them.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-log-dev \
    libboost-program-options-dev \
    libboost-test-dev \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Install Xolotl from source (no apt package exists). No --branch pinned --
# clone the repo's actual default branch, whether it's named main or master.
# Same clone / configure / build layer split as WarpX, for the same caching
# reasons.
#
# Xolotl needs PETSc built *with* Kokkos and KokkosKernels -- Ubuntu's
# petsc-dev (3.15, no Kokkos backend) can't satisfy that, and there's no
# flag that retrofits it. Xolotl's own docs recommend -DXolotl_BUILD_PETSC=ON
# instead: its CMake configure step fetches and compiles Kokkos,
# KokkosKernels, and PETSc itself. -DXolotl_ENABLE_OPENMP=ON selects the
# CPU-only Kokkos backend, matching WarpX's -DWarpX_COMPUTE=OMP above.
RUN git clone --depth 1 https://github.com/ORNL-Fusion/xolotl.git /opt/xolotl

RUN cmake -S /opt/xolotl -B /opt/xolotl/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DXolotl_BUILD_PETSC=ON \
    -DXolotl_ENABLE_OPENMP=ON \
    || (echo '--- plsm_configure.out (tail) ---'; tail -n 100 /opt/xolotl/build/external/plsm_configure.out 2>/dev/null; \
        echo '--- petsc_build.out (tail) ---'; tail -n 200 /opt/xolotl/build/external/petsc_build.out 2>/dev/null; \
        exit 1)

# Exact output location/name isn't guaranteed ahead of time, so search the
# build tree for an executable file named `xolotl` rather than hardcoding a
# path, mirroring the WarpX glob above.
RUN cmake --build /opt/xolotl/build -j"$(nproc)" \
    && XOLOTL_BIN=$(find /opt/xolotl/build -maxdepth 6 -type f -iname 'xolotl' -perm -u+x | head -n 1) \
    && test -n "$XOLOTL_BIN" \
    && ln -s "$XOLOTL_BIN" /usr/local/bin/xolotl \
    && echo "Symlinked $XOLOTL_BIN -> /usr/local/bin/xolotl"

WORKDIR /workspace
