# Method and measurements

Reference for `deciding-with-confidence`: how the reference decision models get
their probabilities, how this skill estimates them without logits, and what the
2026-10-09 eval measured. Read it when choosing thresholds or deciding whether
this skill is good enough for a use.

## Reference models compared

| | OpenAI Decisions (`gpt-6-luna`) | Strands Decider 2B | decider |
|---|---|---|---|
| Model | undisclosed | Qwen3.5-2B torso, LM head removed, rank-16 LoRA | Haiku 5.5, unmodified |
| Where the distribution comes from | the network (method undisclosed) | a ~1M-parameter pointer head scoring each option's hidden state against the `<answer>` position | verbalized per-option probabilities, pooled over permuted samples, temperature-scaled |
| Can it generate text | no output tokens billed | no | yes, so the prompt has to stop it |
| Latency | "~10x faster than Responses" | 115 ms median on a 3090 | ~4 s per request through `claude -p` (see below) |
| Price | $0.10/MTok input, no output charge | local | $0.10/MTok input + $0.50/MTok output, ~$0.0001 per sample |

Both reference APIs report `confidence = (k·p_max − 1)/(k − 1)`, the top
probability's distance above uniform. Neither documents it; it reproduces
OpenAI's published 0.93 (choice) and 0.55 (score) and Strands' 0.768 exactly,
so decider uses it and `tests/test_decide.py` pins all three.

## Estimating confidence without logits

1. Every sample gives a probability for every option. A reply that omits a key
   is discarded rather than guessed at.
2. k samples (default 3) run in parallel with the options shuffled (choice,
   predicate) or the rubric reversed (score). Averaging cancels position bias,
   and disagreement flattens the pooled distribution, which lowers
   `confidence` through the same formula.
3. The pool is temperature-scaled per question type, `p ∝ p^(1/T)`, with T
   fitted by `calibrate` on labelled results.
4. `diagnostics` on each answer carries `agreement` (share of samples whose top
   option matches the pool), `spread` (mean total-variation distance from the
   pool), the pre-temperature `raw` pool and each sample's distribution.

## Measured

2026-10-09, `assets/eval.jsonl`: 104 labelled items. 64 are from
the banking77 test split (PolyAI, CC-BY-4.0), restricted to eight card intents
that are easy to confuse (`card_arrival` / `card_delivery_estimate`,
`compromised_card` / `card_payment_not_recognised`, …). 24 are handwritten
predicates, mostly the Strands agent-guardrail questions (are the tool call's
arguments grounded, should the assistant clarify first). 16 are rubric scores.
One k=5 run supplies k=1/3/5 by pooling the first k samples. The calibrated
row uses 2-fold cross-validation, so no item is scored by a temperature fitted
on itself. Brier is the sum of squared errors over options, halved; ECE uses 10
bins of top probability; AUROC is how well the top probability separates
right answers from wrong ones.

| | accuracy | Brier | ECE | AUROC | wall time | cost / request |
|---|---|---|---|---|---|---|
| Jev (TypeSafe) | 0.894 | 0.075 | 0.045 | 0.88 | 0.3 s | — |
| decider k=1 | 0.865 | 0.106 | 0.070 | 0.80 | 3.6–5.0 s | $0.0001 |
| decider k=3 | 0.846 | 0.104 | 0.068 | 0.86 | 4.1–4.3 s | $0.0003 |
| decider k=3, choice calibrated (shipped) | 0.846 | 0.105 | 0.041 | 0.84 | same | same |
| decider k=5, raw | 0.846 | 0.102 | 0.070 | 0.86 | ~6 s under load | $0.0016 |

What the numbers support:

- Jev is ahead on accuracy (+3–5 points) and Brier, and 14x faster. One
  standard error at n=104 is about 3.4 points, so that gap is suggestive
  rather than settled, and the differences between k values are noise.
- After calibration decider's ECE matches Jev's, and their wrong answers sit
  at similar confidence: 9 of decider's 16 misses had a top probability under
  0.7, and 6 of Jev's 11. Accuracy is level on the yes/no (87.5%) and rubric
  (87.5%) items; the whole gap is on the eight-way intent items (82.8% against
  90.6%).
- Escalating every answer under 0.7 or with split samples sends 23 of 104
  items onward and leaves decider 6 wrong; a 0.7 threshold on Jev sends 12
  onward and leaves 5. Both assume escalated items are resolved correctly,
  and 0.7 was chosen on this same data. (On the uncalibrated pool the same
  threshold sent 29 onward and left 4: calibration sharpens choice answers,
  so fewer fall under it.)
- Agreement between samples is the most useful signal. At k=3 the 88
  unanimous items were 92% right and the 16 split items 44%. Escalate a split
  answer (`diagnostics.agreement < 1`) to a stronger model.
- Extra samples cost no wall time, since they run in parallel, and they buy
  the agreement signal. k=3 is the default.
- Haiku's pooled distributions are underconfident: the choice temperature is
  0.62, which sharpens them. Only `choice` has enough labels (64) to fit one.
  Predicate and score keep T=1 until a labelled set reaches 50 per type
  (`MIN_CALIBRATION`).
- The first run dropped 14 of 520 samples because Haiku left ruled-out
  options out of 8-way answers. Omitted keys now share the unassigned mass,
  and the re-run lost none.

The CLI floor sets the `cli` transport's latency: about 1.2 s of node startup
plus 1 s of CLI work around 0.5–0.8 s of API time. The `api` and `bedrock`
transports skip both, so they should take roughly the API time. They were
tested against a local server standing in for the Messages API, not live: the
eval environment had no API key. Their requests disable thinking at effort
`low`, which the `cli` runs did not set, so refit the calibration on them
before trusting the bundled temperature.

Jev is TypeSafe's decision model, reached at `api.typesafe.ai/v1/systemone` or
through the Cloudflare AI Gateway; it was the comparison because its key was at
hand. Its rows come from the same 104 items through the same scoring code.
