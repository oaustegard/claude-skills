#!/bin/bash
# Install ydata-profiling via uv (runs once, ~19s)
set -e

VENV_PATH="/home/claude/.venvs/exploring-data"

echo "⚙️  Installing ydata-profiling (~19 seconds, one-time only)..."

# Create venv
uv venv "$VENV_PATH" 2>&1 | grep -v "Using Python"

# Install packages.
#  - setuptools<81: ydata-profiling 4.18.x still imports pkg_resources, which
#    was removed from setuptools>=81. Unpinned, uv resolves the latest and the
#    first ProfileReport import dies with ModuleNotFoundError: pkg_resources.
#  - pyarrow: analyze.sh reads .parquet via pandas, which needs an engine.
uv pip install ydata-profiling "setuptools<81" pyarrow --python "$VENV_PATH" 2>&1 | tail -3

echo "✓ Installation complete!"
