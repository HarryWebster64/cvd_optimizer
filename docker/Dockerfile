# Reproducible base image for the CVD Optimizer: OS-level build tooling for
# OpenFOAM (MPI, HDF5), WarpX, and Xolotl, plus uv for the Python CLI.
# Building the physics solvers themselves is a follow-up -- this image is
# the shared foundation they'll be layered on.

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    mpi-default-dev \
    libhdf5-dev \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /workspace
