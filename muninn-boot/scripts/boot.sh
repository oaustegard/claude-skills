#!/bin/bash
# Muninn boot — clone muninn-utilities and put it on the Python path. That is all.
#
# The boot PAYLOAD (identity, ops, recent memories) comes from the Muninn MCP
# connector's `boot` tool, and memory reads and writes go through its `recall`,
# `remember`, `forget` and `muninn_config` tools. None of that needs a Turso
# credential in the container, so this script sources no Turso.env. Direction:
# memory ce3b8b75; what shipped: fd238c22; the plan this follows: 69f3301c.
#
# Skills are not sideloaded either: marketplace sync places oaustegard/claude-skills
# in the session on its own (/root/.claude/skills/synced/<id>/ in Cowork,
# /mnt/skills/user on Claude.ai).
#
# GitHub.env is still sourced when present, only until GitHub write tools exist
# on the worker (69f3301c step 4). Then that block goes and this reads no env.
#
# Transport: `git clone --depth 1` of the public repo (~1s, measured 2026-09-19
# in Cowork). Where the session's git proxy refuses github.com, the codeload
# tarball is the fallback. MUNINN_UTILS_REF accepts a branch, tag, or full SHA.
set -e
MUNINN_UTILS_REF=${MUNINN_UTILS_REF:-main}
REPO=oaustegard/muninn-utilities
DEST=/home/claude/muninn-utilities
PROJECT_DIR=${MUNINN_PROJECT_DIR:-/mnt/project}

# Warm-container fast path. The sentinel's lifetime is the container's; a
# recycled container lacks it and clones fresh. rm it to re-pull main.
SENTINEL=/home/claude/.muninn-booted
if [ -f "$SENTINEL" ] && [ -d "$DEST/muninn_utils" ]; then
  echo "warm boot: muninn-utilities already fetched this container ($(cat "$SENTINEL"))."
  echo "  rm $SENTINEL to re-pull $MUNINN_UTILS_REF."
  exit 0
fi

# ── GitHub.env (transitional) ────────────────────────────────────────────────
# The container presets GH_TOKEN=proxy-injected, a placeholder that is truthy
# but useless to GitHub — sourcing must OVERWRITE it, never setdefault.
set -a
. "$PROJECT_DIR/GitHub.env" 2>/dev/null
set +a
if [ "${GH_TOKEN:-}" = "proxy-injected" ]; then
  echo "note: GH_TOKEN is the container placeholder ($PROJECT_DIR/GitHub.env absent);" \
       "GitHub API calls from this container will 401. Memory tools are unaffected."
fi

# ── fetch ────────────────────────────────────────────────────────────────────
clone() {
  rm -rf "$DEST"
  case "$MUNINN_UTILS_REF" in
    [0-9a-f]??????????????????????????????????????? )   # 40-hex SHA
      git clone --depth 1 -q "https://github.com/$REPO" "$DEST" \
        && git -C "$DEST" fetch --depth 1 -q origin "$MUNINN_UTILS_REF" \
        && git -C "$DEST" checkout -q FETCH_HEAD ;;
    *)
      git clone --depth 1 -q --branch "$MUNINN_UTILS_REF" "https://github.com/$REPO" "$DEST" ;;
  esac
}

tarball() {
  local tgz=/tmp/muninn-utilities.tar.gz
  curl -sL "https://codeload.github.com/$REPO/tar.gz/$MUNINN_UTILS_REF" -o "$tgz" || return 1
  # The egress interception returns JSON with a 200; check the gzip magic.
  [ -s "$tgz" ] && [ "$(head -c2 "$tgz" | od -An -tx1 | tr -d ' \n')" = "1f8b" ] || return 1
  rm -rf "$DEST"; mkdir -p "$DEST"
  tar -xzf "$tgz" -C "$DEST" --strip-components=1
}

if clone 2>/dev/null; then
  HOW="git clone $(git -C "$DEST" rev-parse --short HEAD)"
elif tarball; then
  HOW="codeload tarball (git refused; no commit sha available)"
else
  echo "ERROR: could not fetch $REPO@$MUNINN_UTILS_REF by git clone or codeload tarball." >&2
  exit 1
fi

# ── python path ──────────────────────────────────────────────────────────────
# Resolve site-packages at runtime, preferring a writable entry that is ON
# sys.path: a .pth written to a directory off sys.path succeeds and is inert.
PTH=$(python3 - <<'PY'
import site, sys, os
cands = [p for p in sys.path if p.endswith(('site-packages', 'dist-packages'))]
for c in (site.getusersitepackages(),) if hasattr(site, 'getusersitepackages') else ():
    if c not in cands:
        cands.insert(0, c)
writable = [c for c in cands if os.path.isdir(c) and os.access(c, os.W_OK)]
target = (writable or cands)[0]
os.makedirs(target, exist_ok=True)
print(os.path.join(target, 'muninn-remembering.pth'))
PY
)
HOMEDIR=$(python3 -c 'import os; print(os.path.expanduser("~"))')
printf '%s\n' "$DEST/remembering" "$DEST" "$HOMEDIR" > "$PTH"
# Skill scripts, wherever the session put the skills.
for d in /mnt/skills/user/*/scripts/ /root/.claude/skills/synced/*/*/scripts/; do
  ls "$d"*.py >/dev/null 2>&1 && echo "$d" >> "$PTH"
done

date -u '+%Y-%m-%dT%H:%MZ' > "$SENTINEL"   # last, only on success
echo "── muninn-utilities ready ──────────────────────────────────────"
echo "  fetched:  $HOW -> $DEST"
echo "  pth:      $PTH ($(wc -l < "$PTH") entries)"
echo "  payload:  call the Muninn MCP \`boot\` tool (not run here; no Turso credential in the container)"
