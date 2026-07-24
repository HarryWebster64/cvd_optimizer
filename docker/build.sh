#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root.
docker build -t cvd_optimizer_base -f docker/Dockerfile .
