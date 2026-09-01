---
name: hallucinating-labels
description: >-
  Assign items to a CLOSED label vocabulary that is too large to put in a prompt —
  product taxonomies, category hierarchies, tag vocabularies, routing tables, ICD/SIC-style
  code lists. A cheap model writes the label it thinks the vocabulary would use, and an
  embedder snaps that writing onto the nearest legal value, so the schema is never
  transmitted and the output is always in-vocabulary. Use for "classify these into our
  taxonomy", "tag these against the existing tag list", "map these queries to categories",
  "the enum is too big to send", or a Literal/enum that hits a provider cap. NOT for a
  vocabulary that fits in a prompt — structured output measured 0.701 acc@1 there against
  this pattern's 0.564. NOT for open-ended labelling with no fixed vocabulary, and not for
  ranked retrieval over documents (bm25).
metadata:
  version: 0.1.0
---

# hallucinating-labels

Ask a cheap model to write a plausible label for the item. Snap that label onto the real
vocabulary with an embedder. The model never sees the label set.

Doug Turnbull's pattern ([softwaredoug.com, 2026-08-10](https://softwaredoug.com/blog/2026/08/10/hypothetical-classifications)),
with the two prompt and boundary corrections that measurement produced.

## Check the boundary first

**If the whole vocabulary fits in a prompt, do not use this skill.** Ship the label list
and ask for a constrained choice. Measured on WANDS (860 labels, 468 queries, one gold
label each, gemini-3.5-flash-lite):

| approach | acc@1 | acc@3 | input tokens/item |
|---|---|---|---|
| structured output, all 860 labels shipped | **0.701** | **0.744** | 5,265 |
| this skill | 0.564 | 0.690 | 6 |
| embed the item directly, no model | 0.417 | 0.564 | 0 |

Shipping the vocabulary is 14 points more accurate and 880× more expensive. Take the
accuracy unless the tokens are the problem. The tokens are the problem when the
vocabulary does not fit, when a provider enum cap rejects it, or when per-call cost at
volume dominates — a 5,000-label vocabulary is roughly 30k tokens on *every single call*.

This skill still beats every model-free baseline by a wide margin, so it is the right
tool whenever shipping the vocabulary is off the table.

## Procedure

**1. Write the vocabulary to a file**, one label per line, and index it once.

```bash
python3 scripts/snap.py build --vocab categories.txt --out .snap-index.pkl
```

Default backend is `tfidf` — sklearn only, no download. Pass `--backend minilm` when
sentence-transformers and a ~90 MB download are available and the items share no wording
with the labels; it scored 0.564 to tfidf's 0.528 on WANDS. Where items literally contain
their own label words, tfidf wins outright (0.416 vs 0.356 on a memory-tag corpus).

**2. Write the labels yourself, in batches of 40, using the register prompt below.**
Write them to a file, one per line, in the same order as the items.

**3. Snap.**

```bash
python3 scripts/snap.py snap --index .snap-index.pkl --labels written.txt --k 3
```

Add `--min-score 0.35` to get `null` instead of a bad snap, and `--items items.txt --union`
for long items (see below). Output is JSON with the top-k legal labels per item.

**4. Report the nulls and the low scores.** A snap at cosine 0.18 is noise wearing a legal
label. Never present one as a classification.

## Anchor the prompt on REGISTER, not on novelty

This is the correction that matters most, and it is the opposite of what the source post's
prompt says. Its prompt opens *"create a novel, never-seen-before classification"*. That
instruction is safe only with a model too weak to follow it.

Measured on the same 40 WANDS queries, MiniLM backend:

| prompt | model | acc@1 | acc@3 |
|---|---|---|---|
| embed the query directly, no model | — | 0.500 | 0.650 |
| "novel, never-seen-before" | gemini-3.5-flash-lite | 0.575 | 0.675 |
| "novel, never-seen-before" | Haiku 4.5 subagent | **0.100** | 0.275 |
| register-anchored (below) | Haiku 4.5 subagent | 0.525 | **0.750** |

Haiku obeyed. Asked for novelty it produced novelty — `Hydraulic Styling Thrones`,
`Weathered Branch-Frame Reflectors`, `Chromatic Comfort Accents` — and scored a fifth of
what doing nothing scores. Gemini flash-lite half-ignored the same instruction and wrote
`Salon & Styling Chairs`, `Rustic Wall Mirrors`, which is what the snap needs. The pattern
wants a novel *instance in the vocabulary's register*, and "never-seen-before" asks for
novel *wording*. A better instruction-follower is worse at the badly-worded prompt.

The register prompt also beat the novelty prompt on Gemini across all 468 queries
(0.564 vs 0.489 acc@1), so it is strictly the better wording. Use this:

> You are writing entries for a {DOMAIN} vocabulary.
>
> For each item below, write the label that this vocabulary WOULD file that item under.
> Write it the way the vocabulary writes labels — match the examples' register, length and
> wording exactly.
>
> Do not worry about whether the label already exists. Write the obvious one. Do not invent
> novel or creative wording, do not use marketing adjectives, do not hedge, do not explain.
>
> Examples of the register:
> {6-8 REAL LABELS FROM THE VOCABULARY}
>
> Output one line per item, in the same order, formatted exactly as:
> `<n>. <label>`
>
> ITEMS:
> {NUMBERED ITEMS}

The examples are load-bearing — they are how the register gets communicated. Draw 6-8 real
labels from the vocabulary. They are not the vocabulary; sending eight labels is not
sending five thousand.

