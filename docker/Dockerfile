# Reproducible base image for the CVD Optimizer: OS-level build tooling for
# OpenFOAM (MPI, HDF5), WarpX, and Xolotl, plus uv for the Python CLI.
# Building WarpX and Xolotl themselves is still a follow-up -- OpenFOAM is
# installed below from prebuilt packages, since compiling it from source
# takes hours.

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

WORKDIR /workspace
