# Method and measurements

This file records how `verifying-review-findings` was measured and how its
default thresholds were chosen. It is a reference and does not change the
procedure in SKILL.md.

## Eval set

`assets/eval.jsonl` holds 36 labelled findings. A Claude Sonnet subagent wrote
them on 2026-11-07 from a written specification. They are synthetic: no item
was sampled from a real review.

| Label | Items | What it is |
|---|---|---|
| `confirmed` | 16 | a real defect |
| `refuted` | 16 | a false finding of a kind reviewers produce: a guard earlier in the function, a lock every caller holds, a bound that is correct, a SQL identifier taken from an allowlist, cleanup in a `finally` or `defer` |
| `ungrounded` | 4 | a quote that is not in the file: a renamed variable, a paraphrase, an invented line, two lines merged into one |

The files are Python (14), TypeScript or JavaScript (8), Go (6), shell (4),
and SQL or YAML (4). Each file is 30 to 90 lines. For 15 of the 16 refuted
items, and 15 of the 16 confirmed ones, the code that shows whether the claim holds
sits outside the quoted lines, so the verifier has to read the window, not
just the quote. The subagent that wrote the set compiled or parsed every file
and ran behaviour tests on 19 of the items to check that their labels hold.
Descriptions use the same confident voice for real and false claims.

Each line of the file is one item:

```json
{"id": "py-01", "files": {"src/cache.py": "<full file text>"},
 "finding": {"file": "src/cache.py", "line": 42, "description": "...",
             "code_quote": "...", "fix": "...", "severity": "high"},
 "label": "confirmed", "true_severity": "high", "kind": "unlocked-write-vs-locked-iteration"}
```

`finding` has the input shape of SKILL.md step 1. `label` is one of the three
in the table. `true_severity` is the defect's real severity on the same
five-level scale, or `none` for refuted and ungrounded items. `kind` is a
short free-text tag for the defect or the false-positive pattern. `verify.py
eval` writes each item's files to a temporary directory, then runs the same
grounding and Jev call that `run` does. To measure the skill on your own
reviews, write your labelled findings in this shape, with each file's full
text inline; `true_severity` and `kind` are optional.

## Results

These were run with jev-1.14.0 through the direct API on 2026-11-07, with the
default window: the enclosing top-level block, at least 12 lines of padding,
and a 160-line cap. The 32 "verified" items are the 36 minus the 4
ungrounded ones, which grounding drops before Jev sees them.

| Metric | Result |
|---|---|
| Ungrounded quotes dropped by grounding | 4/4 |
| Real defects kept (not dropped) | 16/16 |
| Real defects `confirmed` | 11/16; the other 5 were `uncertain` |
| False findings dropped | 11/16 |
| False findings `confirmed` | 1/16 |
| Verdict accuracy: the most probable verdict equals the label, over the 32 verified items | 0.781 (25/32) |
| `unverified` (errors) | 0 |

The item ids below refer to `assets/eval.jsonl`.

- **One false finding confirmed.** `ts-04` claims a race condition in
  synchronous single-threaded JavaScript, and P(confirmed) was 0.89. This is
  the one error that would reach a reader as a finding, and its confidence
  gives no warning.
- **Four false findings left `uncertain`.**
  - `sh-03` and `py-05`: the refuting code was in the same file but in another
    function, outside the window. P(insufficient_context) was 0.82 for
    `sh-03`. `py-05` split between P(confirmed) 0.55 and
    P(insufficient_context) 0.40.
  - `py-06` claims that Python parses `flags & wanted == wanted` as
    `flags & (wanted == wanted)`. In Python `&` binds tighter than `==`, so
    the check is correct. It got P(confirmed) 0.65 against P(refuted) 0.34.
  - `sh-02` claims a failed `cd` lets the script run in the wrong directory,
    but `set -e` at the top of the script exits on that failure. It got
    P(confirmed) 0.57 against P(refuted) 0.39.
- **The real defect closest to being dropped** was `ts-03`, prototype
  pollution through an object-merge function that does not skip `__proto__`.
  P(refuted) was 0.64.

## Threshold choice

The drop threshold was swept over the 32 verified items:

| `--refute-at` | Real kept | False dropped |
|---|---|---|
| 0.4, 0.5, 0.6 | 15/16 | 11/16 |
| 0.7, 0.8 | 16/16 | 11/16 |
| 0.9 | 16/16 | 8/16 |

The default is 0.7, the lowest value on this grid at which no real defect was
dropped. The margin is 0.06: `ts-03` sat at 0.64. The thresholds were chosen
on the same 36 items they are reported on, and the items are synthetic, so
treat them as a starting point. Before relying on the gate, run `eval` on
labelled findings from your own reviews.

`--confirm-at` 0.7 was not tuned. At that value 11 of the 16 real defects were
confirmed. The other 5 had P(confirmed) between 0.14 and 0.69 and stayed
`uncertain`, so they were reported, not lost.

## Limits of the eval

- **Real reviewer output.** A real finder's mix of false findings may differ
  from the patterns in this set.
- **Claims that span files.** Every item is a single file, so the refuting or
  confirming code is always in the same file, though not always in the
  window.
- **Run-to-run variation.** Each finding got one Jev call. Repeat calls were
  not compared, so this skill offers no signal from several answers agreeing.
  `deciding-with-confidence` gets that signal by sampling Claude several times.
- **The `decider` and `gateway` transports.** Neither was run on the eval.
