#!/bin/bash
# Install large-file/sketch deps (system-safe self-contained wheels, ~10s)
set -e
python3 - <<'PY' 2>/dev/null && { echo installed; exit 0; }
import duckdb, datasketches, datasketch
PY
echo "Installing duckdb + datasketches + datasketch..."
pip install --break-system-packages -q duckdb datasketches datasketch
echo "done"
