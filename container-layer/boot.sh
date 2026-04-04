#!/bin/bash
# Muninn boot via container-layer
# Replaces the manual curl+tar+setup with a cacheable Containerfile.
#
# Flow:
#   1. Bootstrap: fetch container-layer skill (tiny, ~30KB)
#   2. Restore/build: container-layer handles skills fetch + pip installs,
#      using cached tarball from GitHub Releases when available
#   3. Muninn init: source env vars, run Python boot (Turso, always live)
#
# Cache invalidation: includes claude-skills repo HEAD SHA in cache key,
# so a skills push auto-triggers a full rebuild on next boot.

set -e

# ── Step 1: Bootstrap the container-layer skill ──────────
# We need the skill itself before we can use it. This is the one
# unavoidable fetch — everything else can be cached.
LAYER_SKILL="/mnt/skills/user/container-layer"
if [ ! -f "$LAYER_SKILL/scripts/containerfile.py" ]; then
    echo "Bootstrapping container-layer skill..."
    mkdir -p "$LAYER_SKILL"
    curl -sL "https://codeload.github.com/oaustegard/claude-skills/tar.gz/main" \
        | tar -xz --strip-components=2 -C "$LAYER_SKILL" "claude-skills-main/container-layer/" 2>/dev/null \
        || { echo "Bootstrap fetch failed"; exit 1; }
fi

# ── Step 2: Locate Containerfile ─────────────────────────
# Look in project files first, then fall back to the skill's bundled default
CONTAINERFILE=""
for candidate in \
    "/mnt/project/Containerfile" \
    "$LAYER_SKILL/Containerfile"; do
    [ -f "$candidate" ] && CONTAINERFILE="$candidate" && break
done

if [ -z "$CONTAINERFILE" ]; then
    echo "ERROR: No Containerfile found"
    exit 1
fi

# ── Step 3: Source credentials ───────────────────────────
set -a
for envfile in /mnt/project/*.env; do
    [ -f "$envfile" ] && . "$envfile" 2>/dev/null
done
set +a

# ── Step 4: Restore or build the layer ───────────────────
echo "Container layer: $CONTAINERFILE"
cd "$LAYER_SKILL"
python3 -m scripts.cli \
    --token "$GH_TOKEN" \
    --invalidate-on oaustegard/claude-skills \
    restore "$CONTAINERFILE"

# ── Step 5: Output available skills ──────────────────────
echo ""
echo "<available_skills source=\"/mnt/skills/user\">"
for skill_dir in /mnt/skills/user/*/; do
    skill_file="${skill_dir}SKILL.md"
    if [ -f "$skill_file" ]; then
        name=$(grep -m1 "^name:" "$skill_file" | sed 's/name: *//')
        desc=$(grep -m1 "^description:" "$skill_file" | sed 's/description: *//')
        [ -n "$name" ] && echo "<skill><n>$name</n><description>$desc</description><location>${skill_file}</location></skill>"
    fi
done
echo "</available_skills>"

# ── Step 6: Muninn boot (always live — queries Turso) ────
echo ""
echo "Booting Muninn..."
python3 << 'PYEOF'
import os
from scripts import boot
print(boot(mode=os.environ.get('BOOT_MODE')))
PYEOF
