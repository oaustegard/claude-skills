#!/bin/bash
# Container-layer boot for Claude Code (Web + CLI)
# Called by SessionStart hook. stdout goes into Claude's context.
#
# Ephemeral containers: bootstraps skill, restores cached layer or builds fresh.
# Idempotent within a session via marker file.

set -e

MARKER="/tmp/.container-layer-booted"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CONTAINERFILE="$(cd "$PROJECT_DIR" && pwd)/Containerfile"

# ── Functions ──

_output_skills() {
    local skills_dir="${1:-/mnt/skills/user}"
    [ -d "$skills_dir" ] || return 0
    echo ""
    echo "Available skills:"
    for skill_dir in "$skills_dir"/*/; do
        local skill_file="${skill_dir}SKILL.md"
        if [ -f "$skill_file" ]; then
            local name=$(grep -m1 "^name:" "$skill_file" | sed 's/name: *//')
            [ -n "$name" ] && echo "  - $name"
        fi
    done
}

_source_env() {
    # Source from project dir
    for envfile in "$PROJECT_DIR"/*.env "$PROJECT_DIR"/.env; do
        [ -f "$envfile" ] && { set -a; . "$envfile" 2>/dev/null; set +a; }
    done
    # Also check Claude.ai project files
    for envfile in /mnt/project/*.env; do
        [ -f "$envfile" ] && { set -a; . "$envfile" 2>/dev/null; set +a; }
    done
}

# ── Idempotency ──
if [ -f "$MARKER" ]; then
    echo "Environment ready (cached)."
    _output_skills
    exit 0
fi

# ── Main ──
_source_env

# Bootstrap the container-layer skill from GitHub
SKILL_DIR="/tmp/_container_layer"
if [ ! -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    echo "Bootstrapping container-layer..."
    mkdir -p "$SKILL_DIR"
    if curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" \
        | tar -xz --strip-components=2 -C "$SKILL_DIR" "claude-skills-main/container-layer/" 2>/dev/null; then
        echo "  ✓ container-layer skill loaded"
    else
        echo "  ✗ bootstrap failed (check network/token)"
        exit 1
    fi
fi

# Apply the Containerfile
if [ -f "$CONTAINERFILE" ] && [ -f "$SKILL_DIR/scripts/containerfile.py" ]; then
    echo "Applying container layer: $CONTAINERFILE"

    INVALIDATE_ARGS=""
    if [ -n "$INVALIDATE_ON" ]; then
        for repo in $INVALIDATE_ON; do
            INVALIDATE_ARGS="$INVALIDATE_ARGS --invalidate-on $repo"
        done
    fi

    cd "$SKILL_DIR"
    python3 -m scripts.cli \
        --token "${GH_TOKEN:-}" \
        --repo "${LAYER_CACHE_REPO:-oaustegard/claude-container-layers}" \
        $INVALIDATE_ARGS \
        restore "$CONTAINERFILE" 2>&1
    cd - > /dev/null

    echo "✓ Container layer applied"
else
    echo "No Containerfile found at $CONTAINERFILE — skipping."
fi

touch "$MARKER"
_output_skills

# Custom post-boot hook
[ -f "$PROJECT_DIR/post-boot.sh" ] && bash "$PROJECT_DIR/post-boot.sh" 2>&1

exit 0
