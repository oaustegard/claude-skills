---
name: optimizing-skills
description: Disciplined, validation-gated revision of an EXISTING skill so each edit is a measured improvement rather than a guess. Use when editing, revising, or tuning a skill that already exists and there is evidence it underperforms (observed failures, drift, complaints) — invoke by name, or have versioning-skills / creating-skill defer to it before applying edits. Not for authoring a brand-new skill from scratch (use creating-skill) or one-off prose.
metadata:
  version: 0.1.0
---

# Optimizing Skills

Treat the skill document as the parameter under optimization: change it only
when the change **demonstrably beats the version you already ship**. This is
the discipline distilled from SkillOpt (microsoft/SkillOpt, arXiv:2605.23904) —
its training apparatus dropped, its reproducibility discipline kept. The point
is to stop editing skills on intuition and start editing them on evidence.

## Core principle

A skill edit is only worth shipping if it strictly improves measured behavior
on a held-out check. Most edits that *feel* like improvements don't move the
needle, and some quietly regress. The gate below is what separates a real
improvement from a confident guess.

## The gate — run it every revision

1. **Assemble a held-out check set.** 3–8 representative tasks/prompts the skill
   should handle well, and it **must include the failure(s) that prompted this
   revision**. Keep the set fixed across the revision so before/after scores are
   comparable.
2. **Hold two versions.** `best` = what you currently ship (never let it
   silently degrade). `candidate` = `best` + your proposed edits.
3. **Score both on the check set.** "Run" here = dispatch each check task to the
   **Agent tool** (`subagent_type=general-purpose`) with the skill version in
   context, or evaluate by hand for small sets. Score hard pass/fail per task.
4. **Accept only if `candidate` strictly beats `best`** (more tasks pass). Ties
   → reject, keep `best`. An edit that doesn't move the needle does not ship.

This two-tier `best`/`candidate` split is the heart of it: a working revision
can explore, but the shipped skill only ever ratchets upward.

## Bounded edits (the "textual learning rate")

Cap edits per revision — **default ~4** distinct add/replace/delete operations,
fewer as the skill matures. Large speculative rewrites drift and destroy your
ability to attribute a regression to a cause. If a revision wants more edits
than the budget, rank and keep the top ones (below) and let the rest wait.

## Reflect: failures first, then successes

Separate the evidence before proposing edits:

- **Failure reflection.** Across the failing cases, find the *common,
  systematic* pattern — not a one-off edge case. Propose edits that fix the
  pattern. **Failures take priority** in any merge.
- **Success reflection.** Across cases that already work, find generalizable
  patterns worth encoding so they survive future edits. Reinforce; don't
  duplicate.

For both: edits must **generalize** (never hardcode task-specific values), and
must **not duplicate** content already in the skill — patch genuine gaps only.

## Rank when over budget

When candidate edits exceed the budget, keep them in this priority order:

1. **Systematic impact** — fixes a recurring failure across many cases, not one.
2. **Complementarity** — fills a real gap rather than restating existing content.
3. **Generality** — phrased as a durable principle, not tied to one task/entity.
4. **Actionability** — concrete, followable guidance over vague advice.

Drop the rest. They can return next revision if still warranted.

## Protect the hard-won core

If a skill has a battle-tested core that routine edits keep eroding, fence it
off and treat it as off-limits to fast edits. Revisit it only on a **deliberate
longitudinal review**: compare the *same* check tasks across several versions to
catch slow drift and regressions that single-edit review misses. (SkillOpt
fences this region with HTML-comment markers and only rewrites it at epoch
boundaries — the same idea, manual cadence.)

## Carry memory across revisions

After a revision, record what you learned about editing **this** skill — which
kinds of edits helped, which were brittle, redundant, or harmful — via
`remember()` tagged with the skill name. Before the next revision, `recall()`
it. This is the compounding part: each revision starts smarter than the last,
the way SkillOpt's optimizer-side meta-skill conditions its future edits.

## Edit mechanics

Edits are literal string operations (the `Edit` tool): the target text must
match **exactly** or the edit is a silent no-op. Keep targets unique and
verbatim. Prefer append / insert-after-heading / replace-exact / delete-exact,
and verify each edit landed before scoring.

## When NOT to use this

- Authoring a brand-new skill from scratch → **creating-skill**.
- Tracking/rolling back versions during development → **versioning-skills**.
- One-off prose with no reuse → just write it.

## Checklist

- [ ] Held-out check set assembled (includes the triggering failure), fixed for the revision
- [ ] Edits bounded (~4 max), each generalizable and non-duplicative
- [ ] Failure patterns addressed before success reinforcement
- [ ] Candidate scored against `best` on the check set; shipped only if strictly better
- [ ] Hard-won core left untouched unless doing a deliberate longitudinal review
- [ ] Lesson about editing this skill recorded via `remember()`

For the deeper "dispatch reflection/scoring to the Agent tool" recipe and the
adapted reflection/ranking prompt templates, see
[`references/skillopt-provenance.md`](references/skillopt-provenance.md).
