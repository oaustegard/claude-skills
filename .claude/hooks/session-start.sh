#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Muninn boot: load profile + ops from Turso into the session.
# This replaces the manual "python3 << EOF ... boot() ... EOF" block
# that was previously in CLAUDE.md's "Muninn Boot" section.
#
# The boot output is printed to stdout so the agent sees the profile
# and operational context at session start.

python3 - <<'PYEOF'
import sys, os

# Ensure the remembering skill package is importable
skill_dir = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR", "/home/user/claude-skills"), "remembering")
sys.path.insert(0, skill_dir)

try:
    from scripts import boot
    print(boot())
except Exception as e:
    # Non-fatal: not all sessions need memory access (missing creds, network, etc.)
    print(f"Muninn boot skipped: {e}", file=sys.stderr)
PYEOF
