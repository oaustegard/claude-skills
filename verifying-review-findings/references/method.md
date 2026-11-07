# Method and measurements

This is a reference file: it records how the skill was measured and how the
default thresholds were chosen. It does not change the procedure.

## Eval set

`assets/eval.jsonl` holds 36 labelled findings, written for this skill on
2026-11-07 by a Sonnet subagent working from a brief. They are synthetic, not
sampled from real reviews.

| Label | Items | What it is |
|---|---|---|
| `confirmed` | 16 | a real defect |
| `refuted` | 16 | a false positive of a kind reviewers actually produce: a guard earlier in the function, a lock every caller holds, a correct bound, an allowlisted SQL identifier, cleanup in a `finally` or `defer` |
| `ungrounded` | 4 | a quote that is not in the file: renamed variable, paraphrase, invented line, two lines merged |

The languages are Python (14), TypeScript/JavaScript (8), Go (6), shell (4),
and SQL or YAML (4). Each file has 30 to 90 lines. For 15 of the 16 refuted
items and 15 of the 16 confirmed ones, the deciding evidence sits outside the
quoted lines, so the verifier has to read the window and not just the quote.
The generator compiled or parsed every file and ran behaviour tests on 19
items to check their labels. The descriptions use the same confident voice for
real and false claims.

Each item has the form `{id, files: {path: text}, finding, label,
true_severity, kind}`. `verify.py eval` writes the files to a temporary
directory and runs the same grounding and Jev call that `run` does.

## Results

These are from jev-1.14.0 through the direct API on 2026-11-07, with the
default window (enclosing top-level block, 12 lines of padding, 160-line cap).

| Metric | Result |
|---|---|
| Ungrounded quotes dropped before Jev | 4/4 (deterministic) |
| Real defects kept (not dropped) | 16/16 |
| Real defects marked `confirmed` | 11/16; the other 5 were `uncertain` |
| False findings dropped | 11/16 |
| False findings marked `confirmed` | 1/16 |
| Top-answer accuracy over the 32 verified items | 0.781 |
| Unverified (errors) | 0 |

The errors:

- **One false finding confirmed** (`ts-04`, a race claimed in single-threaded
  synchronous code): P(confirmed) was 0.89. This is the one result that would
  reach a reader as a finding, and its confidence gives no warning.
- **Four false findings left `uncertain`.** Two stayed uncertain because the
  claim depended on code not in the window, which Jev reported as
  `insufficient_context` at 0.40 and 0.82. The other two, an operator-precedence
  misread and `set -e` covering a `cd` failure, got split verdicts of about
  0.6 confirmed against 0.35 refuted.
- **The real defect closest to being dropped** was `ts-03`, unguarded
  prototype pollution, at P(refuted) 0.64. Jev read the merge as safe.

## Threshold choice

The drop threshold was swept over the 32 verified items:

| `refute_at` | Real kept | False dropped |
|---|---|---|
| 0.4 to 0.6 | 15/16 | 11/16 |
| 0.7 to 0.8 | 16/16 | 11/16 |
| 0.9 | 16/16 | 8/16 |

The default is 0.7, the lowest value at which no real defect was dropped. The
margin is small: `ts-03` sat at 0.64. These thresholds were chosen on the same
36 items they are reported on, and the items are synthetic, so treat them as
a starting point. Before relying on the gate, re-run `eval` on labelled
findings from your own reviews.

`confirm_at` 0.7 was not tuned. At that value 11 of the 16 real defects were
confirmed; the other 5 ranged from 0.14 to 0.69 and stayed `uncertain`, so
they are reported, not lost.

## What this does not measure

- **Real reviewer output.** A finder's actual false-positive mix may differ
  from these sixteen patterns.
- **Claims that span files.** Each eval item is a single file, so every item
  has its evidence inside the window.
- **Verdict agreement across runs.** Jev answers in one deterministic call, so
  this skill has no equivalent of the sample-agreement signal in
  `deciding-with-confidence`.
- **The `decider` and `gateway` transports.** Neither was run on the eval.
