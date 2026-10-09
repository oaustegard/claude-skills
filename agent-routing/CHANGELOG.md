# agent-routing - Changelog

All notable changes to the `agent-routing` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.5.0] - 2026-10-09

### Other

- agent-routing 2.5.0: SWE-bench Verified retry-vs-escalation ladder

## [2.5.0] - 2026-10-09

### Changed

- Code edits with tests now route `haiku` → `haiku` informed retry → `sonnet` on a second failure. On 295 SWE-bench Verified tasks (`swe-ladder`), Haiku 5.5 resolved 256 at rung 1; on its 39 misses the informed Haiku retry resolved 30 for $1.43 and Sonnet 5.5 escalation 34 for $13.53, with Sonnet's set containing Haiku's. Sonnet moves to the third rung; that order is projected, not measured.
- The informed-versus-blind retry evidence now includes the SWE-bench controls: blind Haiku re-roll 8/39, Sonnet from the issue text 17/39. Neither blind arm solved a task its informed counterpart missed.
- Real repair is recorded as separating the tiers modestly (Sonnet est. 92.5% vs Haiku 86.8%), where seeded repair did not.

### Added

- Per-spawn cost on SWE-bench-sized tasks: $0.024–0.037 for Haiku 5.5, $0.23–0.35 for Sonnet 5.5.
- The caveat that the SWE-bench rung-2 feedback was the hidden test suite, so the informed-retry rows are a ceiling for a real verifier.

## [2.4.0] - 2026-10-07

### Other

- agent-routing 2.4.0: Haiku 5.5 ladder, per-spawn pricing

## [2.4.0] - 2026-10-07

### Changed

- Repriced for the 5.5 generation. Haiku 5.5 is $0.10/$0.50, 20× under Sonnet 5.5 on every token class, so the Haiku 4.5 cost arguments (the verbosity penalty, the failed `haiku → sonnet` precondition) no longer hold, and they are marked as 4.5 data.
- Checkable work now starts on Haiku at any output length. Code edits with tests route `haiku` → `haiku` informed retry, measured 14/14 for $0.12 on the seeded-bug battery, where the Sonnet 5.5 rung 2 rescued the same 3 tasks at 35× the per-spawn cost.
- The judgment row splits on whether the prompt names its deliverable. A goal-shaped prompt, where the work has to be found, is a new escalation trigger to Opus 5.5.

### Added

- Per-spawn pricing for Claude Code subagents. A fresh spawn writes a ~55K-token prefix to cache, which cost $0.17 on Sonnet 5.5 and $0.005–0.011 on Haiku 5.5, and outweighed the output on short tasks.
- Haiku 5.5 effort semantics: it accepts `low` to `max` with a default of `medium`. Whether the Workflow tool reaches it is unmeasured.

## [2.3.0] - 2026-09-29

### Other

- agent-routing 2.3.0: Sonnet 5.5 effort measured

## [2.3.0] - 2026-09-29

### Added

- Sonnet 5.5 effort measured on the seeded-bug battery, two replicates: `low` 10 and
  11 of 14, `medium` 11 and 12, `high` 12 and 12, against Sonnet 5 `low` at 9/14. `low`
  no longer switches thinking off. Sonnet 5.5 @ `high` matched Opus 5.5 @ `high` (24 of
  28 each) at 0.43x the cost per completed task. Opus 5.5 emitted a third of Opus 5's
  output on the same tasks.

## [2.2.0] - 2026-09-29

### Other

- agent-routing 2.2.0: effort channels, cache TTL, Sonnet 5.5 caveat

## [2.2.0] - 2026-09-29

From the 2026-09-28 Claude Code effort experiments
(muninn.austegard.com/blog/effort-levels-in-claude-code-subagents.html) and the Sonnet 5.5
release.

### Added

- Which channel sets whose effort: Workflow `agent({effort})` is the only way a parent sets
  a subagent's effort; Agent and SendMessage have none; a resumed subagent picks up the
  session's `/effort`.
- How to run rung 2 in Claude Code: a fresh Workflow agent one effort step up for
  subagents, a recommended `/effort` change for the main loop.
- The cache TTL, not the effort change, is what misses: subagents cache on the 5-minute
  tier, the parent on the 1-hour tier.

### Changed

- Caching paragraph: an effort change keeps the cache in Claude Code (five resumes across a
  level change all hit), and the API's per-message effort message now covers Opus 5.5 and
  Sonnet 5.5. Replaces "an effort change invalidates the messages cache on every model".
- Haiku's effort column reads n/a: the API rejects `effort` on Haiku 4.5 and Claude Code
  drops it.
- Every Sonnet figure is labelled as Sonnet 5 data pending a re-measure on Sonnet 5.5,
  whose effort levels were recalibrated.

## [2.1.0] - 2026-09-04

### Other

- agent-routing 2.1.0: measured cascade rungs, escalation signal, tier gap (#785)

## [2.1.0] - 2026-09-03

Measured against a 14-repo seeded-bug agentic battery (~120 subagent runs;
`oaustegard/experiments` -> `temporal-routing-headroom`). Nothing was retracted; the
cascade section gained the numbers it was missing.

### Added

- The escalation call belongs to whoever holds the verifier, never the worker. 58 of 58
  graded runs self-reported success; 44 had passed. Every failure claimed to be done.
- Rung 2 is the same model one effort step up; a tier jump is the exception. From an
  identical failed attempt, `sonnet` @ `medium` and `opus` @ `high` rescued the same 4 of
  5 tasks at 11,691 vs 32,504 output tokens (0.31x vs 0.76x always-`opus` composed).
- A cascade can beat the frontier solo arm on correctness: 13/14 vs 10/14.
- Caching in the cascade: caches are model-scoped with no escape hatch, so a tier jump
  discards rung 1's prefix; an `effort` change invalidates the messages cache on every
  model, and the per-message effort hatch is Opus 5 / Fable 5.1 / Mythos 5.1 only.
- Informed retry means the artifacts, not the prior model's narrative: adding rung 1's
  stated diagnosis moved 12/15 to 13/15 on one replicate of one unstable task.
- Concision does not reach small-output work: 2.9% on agentic repair vs 37% on generation.
- Route up for capability, not thoroughness: `opus` @ `high` fell into the same
  stop-early trap as `sonnet` @ `low` on three of four tasks.
- Seeded-bug repair in a small module is measured as not tier-separating across three
  probe shapes.

### Changed

- Cost-model caveat made explicit: every figure prices output tokens only.

## [2.0.0] - 2026-08-18

### Added

- Add/Update skill: agent-routing (#767)