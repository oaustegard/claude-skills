# delegating-with-context - Changelog

## 0.2.0 — 2026-09-23
- Covers `create_session`: the hook matches `mcp__*__create_session` and
  labels the appended block as reference data from the parent session and
  repeats the task after it (two probes stalled without that; the third
  answered). `updatedInput` on an MCP
  tool verified with a stub MCP server and on the real remote server.
- Ships as its own plugin (`hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}` paths);
  `registry/generate.py` now builds a standalone plugin for any skill with hooks.

## 0.1.0 — 2026-09-23
- New skill. Write only the task when delegating; `scripts/context_hook.py`
  (PreToolUse on Agent) pages the parent transcript through Jev and appends the
  chunks the task needs. `scripts/preview.py` shows the selection before the
  prompt is written. Measured in `oaustegard/experiments/subagent-context-filter`.

## [0.1.0] - 2026-09-23

### Other

- delegating-with-context 0.1.0: write only the task, a hook passes the context
