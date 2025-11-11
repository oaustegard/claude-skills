#!/bin/bash
# Quick check if ydata-profiling is installed
VENV_PYTHON="/home/claude/.venvs/exploring-data/bin/python"
[ -f "$VENV_PYTHON" ] && echo "installed" || echo "not_installed"
