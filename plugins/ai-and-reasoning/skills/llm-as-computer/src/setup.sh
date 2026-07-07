#!/bin/bash
# Setup script for LLM-as-Computer skill
# Installs Mojo (slim — no ML serving deps) and compiles the executor binary
set -e

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
MOJO_SRC="$SKILL_DIR/executor.mojo"
MOJO_BIN="$SKILL_DIR/percepta_exec"

# Skip if binary already exists
if [ -f "$MOJO_BIN" ]; then
    echo "Binary exists: $MOJO_BIN"
    exit 0
fi

# Install Mojo if needed
if ! mojo --version 2>/dev/null; then
    echo "Installing Mojo (slim)..."
    # modular --no-deps: gets compiler binary (1.1GB) without max[benchmark]/max[serve] extras
    # mojo + max: gets entry points and base deps (numpy, pyyaml, rich) — no transformers/pyarrow
    uv pip install --system --break-system-packages modular --no-deps 2>&1 | tail -3
    uv pip install --system --break-system-packages mojo max 2>&1 | tail -3
fi

echo "Mojo: $(mojo --version)"

# Compile
echo "Compiling executor..."
mojo build "$MOJO_SRC" -o "$MOJO_BIN"
echo "Ready: $MOJO_BIN"
