# Calibration evidence — 2026-07-15

Data behind the routing heuristics in SKILL.md. Collected in one CCotw session
(Fable 5 orchestrator, Workflow tool, session `bf6d02ee`), ~12.3M subagent
tokens total across four workflow runs, zero agent errors. All numeric grading
was deterministic (Python scorers against generated ground truth); the only
judge tokens were Sonnet scoring open-ended text in Experiment 1.

## Experiment 1 — Looped Haiku subagents (Looped-Mamba analog, arXiv 2607.10110)

Design: `answer_r = Haiku(task, answer_{r-1})`, R=5, out-of-band eval per loop.

| Task family | Instances × loops | Result |
|---|---|---|
| Nested mod-23 arithmetic, depth-3 trees | 5 × 5 | 100% at r=1, flat, 0 churn |
| p-hop function chains (n=7, 8–12 hops) | 5 × 5 | 100% at r=1, flat, 0 churn |
| Harder: depth-4 trees (16 leaves) | 8 × 5 | 100% at r=1, flat, 0 churn |
| Harder: n=12 chains, 20–30 hops | 8 × 5 | 100% at r=1, flat, 0 churn |
| Answer-only control (CoT suppressed, effort=low), depth-4 trees | 8 × 5 | still 100% at r=1, 0 churn |
| Open-ended (Sonnet judge /10): prime one-liner | 1 × 5 | [10,10,10,10,10] |
| Open-ended: sky-blue explanation | 1 × 5 | [9,9,9,9,9] |
| Open-ended: 5-7-5 haiku | 1 × 5 | **[9,3,3,3,3]** — loop 2 broke the middle line to 8 syllables, loops 3–5 froze on identical broken text |

Interpretation: a single LLM call spends variable internal compute (CoT), so
`answer_1` is already a fixed point on checkable tasks — the paper's
fixed-compute-per-step premise doesn't hold for LLM subagents. The exit-gate
idea *does* transfer: the evaluator-as-selector recovers the loop-1 haiku and
skips wasted loops elsewhere. Answer churn across all deterministic loop-pairs:
0/96 flips.

## Experiment 2 — Single-shot routing calibration (60 agents)

20 tasks × 3 configs, single shot, deterministic local scoring:

Tasks: 9 constraint-stack sentences (K=3/4/5 simultaneous constraints: exact
word count, begin-word, include-word, end-word, no letter 'e'), 4 trap-laden
word-math problems (distractor numbers), 3 state-tracking problems (3 boxes,
25 operations), 4 constraint-preserving revisions (exact N words, fixed
first/last word, ≥2 changes).

| Config | stack | trap | state | revision | total |
|---|---|---|---|---|---|
| haiku, effort=low | 9/9 | 4/4 | 3/3 | 4/4 | **20/20** |
| haiku, effort=high | 9/9 | 4/4 | 3/3 | 4/4 | **20/20** |
| sonnet, effort=low | 6/9 | 4/4 | 3/3 | 4/4 | **17/20** |

Sonnet-low failures (hand-verified, real):
- `stack-K3-1`: 15 words where exactly 14 required
- `stack-K4-0`: 13 words where exactly 12 required
- `stack-K5-0`: used "quiet" in a no-letter-'e' sentence

Notes:
- n=20/config: 17 vs 20 is not statistically significant. The defensible claim
  is "no evidence of up-tier benefit on mechanical tasks," which is enough to
  invert the default (burden of proof on routing up).
- Haiku's K5 lipogram outputs were flawless, e.g. "Our distant stars hang
  bright and high throughout dark night" (10 words, begins "our", includes
  "stars", ends "night", zero e's).
- Effort had no measurable effect on Haiku here (both 100%) — consistent with
  Experiment 1's answer-only/effort-low control also scoring 100%.

## Pricing basis (2026-07, per MTok in/out)

Haiku 4.5 $1/$5 · Sonnet 5 $3/$15 ($2/$10 intro through 2026-08-31) ·
Opus 4.8 $5/$25. Cascade break-even: Haiku-first beats Sonnet-direct while
p_fail(Haiku) < 1 − c_H/c_S ≈ 2/3; beats Opus-direct while < 4/5 (verifier
assumed near-free, which held — all Experiment 2 scoring was local Python).

## What has NOT been measured

- A deterministic task family where Haiku actually fails (the cliff).
- Multi-turn agentic tool-use quality per tier.
- Same-model self-judging reliability.
- Haiku at higher K (>5 simultaneous constraints) or longer state chains.

Re-run: generators + scorer live in the session scratchpad pattern
(`gen.py`/`gen2.py`/`gen3.py`, `score.py`); regenerate with new seeds and a
current model rev before trusting the table across model versions.
