#!/usr/bin/env bash
# Probe (2026-09-19): does a plugin SessionStart hook fire in Cowork?
# Writes a sentinel and nothing else. Remove once the answer is known.
set -u
out=/home/claude/.muninn-hook-fired
{
  echo "fired_at=$(date -u +%FT%TZ)"
  echo "plugin_root=${CLAUDE_PLUGIN_ROOT:-unset}"
  echo "project_dir=${CLAUDE_PROJECT_DIR:-unset}"
  echo "env_file=${CLAUDE_ENV_FILE:-unset}"
  echo "remote=${CLAUDE_CODE_REMOTE:-unset}"
  echo "entrypoint=${CLAUDE_CODE_ENTRYPOINT:-unset}"
  echo "cwd=$(pwd)"
  echo "stdin=$(cat 2>/dev/null | head -c 400)"
} > "$out" 2>&1 || true
[ -n "${CLAUDE_ENV_FILE:-}" ] && echo 'export MUNINN_HOOK_FIRED=1' >> "$CLAUDE_ENV_FILE"
exit 0
