# deciding-with-confidence - Changelog

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
