#!/bin/bash
# Run ydata-profiling analysis
# Usage: analyze.sh <datafile> [minimal|full] [html|json|both]

set -e

DATAFILE="$1"
MODE="${2:-minimal}"  # default: minimal
FORMAT="${3:-html}"   # default: html

VENV_PYTHON="/home/claude/.venvs/exploring-data/bin/python"
OUTPUT_DIR="/mnt/user-data/outputs"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: ydata-profiling not installed"
    echo "Run: bash /mnt/skills/user/exploring-data/scripts/install_ydata.sh"
    exit 1
fi

if [ ! -f "$DATAFILE" ]; then
    echo "Error: File not found: $DATAFILE"
    exit 1
fi

# Set minimal flag
if [ "$MODE" = "minimal" ]; then
    MINIMAL_FLAG="True"
else
    MINIMAL_FLAG="False"
fi

# Determine what to generate
GENERATE_HTML="false"
GENERATE_JSON="false"

if [ "$FORMAT" = "json" ]; then
    GENERATE_JSON="true"
elif [ "$FORMAT" = "both" ]; then
    GENERATE_HTML="true"
    GENERATE_JSON="true"
else
    # Default: HTML + always generate JSON for potential Claude analysis
    GENERATE_HTML="true"
    GENERATE_JSON="true"
fi

# Generate report
"$VENV_PYTHON" << PYEOF
import sys
from pathlib import Path
from ydata_profiling import ProfileReport
import pandas as pd

filepath = Path("$DATAFILE")

# Load data
if filepath.suffix == '.csv':
    df = pd.read_csv(filepath)
elif filepath.suffix == '.xlsx':
    df = pd.read_excel(filepath)
elif filepath.suffix == '.json':
    df = pd.read_json(filepath)
elif filepath.suffix == '.parquet':
    df = pd.read_parquet(filepath)
elif filepath.suffix == '.tsv':
    df = pd.read_csv(filepath, sep='\t')
else:
    print(f"Unsupported format: {filepath.suffix}")
    sys.exit(1)

# Generate profile
minimal = $MINIMAL_FLAG
profile = ProfileReport(df, minimal=minimal, title=f"EDA: {filepath.name}")

# Output files
output_dir = Path("$OUTPUT_DIR")
html_path = output_dir / "eda_report.html"
json_path = output_dir / "eda_report.json"

# Generate requested outputs
if "$GENERATE_HTML" == "true":
    profile.to_file(html_path)
    print(f"✓ HTML report: {html_path}")

if "$GENERATE_JSON" == "true":
    profile.to_file(json_path)
    print(f"✓ JSON report: {json_path}")

# Print summary
print(f"\nDataset: {len(df):,} rows × {len(df.columns)} columns")
print(f"Mode: {'Minimal' if minimal else 'Full'} analysis")
PYEOF
