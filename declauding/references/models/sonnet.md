# Sonnet 4.6 and Sonnet 5

## As author

The Sonnet line stages less than the Opus line and does not drift the same way.
On blind staging judgments in the model-register-drift run
(`oaustegard/experiments`, `model-register-drift/`, 2026-08-23) Sonnet 4.6
scored −1.41 (95% CI [−2.74, −0.54], the only model whose interval cleared zero
on the low side) and Sonnet 5 −1.00. Between 4.6 and 5 the aphorism and verdict
family's share of violations moved from 44% to 58%, a far smaller rise than the
Opus line's.

Sonnet 5's tics are punctuation and reversal:

| entry | count | what it looked like |
|---|---|---|
| 16 em-dash gotcha | 5 | 2.94 em dashes per 150 words, about three times the entry-16 guard |
| 2 negation-first | 4 | "The cache wasn't broken — it was doing exactly what we asked it to do." |
| 3 significance designation | 4 | "But nobody complains about median latency." |
| 12 aphoristic closer | 3 | "Serial dependencies multiply your tail risk; they don't average it." |

The linter reaches most of this: `negation-first` and `em-dash` were its top
categories on the Sonnet 5 sample. Entry 16 applies unless the author's own
sample uses dashes at that rate.

Sonnet 4.6 favours fragment cadence and short verdict closers: "The p50
improved. The p99 got demolished." (15), "Straightforward stuff." (35), "So a
slow Redis was worse than no Redis." (12), and Title Case headers throughout (30).
The linter's `cadence` and `header` categories catch most of it.

Evidence is three Sonnet samples on one prompt; the hand count was retracted as a
score, and the blind judgments are what stand.

## As editor

Sonnet deletes the evidence along with the framing. In a catalogue-wide audit
of this repository (claude-skills PR #791, 2026-09-08), 7 of about 30 hunks that
Sonnet subagents produced needed a parent override, all the same shape: the
agent correctly identified a pattern to cut and took the numbers, dates and
command values with it. "5,697-line gather cut at line 120" became "thousands
of lines"; "measured 2026-07-18: asked 16:7, got 2.33" became "measured".

That is this skill's "Content lost" failure. When Sonnet runs the pass, or runs
it as a delegate:

- Step 5 (`declaude_diff.py`) is mandatory, not a check to skip on a short
  draft. Read every `LOST` line.
- State in the brief that dates, measured numbers and copy-pasteable values
  stay even when the sentence around them is cut.
- Review every hunk that is mostly deletion before accepting it.
