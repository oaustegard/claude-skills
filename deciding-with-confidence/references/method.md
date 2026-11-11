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

1. Every sample first quotes the words of the evidence that decide each
   question (the `cue`), then gives a probability for every option. When a
   sample leaves options out, they share the probability it left unassigned.
2. One sample is the default since 0.2.0. With k > 1 the samples run in
   parallel with the options shuffled (choice, predicate) or the rubric
   reversed (score). Averaging cancels position bias, and disagreement
   flattens the pooled distribution, which lowers `confidence` through the
   same formula. `--stack` also gives each of three samples a different angle:
   `plain` (no extra instruction), `literal` (decide from what the evidence
   itself states, not what it attributes to others or raises as a
   possibility) and `sceptic` (start from the answer that claims least and
   move only on an explicit statement).
3. The answer is temperature-scaled per question type, `p ∝ p^(1/T)`, with T
   fitted by `calibrate` on labelled results. A pool of several samples has
   its own temperatures (the `pooled` set in `calibration.json`), since
   averaging makes it flatter than one sample.
4. `diagnostics` on each answer carries `agreement` (share of samples whose top
   option matches the pool), `spread` (mean total-variation distance from the
   pool), the pre-temperature `raw` pool and each sample's distribution.

## Measured 2026-10-09

This run predates the cue, the one-sample default and the pooled
temperatures. Its "k=3 is the default" was true at the time. Jev, the
comparison row, is TypeSafe's decision model (last paragraph of this section).

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

## Measured 2026-11-11 with the cue prompt

Three labelled sets, all through the `cli` transport at low effort:

- `bundled`, the 104 items of `assets/eval.jsonl` described above.
- `papers`, 150 open-access research articles, each read whole (median
  3,850 words), with four questions each.
- `sections`, 395 article sections with eight questions each.

The papers and sections are labelled only where Sonnet 5.5 and Opus 5.5 gave
the same answer, so they have fewer labels than questions. Items are split
into a dev and a test half by a hash of their id. Prompts were chosen on dev,
and every figure below except the first table is from test. The eval sets,
the runner (`run/prompts.py`, `run/compare.py`) and every raw distribution
are in `oaustegard/experiments`, `haiku-decider/`. Metrics are on
uncalibrated distributions unless a row says otherwise, and intervals are
paired-bootstrap 90% intervals.

An angle is one extra instruction appended to a sample's prompt. Each
candidate ran as one sample per dev item, and stacks of three were scored by
averaging those samples. Mean over the three dev sets:

| arm | accuracy | AUROC | Brier |
|---|---|---|---|
| `plain` (no angle) | 0.868 | 0.816 | 0.194 |
| `literal` | 0.868 | 0.826 | 0.189 |
| `sceptic` | 0.869 | 0.837 | 0.186 |
| `contrast`: decide between the two best options on where they differ | 0.886 | 0.832 | 0.180 |
| `strict`: each description is a test the evidence must pass | 0.865 | 0.861 | 0.188 |
| `cue`: quote the deciding words before the probabilities | **0.902** | 0.829 | 0.160 |
| `cue` + `literal` | 0.884 | 0.876 | 0.157 |
| `cue` + `sceptic` | 0.899 | 0.856 | 0.151 |
| stack: plain, literal, sceptic | 0.881 | 0.854 | 0.177 |
| stack: each of those with the cue | **0.912** | 0.885 | **0.142** |

The cue's gain on dev was +0.030 on papers and +0.033 on sections, and
neither interval reached zero. The cue went into the system prompt's answer
format, so every sample now writes it. The stack kept its three angles.

Test half, run through `decide.py` itself (`--stack`, options shuffled per
sample). "One sample" is the first sample of each stacked request:

| accuracy (Δ vs old single, 90% interval) | bundled (52) | papers (289) | sections (1,457) |
|---|---|---|---|
| old single: plain, no cue | 0.808 | 0.931 | 0.857 |
| old stack: plain + literal + sceptic, no cue | 0.769 | 0.924 | 0.870 |
| one sample with the cue | 0.827 (+0.019, −0.058 to +0.096) | 0.969 (+0.038, +0.017 to +0.059) | 0.870 (+0.012, −0.001 to +0.027) |
| stack with the cue | 0.865 (+0.058, 0 to +0.135) | 0.962 (+0.031, +0.010 to +0.052) | 0.906 (+0.049, +0.035 to +0.063) |

