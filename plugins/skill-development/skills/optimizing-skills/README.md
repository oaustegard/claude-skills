# optimizing-skills

Disciplined, validation-gated revision of an existing skill so each edit is a measured improvement rather than a guess. Use when editing, revising, or tuning a skill that already exists and there is evidence it underperforms (observed failures, drift, complaints) — invoke by name, or have versioning-skills / creating-skill defer to it before applying edits. Not for authoring a brand-new skill from scratch (use creating-skill) or one-off prose.

Distilled from [SkillOpt](https://arxiv.org/abs/2605.23904) (microsoft/SkillOpt): a held-out check set, a two-tier `best`/`candidate` validation gate (ship only on a strict improvement), bounded edits, failure-first reflection, impact ranking, a protected core, and `remember()`-backed cross-revision memory — the discipline kept, the training harness dropped.
