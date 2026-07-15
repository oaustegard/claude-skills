---
name: agent-routing
description: Decide which model (Haiku/Sonnet/Opus) and effort level each subagent gets, when to cascade cheap-first behind a verifier, and how to run improvement loops safely (evaluator-as-selector, stop on regression). Use when spawning subagents via the Agent or Workflow tools, when fanning out more than a handful of agents, or when the user asks which model or effort a task should route to. Grounded in measured calibration data (references/calibration-2026-07-15.md), not vibes.
compatibility: Designed for Claude Code / Claude Code on the Web — assumes an orchestrator with Agent/Workflow subagent tools exposing per-call model and effort options. Not applicable to claude.ai chat use.
metadata:
  author: Oskar Austegard and Claude (Fable 5)
  version: "1.0.0"
---

# Agent Routing — model + effort selection for subagents

One question decides most routing: **is the task mechanically checkable, or does
it require judgment?** Checkable tasks go to Haiku with a verifier. Judgment
tasks go up-tier. Everything else here is refinement of that split.

For turning a judgment-shaped task INTO a Haiku-executable one (explicit
procedures, n-shot examples), use the sibling `down-skilling` skill; this skill
decides the routing, that one engineers the prompt.

## Priors that measured data overturned (2026-07-15)

- **Haiku 4.5 does not need help on closed-form work.** 240/240 across nested
  mod-23 arithmetic (16-leaf trees), 30-hop function chains, 25-op state
  tracking, trap-laden word math, and 5-constraint sentence generation
  (including a lipogram) — even with chain-of-thought suppressed and
  `effort: 'low'`. Do not route these up-tier "to be safe"; the safety is
  imaginary and the cost is 3–5×.
- **Bigger is not automatically more precise.** In the same battery Sonnet at
  low effort went 17/20, miscounting exact-word-count constraints twice and
  breaking a no-letter-'e' constraint once. Small n — treat as "no evidence of
  up-tier benefit," not "Sonnet is worse" — but the burden of proof now sits on
  routing *up*, not down.
- **Effort didn't move Haiku on mechanical tasks** (low == high == 100%).
  Default subagents to `effort: 'low'` for anything checkable; spend effort,
  not parameters, only where reasoning depth demonstrably falls short.
- **Blind self-improvement loops are identity-or-drift.** Re-running a fixed
  prompt on a correct answer returned the identity in 96/96 loop-pairs; the
  one task whose output did change (a 5-7-5 haiku) got *worse* on loop 2 and
  froze on the broken text for all remaining loops. Loops only pay when an
  out-of-band evaluator selects among iterations.

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

## The cascade (default composition)

When a cheap verifier exists, never choose between Haiku and Sonnet — compose:

```
result = haiku(task, effort=low)
if verify(result) fails:  result = sonnet(task)      # escalate on evidence
if verify(result) fails:  result = opus(task)         # rare
```

Pricing (per MTok, 2026-07): Haiku $1/$5 · Sonnet $3/$15 · Opus 4.8 $5/$25.
Expected cascade cost ≈ `c_haiku + p_fail × c_sonnet`, so with a reliable
near-free verifier the cascade beats Sonnet-direct whenever Haiku's failure
rate is **below ~2/3**, and beats Opus-direct below ~4/5. Every checkable task
measured so far has Haiku failure ≈ 0 — the cascade is nearly pure savings.
No verifier ⇒ no cascade: route by the table instead, because silent Haiku
errors compound downstream.

## Loop discipline (evaluator as exit gate)

Derived from a Looped-Mamba replication (arXiv 2607.10110, run 2026-07-15 with
Haiku subagents as the shared recurrent block): an LLM call already unrolls its
own depth as chain-of-thought, so re-applying the same prompt to its own output
is the identity at best and regression-then-freeze at worst.

1. **Never blind-loop.** Only loop with an out-of-band evaluator scoring every
   iteration — ground truth, mechanical checker, or an up-tier judge.
2. **Select, don't trust the last.** `final = argmax_r eval(answer_r)` — never
   ship iteration N just because it's newest.
3. **Stop on first regression.** If `eval(r) < eval(r-1)`, stop; empirically
   loops froze on the degraded output rather than recovering, so the
   local-minimum risk of stopping early is smaller than the drift risk of
   continuing.
4. **Loop for diversity, not depth.** Vary the prompt/angle per iteration if
   you want the loop to explore; identical re-application converges instantly.
5. **"Improve this" with no headroom is the danger zone.** Asking a model to
   improve an already-good answer pressures it to change something; without a
   selector that change ships. With one, it's harmless.

## Judge rules

- Judge model ≠ worker model; judge at least one tier up (Sonnet judging
  Haiku, Opus judging Sonnet). Same-model self-assessment was not tested here —
  don't assume it works.
- Prefer mechanical checkers over judges wherever a spec can be executed
  (word counts, schemas, tests, regex). They're free, deterministic, and the
  calibration used zero judge tokens.
- Judges are for rubric quality, not arithmetic — don't ask Sonnet to verify a
  sum a Python one-liner can check.

## Escalation triggers (route up despite the table)

- The verifier fails twice at the same tier.
- The task requires weighing trade-offs with no checkable ground truth.
- Output will be shipped verbatim to a human without review.
- The subagent must plan its own multi-step tool strategy over many turns.

## Known unknowns (recalibrate when these bite)

- Boundary location: no deterministic task has made Haiku fail yet, so the
  cliff is *somewhere past* this battery — probe with harder instances before
  trusting Haiku on a genuinely novel task family.
- Multi-turn agentic tool use was not calibrated — the table's up-tier rows
  there are prior, not measurement.
- Model versions move: re-run the battery in
  [references/calibration-2026-07-15.md](references/calibration-2026-07-15.md)
  when Haiku or Sonnet rev bumps.
