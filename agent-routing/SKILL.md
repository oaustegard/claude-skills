---
name: agent-routing
description: Decide which model (Haiku/Sonnet/Opus) and effort level each subagent gets, when to cascade cheap-first behind a verifier, and how to run improvement loops safely (evaluator-as-selector, stop on regression). Use when spawning subagents via the Agent or Workflow tools, when fanning out more than a handful of agents, or when the user asks which model or effort a task should route to. Grounded in measured calibration data (references/calibration-2026-07-15.md), not vibes.
compatibility: Designed for Claude Code / Claude Code on the Web — assumes an orchestrator with Agent/Workflow subagent tools exposing per-call model and effort options. Not applicable to claude.ai chat use.
metadata:
  author: Oskar Austegard and Claude (Fable 5)
  version: "1.1.0"
---

# Agent Routing — model + effort selection for subagents

Before spawning any subagent, answer one question: **is the task mechanically
checkable, or does it require judgment?** Checkable → Haiku at `effort: 'low'`
behind a verifier. Judgment → up-tier. The routing table refines this split; the
rest of the skill governs cascades and loops.

**Do not up-tier checkable work "to be safe."** Measured Haiku 4.5 failure on
every checkable task family tested is ≈0, at `effort: 'low'`, with
chain-of-thought suppressed (evidence: references/calibration-2026-07-15.md).
The burden of proof is on routing *up*: reflexive up-tiering costs 3–5× for
safety that the data says is imaginary. Spend effort, not tier, and only where
reasoning depth demonstrably falls short.

To turn a judgment-shaped task INTO a Haiku-executable one (explicit procedures,
n-shot examples), use the sibling `down-skilling` skill. This skill decides the
routing; that one engineers the prompt.

## Routing table

| Task shape | Model | Effort | Verify with |
|---|---|---|---|
| Extraction, classification, format transforms, schema-bound output | `haiku` | `low` | schema / spot-check |
| Closed-form computation, state tracking, multi-hop lookup | `haiku` | `low` | deterministic check |
| Constraint-bound generation (exact counts, required tokens, lipograms) | `haiku` | `low` | mechanical checker |
| Bulk scans/greps, per-file summaries, fan-out reads | `haiku` | `low` | sample audit |
| Code edits with tests available | `haiku` first | `low`–`medium` | run the tests |
| Judging / scoring another model's output | `sonnet`+ | `medium` | — (judge ≠ worker) |
| Ambiguity resolution, novel synthesis, architecture, taste | `sonnet`/`opus` | `high` | human or panel |
| Long-horizon multi-step agentic work, cross-file reasoning | `sonnet`/`opus` | `high`/`xhigh` | milestone checks |

## Cascade (default composition)

When a near-free verifier exists, compose instead of choosing a tier up front:

```
result = haiku(task, effort=low)
if verify(result) fails:  result = sonnet(task)      # escalate on evidence
if verify(result) fails:  result = opus(task)         # rare
```

Input-cost ratio is Haiku 1× · Sonnet 3× · Opus 5×. Expected cascade cost ≈
`c_haiku + p_fail × c_sonnet`, so the cascade beats Sonnet-direct while Haiku's
failure rate stays below ~2/3, and beats Opus-direct below ~4/5 (derivation in
the reference). Every checkable task measured has Haiku failure ≈0, so the
cascade is nearly pure savings.

**No verifier ⇒ no cascade.** Route by the table instead, because silent Haiku
errors compound downstream with nothing to catch them.

## Loop discipline

Never blind-loop. Re-applying the same prompt to a model's own output is the
identity at best (an LLM call already unrolls its reasoning depth internally) and
regression-then-freeze at worst — in calibration, a re-looped haiku broke its
own middle line on iteration 2 and froze on the broken text for every iteration
after. Loops only pay when an out-of-band evaluator scores each iteration.

1. **Loop only with an out-of-band evaluator** — ground truth, mechanical
   checker, or an up-tier judge scoring every iteration.
2. **Select, don't trust the last:** `final = argmax_r eval(answer_r)`. Never
   ship iteration N just because it's newest.
3. **Stop on first regression.** If `eval(r) < eval(r-1)`, stop — loops froze on
   degraded output rather than recovering, so early-stop risk beats drift risk.
4. **Loop for diversity, not depth.** Vary the prompt/angle per iteration to
   explore; identical re-application converges instantly.
5. **"Improve this" with no headroom is the danger zone.** It pressures the model
   to change something; without a selector, that change ships.

## Judge rules

- Judge model ≠ worker model; judge at least one tier up (Sonnet judging Haiku,
  Opus judging Sonnet). Same-model self-assessment is untested — don't assume it.
- Prefer mechanical checkers over judges wherever a spec can be executed (word
  counts, schemas, tests, regex): free, deterministic, zero judge tokens.
- Judges are for rubric quality, not arithmetic — don't ask Sonnet to verify a
  sum a Python one-liner can check.

## Escalation triggers (route up despite the table)

- The verifier fails twice at the same tier.
- The task requires weighing trade-offs with no checkable ground truth.
- Output will be shipped verbatim to a human without review.
- The subagent must plan its own multi-step tool strategy over many turns.

## Recalibrate when

- **The task is off the measured battery.** No deterministic task has made Haiku
  fail yet, so the cliff is past what's been probed — test harder instances
  before trusting Haiku on a genuinely novel task family.
- **The work is multi-turn agentic tool use.** That was not calibrated; treat the
  table's up-tier rows there as prior, not measurement.
- **A model rev bumps.** Re-run the battery (generators + scorer described in
  references/calibration-2026-07-15.md) before trusting the table.
