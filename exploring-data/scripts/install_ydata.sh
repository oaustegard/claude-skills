#!/bin/bash
# Install ydata-profiling via uv (runs once, ~19s)
set -e

VENV_PATH="/home/claude/.venvs/exploring-data"

echo "⚙️  Installing ydata-profiling (~19 seconds, one-time only)..."

# Create venv
uv venv "$VENV_PATH" 2>&1 | grep -v "Using Python"

# Install packages
uv pip install ydata-profiling setuptools --python "$VENV_PATH" 2>&1 | tail -3

echo "✓ Installation complete!"
