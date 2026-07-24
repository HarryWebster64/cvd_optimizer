#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root. Drops into an interactive shell inside the
# cvd_optimizer_base image, with the repo bind-mounted at /workspace.
docker run -it --rm -v "$(pwd)":/workspace -w /workspace cvd_optimizer_base
