# delegating-with-context - Changelog

## 0.1.0 — 2026-09-23
- New skill. Write only the task when delegating; `scripts/context_hook.py`
  (PreToolUse on Agent) pages the parent transcript through Jev and appends the
  chunks the task needs. `scripts/preview.py` shows the selection before the
  prompt is written. Measured in `oaustegard/experiments/subagent-context-filter`.
