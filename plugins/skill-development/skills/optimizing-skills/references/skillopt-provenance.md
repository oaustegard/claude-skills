# Provenance & the Agent-tool recipe

This skill is distilled from **SkillOpt** (microsoft/SkillOpt,
arXiv:2605.23904, MIT). SkillOpt trains a skill document as the external state
of a frozen agent: a separate optimizer LLM turns scored rollouts into bounded
add/delete/replace edits, accepted only when they strictly improve a held-out
score. We keep the discipline and drop the training harness — no Azure, no
rollout infra, no weight-training analogy required.

## Mapping: SkillOpt mechanism → this skill

| SkillOpt | Here |
|---|---|
| Validation gate (`gate.py`, strict `>`, ties rejected) | "The gate" — accept only if candidate strictly beats `best` |
| Two-tier `current`/`best` skill state | `candidate` / `best` |
| Textual learning rate = integer cap on edits/step, cosine-annealed | "Bounded edits", ~4 default, fewer as it matures |
| Failure-minibatch + success-minibatch reflection, failures win merge | "Reflect: failures first, then successes" |
| Rank-and-select top-L by impact (`clip.py`, `ranking.md`) | "Rank when over budget" |
| Protected slow-update region (`<!-- SLOW_UPDATE_START/END -->`) | "Protect the hard-won core" + longitudinal review |
| Optimizer-side meta-skill (`meta_skill.md`) | "Carry memory across revisions" via `remember()`/`recall()` |
| Literal `str.replace(target, content, 1)` edits | "Edit mechanics" — exact-match `Edit` tool ops |

## Recipe: dispatch scoring/reflection to the Agent tool

The one piece that needs compute is scoring the check set. There is no
ANTHROPIC_API_KEY in this environment — route through the **Agent tool**, not a
standalone SDK call.

1. **Score a version.** For each check task, spawn `subagent_type=general-purpose`
   (model `sonnet` for cheap, `opus` for hard checks) with the skill version
   pasted into the prompt and the task. Collect hard pass/fail. Run `best` and
   `candidate` the same way for a fair comparison. Parallelize independent tasks
   in one message.
2. **Reflect (optional, for large failure sets).** Hand the failing transcripts
   to an optimizer subagent using the prompt below; it returns bounded edits.
   You still apply them with the `Edit` tool and re-score through the gate.

### Adapted failure-reflection prompt (optimizer subagent)

```
You are a failure-analysis agent for an existing skill document.
Given the current skill and MULTIPLE failed task transcripts, identify the
most important COMMON failure pattern across them (not one-off edge cases) and
propose AT MOST <budget> generalizable edits. Do not hardcode task-specific
values. Do not duplicate content already in the skill — patch gaps only.
Return JSON: {"failure_summary": [...], "edits": [{"op": "append|insert_after|
replace|delete", "target": "<exact text, if needed>", "content": "<markdown>"}]}
```

### Adapted ranking prompt (when edits exceed budget)

```
Rank the proposed edits and select the top <budget>, by: (1) systematic impact
on recurring failures, (2) complementarity / fills a gap, (3) generality as a
principle, (4) actionability. Return {"selected_indices": [...]} in priority order.
```

Keep the optimizer subagent separate from the target subagent — the model that
*proposes* edits should not be the one being measured by them.
