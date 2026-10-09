# deciding-with-confidence - Changelog

## 0.1.1 - 2026-10-09

### Fixed
- SKILL.md and references/method.md overstated how differently the two models
  fail. Measured with the shipped calibration, 9 of decider's 16 misses and 6
  of Jev's 11 had a top probability under 0.7; the claim that Jev's misses sat
  at 0.91-0.97 held for 4 of its 11. The escalation figures now use the
  calibrated pool and the combined rule (under 0.7 or split samples: 23 of 104
  escalated, 6 left wrong) and state that they assume escalated items are
  resolved correctly. method.md adds accuracy by question type: the whole
  gap is on eight-way intent questions.

## 0.1.0 - 2026-10-09

### Added
- `scripts/decide.py`: `run`, `emit`, `aggregate`, `eval` and `calibrate` over
  OpenAI Decisions API requests (`predicate`, `choice`, `score`), answered by
  Claude Haiku 5.5. k permuted samples are pooled and temperature-scaled;
  `confidence` is (k*p_max - 1)/(k - 1), which matches the published OpenAI
  and Strands Decider examples.
- Transports: `api` (Anthropic SDK; thinking disabled, effort low), `cli`
  (`claude -p` with no tools, settings, MCP or session file), `bedrock`
  (AnthropicBedrockMantle), and subagent prompts through `emit` / `aggregate`.
  The `cli` path was measured live; `api` was tested against a local stand-in
  server only.
- `agents/decider.md`: a subagent pinned to `claude-haiku-5-5` with the
  decision prompt inline. The registry now builds a standalone plugin for any
  skill that ships `agents/*.md`, as it already did for hooks, so installing
  the `deciding-with-confidence` plugin brings the agent and the skill together.
- `assets/`: the system prompt, a 104-item labelled eval, and a choice
  calibration (T = 0.62) fitted on it.
- Ported from `oaustegard/claude-workspace` `scripts/decide.py`, without its
  Jev comparison backend.

## [0.1.1] - 2026-10-09

### Other

- deciding-with-confidence 0.1.1: correct the miss-confidence and escalation claims
