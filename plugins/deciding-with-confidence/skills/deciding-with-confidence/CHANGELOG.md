# deciding-with-confidence - Changelog

## 0.4.0 - 2026-11-11

### Added
- System One requests: a body written for TypeSafe's `POST /v1/systemone`
  (`state` plus `noul` / `choice` / `score` questions keyed by id, with
  `criteria`) is accepted as it is, and the answer comes back in System One's
  shape (`probabilities` keyed by option, `label`, `confidence`,
  `probability_true` or `score`). `run`, `batch`, `emit`, `aggregate` and
  `eval` all take it.
- A predicate's `criteria` (`{"true": ..., "false": ...}`) replace the default
  option descriptions.
- `diagnostics.cues`: each sample's quote of the evidence it decided on.

## 0.3.0 - 2026-11-11

### Changed
- Every sample now quotes the words of the evidence that decide each
  question (`cue`) before its probabilities. On the held-out half of three
  labelled sets, one sample went from 0.808 / 0.931 / 0.857 to
  0.827 / 0.969 / 0.870 (short items / whole articles / sections) and the
  stack from 0.769 / 0.924 / 0.870 to 0.865 / 0.962 / 0.906.
- `assets/calibration.json` is refitted for the cue prompt on 1,798 labelled
  answers. It now covers predicates and scores as well as choices, and has
  a separate `pooled` set of temperatures for k > 1.

### Added
- `calibrate` fits single-sample temperatures from each request's first
  sample and pooled ones from the pools of a `--stack` eval; `decide` applies
  the pooled set when more than one sample answered.

## 0.2.0 - 2026-11-10

### Changed
- The default is one sample at low effort (was three samples at the CLI's
  default effort). Measured on three labelled sets it costs about a quarter as
  much and scores 0.885 / 0.908 / 0.846 against 0.846 / 0.944 / 0.886.
- The `cli` transport sends the prompt on stdin and passes `--effort`.

### Added
- `--stack`: three samples, one under each of the `plain`, `literal` and
  `sceptic` angles, pooled. Its agreement signal separates right answers
  (0.91 to 0.96 when unanimous) from wrong ones (0.39 to 0.66 when split).
  `--angles` and a request's `angles` take custom instruction text.
- `input_file`: evidence read from a file by `run` and `batch`, and passed to
  the subagent as a path by `emit`.
- `input_transcript`: the session's own conversation as evidence, read from
  Claude Code's transcript file, clipped and redacted.
- `batch`: a JSONL of requests answered in parallel, resumable.
- `eval` accepts items labelled for only some of their questions.

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

## [0.4.0] - 2026-11-11

### Other

- deciding-with-confidence 0.4.0: System One requests, predicate criteria, cues returned

## [0.3.0] - 2026-11-11

### Other

- deciding-with-confidence 0.3.0: cue prompt, refitted single and pooled temperatures

## [0.2.0] - 2026-11-11

### Other

- deciding-with-confidence 0.2.0: measured numbers for the new default and the stack
- deciding-with-confidence: the conversation itself as evidence (input_transcript)
- deciding-with-confidence: one low-effort sample by default, angle stack, file inputs, batch

## [0.1.1] - 2026-10-09

### Other

- deciding-with-confidence 0.1.1: correct the miss-confidence and escalation claims