The old stack here is scored by averaging the three cue-less single runs,
without the option shuffle. On the answers the 2026-11-10 run also covered,
three plain samples without the cue at the CLI's default effort (the 0.1
default) scored 0.808, 0.952 and 0.885 (the last on 591 answers); the cue
stack at low effort scored 0.865, 0.962 and 0.893 on the same answers.

- **Agreement.** The stack's unanimous answers were right 0.902, 0.985 and
  0.957 of the time on the three sets, its split ones 0.727, 0.632 and
  0.671. Splits were 21%, 7% and 18% of answers.
- **Escalation.** Calibrated top probability under 0.7, plus split answers
  for the stack. On sections one sample sent 17% of answers onward and kept
  5.6% wrong, and the stack sent 19% and kept 3.0% wrong. On papers the
  figures were 7% and 1.7% for one sample, 8% and 1.0% for the stack.
- **Cost and time.** Mean cost per stacked request was $0.0014, $0.0073 and
  $0.0038 on the three sets, and one sample costs a third of that. The cue
  adds output tokens, so one sample costs slightly more than the old single
  call and takes 1 to 1.5 s longer. Median wall time for a stacked request
  through the CLI was 7 to 11 s.
- **Calibration.** Both arms are underconfident. With 2-fold
  cross-validation by item, per-type temperatures bring ECE from
  0.027 / 0.122 / 0.037 (predicate / choice / score) to 0.008 / 0.019 / 0.043
  for one sample, and from 0.057 / 0.146 / 0.153 to 0.009 / 0.013 / 0.046 for
  the stack. The stack needs the lower temperatures (0.44 / 0.52 / 0.50,
  against 0.74 / 0.60 / 0.81 for one sample) because averaging flattens it,
  so `calibration.json` carries a `pooled` set. The shipped temperatures are
  fitted on all 1,798 test answers.
- **Scope.** Two of the three sets are life-science text labelled by
  agreeing Claude models. The short set is 52 items per half, too few to
  separate one arm from another on its own.

### Jev on the same items, and Typed Decisions

Jev's distributions for the same articles and sections were saved by the
`dettin-68m` experiment, so `run/jev_compare.py` in `haiku-decider` scores them
on the test-half answers above:

| accuracy (ECE uncalibrated / cross-validated) | articles (289) | sections (1,457) |
|---|---|---|
| Jev | 0.972 (0.023) | 0.894 (0.013) |
| one sample with the cue | 0.969 (0.093 / 0.015) | 0.870 (0.060 / 0.015) |
| stack with the cue | 0.962 (0.091 / 0.013) | 0.906 (0.113 / 0.014) |

Stack minus Jev, 90% interval: −0.028 to +0.007 on articles, −0.002 to
+0.026 on sections. One sample minus Jev on sections: −0.041 to −0.008.
On all 104 bundled items the stack scored 0.894 and one sample 0.856, against
Jev's 0.894 from 2026-10-09; half of those items chose the prompt.

[Typed Decisions](https://huggingface.co/datasets/LocalLLaMA/typed-decisions)
has 400 synthetic test cases from four workflows (agent traces, customer
service, invoices, security alerts), five questions each. Gold is the mean of
three samples from a roughly 4B-class teacher, which agrees with itself 0.735
of the time. Every case went through `decide.py` unchanged as a System One
request, `--stack` at low effort, and was scored with a copy of the dataset's
own scorer (`run/td.py`):

| 2,000 decisions | accuracy | KL from gold | Brier | ECE |
|---|---|---|---|---|
| stack, shipped calibration | 0.7465 | 0.333 | 0.121 | 0.035 |
| stack, uncalibrated | 0.7465 | 0.131 | 0.069 | 0.113 |
| one sample, shipped calibration | 0.741 | 0.241 | 0.101 | 0.039 |
| one sample, uncalibrated | 0.741 | 0.163 | 0.079 | 0.096 |
| Jev 1.13.0 (card) | 0.727 | 1.442 | 0.148 | 0.144 |

The shipped temperatures were fitted on hard labels, so they sharpen: ECE
drops, and KL and Brier against the benchmark's soft gold rise. When the
target is a soft distribution, read `diagnostics.raw`. By workflow the stack
scored 0.668 (agent traces), 0.792 (customer service), 0.814 (invoices) and
0.712 (security alerts); by type, 0.810 on yes/no, 0.737 on choice and 0.706 on
score. Unanimous answers matched gold 0.830 of the time and split ones 0.522.
A stacked case cost $0.0023 at list price and took a median 8.8 s.