## Batch 40 per call. Never one item per call

Batching is free: 0.496/0.641 batched ×40 against 0.489/0.613 unbatched, at 1/17 the input
tokens and 1/9 the wall-clock.

Write the labels yourself when the items are already in context — you are the cheap model
here, and it costs one short generation. **Delegate to a Haiku subagent only in batches,
and only when the item list is long enough to be worth it.** A subagent invocation carries
a measured floor of ~32,500 tokens before it reads your prompt: a `general-purpose` Haiku
subagent asked to output the single word `ok`, with zero tool calls, spent 32,539. Per
item that floor is 813 tokens at batch 40 and 32,500 at batch 1.

Parse the model's numbered reply **back by index**, not by zipping positionally. When the
model drops item 2 of 40, zipping shifts every later item onto its neighbour's label and
nothing signals it. A dropped item is an empty label and then a `null`.

## Long items want `--union`, not a different pattern

The written label replaces direct embedding cleanly when item and label are the same kind
of string — a WANDS query and a WANDS category are both short noun phrases. When the item
is a 1,500-character document and the label is one word, the written label throws away most
of the document, and the direct embedding still has it. The two are complementary.

Memory store, 1,273 tags, 250 documents of 300-2000 characters, mean 4.8 gold tags, tfidf:

| arm | @1 | @3 | @5 |
|---|---|---|---|
| embed the document directly | 0.416 | 0.628 | 0.712 |
| write 5 tags, **novelty** prompt | 0.208 | 0.352 | 0.424 |
| write 5 tags, **register** prompt | 0.508 | 0.700 | 0.792 |
| both, interleaved (`--union`) | **0.672** | **0.852** | **0.888** |

Note the middle two rows. With the wrong prompt this corpus says the pattern loses to doing
nothing by 2x; with the right one it wins, and the union wins by a lot more. Long items
amplify the register error rather than causing a separate problem — a distinctive
vocabulary is exactly where novel wording lands furthest from anything legal.

Rule: item and label share a register → write labels and snap them. Item is a long document
→ do that **and** pass `--items ... --union`. Neither case is a reason to reach for the
novelty prompt.

## Picking the encoder, and why there is no local-LLM version

The encoder is the whole system when you cannot reach an API. Snapping the raw query,
no model call anywhere, full WANDS set:

| encoder | int8 ONNX | acc@1 | acc@3 |
|---|---|---|---|
| all-MiniLM-L6-v2 | 23 MB | 0.417 | 0.564 |
| bge-small-en-v1.5 | 33 MB | 0.427 | 0.583 |
| **gte-small** | **33 MB** | **0.455** | 0.594 |
| bge-base-en-v1.5 | 109 MB | 0.462 | 0.630 |

`gte-small` is the knee. `bge-base` buys +0.007 acc@1 for 3.3x the download.

**Do not substitute a tiny local model for the label-writing half.** Pleias `Monad` (57M)
and `Baguettotron` (321M) both have `onnx-community` builds — 35 MB and 236 MB at q4f16 —
so a wholly client-side pipeline packages fine. Neither earns its bytes. As writers they
score 0.425 and 0.400 acc@1 against a 0.500 no-model control on the same 40 queries: they
echo the query (`smart coffee table` → `Smart coffee table`) and bleed from the few-shot
exemplars (`chair and a half recliner` → `Chair & Recycling Bins`). As likelihood
rerankers over the encoder's top-10 — which asks them for no format compliance at all —
they score 0.325 and 0.350 against the same 0.500, with the gold label present in that
top-10 for 82.5% of queries.

The reason is the same one that makes the register prompt matter: what the cheap model
contributes here is not reasoning but a **prior over how taxonomies name things**, learned
from web-scale pretraining. A small model trained for reasoning has no retail-taxonomy
prior, and reasoning does not substitute for one. In a browser, ship the encoder alone.

## Failure modes

| signal | cause | fix |
|---|---|---|
| Snapped labels are wrong but confident; written labels read like ad copy | novelty-anchored prompt, obeyed | switch to the register prompt; read the written labels before blaming the snap — `Hydraulic Styling Thrones` is a prompt bug, not an embedder bug |
| Everything snaps to the same one or two labels | the register examples are unrepresentative, or the vocabulary has one dominant string | draw examples spanning the vocabulary's breadth |
| Scores cluster near 0.15 | items and labels share no surface wording | `--backend minilm`, and `--union` if items are long |
| Item *n* onward all shifted by one | positional zipping of a reply with a dropped line | parse by the emitted index; verify counts match before snapping |
| Accuracy below the no-model control | novelty-anchored prompt, or a long item without `--union` | fix the prompt first — it cost 30 points on one corpus and 7.5 on another; then add `--union` |

## Verify it beat doing nothing

**Run the no-model control before shipping this anywhere.** Snap the items directly
(`--labels items.txt`, no written labels) and compare. On one of the two corpora measured
here the control won by 2x under the wrong prompt. If you have no gold labels to score against, hand-check 20
items both ways — the control is one command and its absence is how this pattern gets
adopted where it loses.

## Related

- `bm25` — ranked retrieval over documents. Different problem: no closed label set.
- `agent-routing` — routing to a small named set, which fits in a prompt. Ship it instead.
- `muninn_utils.hypothetical_classifier` — the same pattern as a Python API with Gemini
  wired in, for Muninn sessions.

Experiment, arms and artifacts: `oaustegard/experiments/hypothetical-classification`.
