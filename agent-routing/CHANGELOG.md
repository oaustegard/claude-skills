# agent-routing - Changelog

All notable changes to the `agent-routing` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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