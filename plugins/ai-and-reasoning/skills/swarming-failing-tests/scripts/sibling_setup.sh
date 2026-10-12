#!/bin/bash
# Bootstrap a federated sibling container for a swarm. Idempotent: rerun after a container restart.
#
#   bash sibling_setup.sh NAME [--config swarm.toml]
#
# Run from the sibling's checkout of the transport repo (create_session source_url) at the hub's
# main branch (<prefix>main). It
#   - finds this skill's scripts (the mount, else a clone of oaustegard/claude-skills in ~/claude-skills),
#     and dispatching-subagents' headless_fanout.py next to them,
#   - runs the project's own setup (config federation.setup_command: toolchains, corpora),
#   - sets the commit identity from the config's [git] section,
#   - adds the transport remote `fed` and fetches <prefix>main + <prefix>state,
#   - puts the checkout on a local branch fed-NAME (the swarm's main on this node).
# It never pushes. The loop pushes <prefix>cand/NAME itself.
set -u
NAME=${1:?usage: sibling_setup.sh NAME [--config FILE]}
CONFIG=swarm.toml
[ "${2:-}" = "--config" ] && CONFIG=${3:?--config needs a file}
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "setup: run inside the checkout" >&2; exit 2; }
cd "$ROOT"
warn() { echo "setup: WARN: $*" >&2; }

HERE=$(cd "$(dirname "$0")" && pwd)
if [ -f "$HERE/swarm.py" ]; then
  SKILL_SCRIPTS=$HERE
elif [ -f /mnt/skills/user/swarming-failing-tests/scripts/swarm.py ]; then
  SKILL_SCRIPTS=/mnt/skills/user/swarming-failing-tests/scripts
else
  [ -d "$HOME/claude-skills/.git" ] || git clone -q --depth 1 https://github.com/oaustegard/claude-skills "$HOME/claude-skills" \
    || { echo "setup: cannot fetch the skill scripts" >&2; exit 2; }
  SKILL_SCRIPTS=$HOME/claude-skills/swarming-failing-tests/scripts
fi
FANOUT=$(cd "$SKILL_SCRIPTS/../.." && pwd)/dispatching-subagents/scripts/headless_fanout.py
[ -f "$FANOUT" ] || warn "headless_fanout.py not found at $FANOUT; set SWARM_FANOUT"

[ -f "$CONFIG" ] || { echo "setup: config $CONFIG not in this checkout" >&2; exit 2; }
read_cfg() {  # read_cfg 'python expression over c' -> prints the value
  python3 - "$CONFIG" "$1" <<'EOF'
import json, sys
p, expr = sys.argv[1], sys.argv[2]
c = json.load(open(p)) if p.endswith(".json") else __import__("tomllib").load(open(p, "rb"))
v = eval(expr, {"c": c})
print(json.dumps(v) if isinstance(v, (list, dict)) else (v or ""))
EOF
}
PREFIX=$(read_cfg 'c.get("federation", {}).get("prefix", "swarm/")')
REMOTE=$(read_cfg 'c.get("federation", {}).get("remote", "")')
SETUP=$(read_cfg 'c.get("federation", {}).get("setup_command", [])')
AUTHOR=$(read_cfg 'c.get("git", {}).get("author_name", "")')
EMAIL=$(read_cfg 'c.get("git", {}).get("author_email", "")')
[ -n "$REMOTE" ] || { echo "setup: federation.remote is empty in $CONFIG" >&2; exit 2; }

export SWARM_SIBLING=$NAME
if [ "$SETUP" != "[]" ] && [ -n "$SETUP" ]; then
  python3 -c 'import json,subprocess,sys; sys.exit(subprocess.run(json.loads(sys.argv[1])).returncode)' "$SETUP" \
    >/tmp/sibling-setup.log 2>&1 || warn "project setup failed (see /tmp/sibling-setup.log)"
fi
[ -n "$AUTHOR" ] && git config user.name "$AUTHOR"
[ -n "$EMAIL" ] && git config user.email "$EMAIL"
git remote get-url fed >/dev/null 2>&1 || git remote add fed "$REMOTE"
git fetch -q --no-tags fed "+refs/heads/${PREFIX}main:refs/fed/main" "+refs/heads/${PREFIX}state:refs/fed/state" \
  || warn "fetch of ${PREFIX}main / ${PREFIX}state failed"
cur=$(git symbolic-ref --short -q HEAD || echo DETACHED)
if [ "$cur" != "fed-$NAME" ]; then
  if git rev-parse -q --verify "refs/heads/fed-$NAME" >/dev/null; then
    git checkout -q "fed-$NAME"
  else
    git checkout -q -b "fed-$NAME" refs/fed/main 2>/dev/null || git checkout -q -b "fed-$NAME"
  fi
fi
mkdir -p runs
echo "setup: ok  branch=$(git symbolic-ref --short HEAD) head=$(git rev-parse --short HEAD) prefix=$PREFIX"
echo "setup: SWARM=$SKILL_SCRIPTS/swarm.py claude=$(command -v claude || echo MISSING) fanout=$([ -f "$FANOUT" ] && echo ok || echo MISSING)"
