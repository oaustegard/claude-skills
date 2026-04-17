# challenging - Changelog

All notable changes to the `challenging` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.8.0] - 2026-04-17

### Changed
- **Subagent path is now the primary adversary in Claude Code.** `prepare()` + Task tool + `parse_response()` is the documented default; `challenge()` with `adversary='claude'` is reserved for claude.ai (which can't spawn subagents). Gemini remains the cross-model option.
- **Drill is now a `challenge` profile, not a separate function.** One unified surface (`prepare` / `parse_response` / `challenge`) with two iteration strategies: review profiles run *parallel replay* (current blocking mode), drill runs *sequential deepen* (one why-level per pass, conditioned on the chain so far, until bedrock or max depth) followed by a synthesis pass.
- `prepare()` now dispatches on profile and accepts `finding`, `chain`, `synthesize` for drill. Returns `stage` ('review' | 'deepen' | 'synthesize') and `depth` (drill only).
- `parse_response()` auto-detects response shape (review / deepen / synthesize).
- `challenge()` with `profile='drill'` runs the full deepen→synthesize loop internally. `max_iterations` defaults to 3 for review, 5 for drill.
- `references/drill.md` system prompt split into `## System Prompt: Deepen` (one level per pass) and `## System Prompt: Synthesize` (root-cause extraction from the completed chain). The single-shot "whole tree in one call" prompt that shortcut into renames is gone.
- CLI accepts `--profile=drill` with `--finding=<inline or @path>` and `--max-iterations`.

### Removed
- `prepare_drill()` / `parse_drill_response()` — folded into `prepare()` / `parse_response()`.
- Standalone `drill()` function — use `challenge(..., profile='drill', finding=...)`.

### Migration
```python
# Before
from challenger import prepare_drill, parse_drill_response, drill
job = prepare_drill(artifact, finding, context)
diagnosis = parse_drill_response(subagent_text)
# — or —
diagnosis = drill(artifact, finding, context)

# After
from challenger import prepare, parse_response, challenge
chain = []
for depth in range(1, 6):
    job = prepare(artifact, 'drill', context=context, finding=finding, chain=chain)
    step = parse_response(subagent_text)     # {why, because, bedrock, reasoning}
    chain.append({'why': step['why'], 'because': step['because']})
    if step.get('bedrock'): break
job = prepare(artifact, 'drill', context=context, finding=finding, chain=chain, synthesize=True)
diagnosis = parse_response(subagent_text)    # {chain, root_causes, direction, summary}
# — or, API path —
diagnosis = challenge(artifact, 'drill', context=context, finding=finding)
```

## [0.7.0] - 2026-04-16

### Other

- Add drill() — 5 Whys follow-up pass (#544)

## [0.7.0] - 2026-04-16

### Added
- `drill()` — 5 Whys follow-up pass for a single finding. Returns chain, root_causes, direction, summary. Adapted from Tim Kellogg's open-strix pattern (timkellogg.me/blog/2026/04/14/forgetting).
- `references/drill.md` — drill persona, anti-pattern table (surface-level "becauses" to reject), system prompt.

### Changed
- Internal: `_gemini_raw` / `_claude_raw` helpers extracted from `_invoke_gemini` / `_invoke_claude` so `challenge` and `drill` share invocation machinery. No behavior change for existing callers.
- `_load_system_prompt` refactored around shared `_extract_system_prompt` helper for reuse by drill loader.

## [0.6.0] - 2026-04-11

### Other

- challenging v0.6.0: self-review fixes (#540)

## [0.6.0] - 2026-04-11

### Security
- Auto-pip-install now gated to sandboxed containers only (CWE-94 mitigation for non-container environments)
- Env file parser now strips surrounding quotes from values

### Fixed
- Claude max_tokens increased 2048→32768 (self-review truncated its own output at 2048)
- Claude response parsing uses defensive `.get()` with diagnostic errors instead of bare indexing
- Retry logic now covers `JSONDecodeError`, `ReadTimeout`, `KeyError`, `IndexError` — proxy HTML responses no longer crash

### Changed
- **Confabulation heuristic rewritten**: no longer uses adversary's self-assigned severity labels (untrusted model output as security decision). Now tracks cross-iteration finding novelty — real issues persist across passes, confabulated ones don't.
- `unverifiable` severity added to all profiles — adversary uses this when it doesn't recognize an API/pattern rather than flagging as incorrect
- Knowledge cutoff guardrail appended to all system prompts — instructs adversary to classify unfamiliar patterns as unverifiable, not wrong
- Blocking mode filters `unverifiable` findings from actionable count (they surface for awareness but don't block SHIP)

## [0.5.0] - 2026-04-11

### Other

- challenging v0.5.0: prompt injection mitigation, credential path hardening, input size guard, retry logic, robust parsing

## [0.5.0] - 2026-04-11

### Security
- Prompt injection mitigation: artifact/context wrapped in XML tags with trust boundary instruction in all profile system prompts
- Removed `os.getcwd()` from credential search path — prevents rogue env files from redirecting API calls

### Added
- Input size guard: rejects artifacts > 500k chars before sending to API
- Retry with exponential backoff on transient API errors (429, 5xx, connection errors)

### Fixed
- System prompt extraction uses regex instead of fragile string slicing — handles code fences with language tags

## [0.4.0] - 2026-04-11

### Other

- challenging v0.4.0: fix Gemini model, token budget, defensive parsing

## [0.4.0] - 2026-04-10

### Fixed

- Gemini model upgraded from 2.5-pro to 3.1-pro-preview
- maxOutputTokens bumped 2048→16384 (thinking models exhaust budget on internal reasoning)
- Defensive response parsing in _invoke_gemini — handles missing `parts` key instead of crashing with KeyError
- Input validation for mode, adversary, and max_iterations parameters

## [0.3.0] - 2026-04-10

### Other

- challenging: generalize description, remove skill dependencies

## [0.2.0] - 2026-04-10

### Other

- challenging: proper progressive disclosure — one file per profile

## [0.1.0] - 2026-04-10

### Other

- Add challenging skill — adversarial review for deliverables