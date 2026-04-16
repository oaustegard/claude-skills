# challenging - Changelog

All notable changes to the `challenging` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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