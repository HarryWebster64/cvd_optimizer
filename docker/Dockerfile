# Reproducible base image for the CVD Optimizer: OS-level build tooling for
# OpenFOAM (MPI, HDF5), WarpX, and Xolotl, plus uv for the Python CLI.
# Building Xolotl is still a follow-up. OpenFOAM is installed from prebuilt
# packages (compiling it from source takes hours); WarpX has no apt package
# at all, so it's compiled from source below.

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    mpi-default-dev \
    libhdf5-dev \
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

WORKDIR /workspace
