# challenging - Changelog

All notable changes to the `challenging` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.9.0] - 2026-04-18

### Other

- challenging v0.9.0: prepare_self() + adversary=auto default (#554)

## [0.9.0] - 2026-04-18

### Added
- **`prepare_self()`** — third adversary path. Returns `{system, user, profile, stage, mode: 'self'}` for the caller assistant to inhabit the adversary persona in a dedicated response. Symmetric with `prepare()` (subagent path) but returns raw system+user instead of a Task-tool-formatted prompt, since the caller is running the review inline rather than handing off.
- **`SELF_MODE_PREAMBLE`** — prepended to self-path system prompts. Explicit persona-switch instruction plus framing of the trade-off: self-mode's advantage is retained subject-matter context (catches local-convention mismatches and factual errors the artifact omits); its disadvantage is same-session goodwill (caller may inherit confabulations). Preamble instructs the reviewer to commit to the adversarial lens and reject findings that could have been produced without it. Kin to generative-thinking's inversion move.
- **`adversary='auto'`** resolution. Picks gemini > claude > self based on available credentials. Detection via new `_has_gemini_key()`, `_has_claude_key()`, `_resolve_auto_adversary()` helpers. Claude Code callers continue to use `prepare()` + Task tool explicitly; auto is for claude.ai / Codex / headless scripts.
- **`adversary='self'` in `challenge()`** raises `ValueError` with a pointer to `prepare_self()` + `parse_response()`. Self-challenge requires the caller assistant to produce the response; a synchronous function cannot do that.

### Changed
- **Default `adversary` flipped from `'gemini'` to `'auto'`** in `challenge()`. Behavior unchanged for callers with Gemini credentials configured (auto resolves to gemini). Callers with only Claude credentials now route there automatically. Callers with no credentials get an actionable error instead of a credential-not-found exception.
- `SKILL.md` reframed around three paths (subagent / external API / self) with explicit trade-off documentation. Honest about when each mode dominates: subagent for Claude Code; external for cross-context structural review; self for subject-aware review when context is load-bearing.
- Error message for unknown adversary values now mentions `auto` and `self` alongside `gemini` and `claude`.

### Rationale
v0.8.2's `LOCAL_CONVENTIONS_GUARDRAIL` addressed the symptom (external adversaries issuing confident-but-wrong findings when generic priors contradict artifact-local conventions). v0.9.0 addresses the dual problem structurally: some reviews genuinely benefit from subject-matter context the external adversary lacks. Self-challenge isn't a strict downgrade from external — it has a different failure-mode profile. Externals catch structural flaws invisible from inside; self catches local-convention mismatches and factual errors from retained context. Making self a first-class path (not a fallback) acknowledges that.

Triggered by a Claude.ai session (2026-04-18) where Gemini review of an EML↔mythology claim correctly killed the core parallel but issued a partially-wrong secondary finding that self-review would have caught — because Gemini couldn't see the referenced codebase's IEEE-754 conventions.

## [0.8.2] - 2026-04-18

### Other

- challenging v0.8.2: add LOCAL_CONVENTIONS_GUARDRAIL (#553)

## [0.8.2] - 2026-04-18

### Added
- **`LOCAL_CONVENTIONS_GUARDRAIL`** — new constant appended to every system prompt (alongside `KNOWLEDGE_CUTOFF_GUARDRAIL`). Instructs the adversary to classify findings as `unverifiable` when the critique depends on generic domain priors that may conflict with artifact-local conventions, and to state the assumption in `reasoning`. Uses `ln(0) = -∞` (domain error under pure math vs. intentional IEEE-754 signed-infinity feature) as the anchoring example.
- Anti-rationalization row in `references/analysis.md`, `references/code.md`, and `references/recommendation.md`: "I know this field / language / domain" — prompts the adversary to check whether generic knowledge contradicts local conventions before flagging.

### Rationale
Observed failure mode (2026-04-18): Gemini review of an EML↔mythology claim correctly killed the core parallel (findings #1 and #3) but issued a partially-wrong finding #2 ("`ln` is a domain error on `y ≤ 0`") because it applied generic real-analysis priors without knowing the referenced codebase's CLAUDE.md invariant that `ln(0) = -∞` is intentional. The existing `KNOWLEDGE_CUTOFF_GUARDRAIL` handles "I don't recognize this API"; the new guardrail handles "I think I recognize this term but my default may disagree with local convention." Verdict was unaffected (the bad finding wasn't load-bearing), but the review was messier than it needed to be.

## [0.8.1] - 2026-04-17

### Other

- challenging v0.8.1: add README

## [0.8.1] - 2026-04-17

### Added
- `README.md` — quickstart overview with two-path table (subagent / API), profile table, verdicts, provenance (VDD, Grainulation, Tim Kellogg's 5 Whys), and complements (generative-thinking, convening-experts, tiling-tree). Points at `SKILL.md` for full protocol.

## [0.8.0] - 2026-04-17

### Other

- challenging v0.8.0: unify drill into challenge (sequential-deepen profile) (#547)

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