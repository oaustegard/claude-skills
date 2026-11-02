# delegating-with-context - Changelog

## 0.2.3 — 2026-11-02
- Fix: `jevfilter._global_state` looped forever on sessions of ~500+ chunks.
  `clip(x, 20)` returns 25 characters, so the exit test (every index entry
  <= 24 chars) never passed once the one-line session index outgrew its 5k-token
  share. The hook then hit its 120 s timeout and the subagent got no context.
  The loop now stops when a pass changes nothing, then thins the index and
  drops the oldest user messages until the global state fits. Found running the
  filter on 498-581-chunk sessions (`oaustegard/experiments`
  `subagent-context-filter`).

## 0.2.1 — 2026-10-02
- "When NOT to use": a relay of fresh subagents that must carry a running
  result needs a model-maintained state file with invariant checks, not
  passed chunks. Evidence line for verbatim extraction over model copying.
  Both from `oaustegard/experiments/clm-relay-needles`.

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

## [0.2.3] - 2026-11-02

### Other

- delegating-with-context 0.2.3: fix infinite loop on 500+ chunk sessions

## [0.2.2] - 2026-10-11

### Other

- orchestrating-agents renamed orchestrating-chat-agents; old name deprecated

## [0.2.1] - 2026-10-02

### Other

- delegating-with-context 0.2.1: running-result relays need gated state, not chunks

## [0.1.0] - 2026-09-23

### Other

- delegating-with-context 0.1.0: write only the task, a hook passes the context