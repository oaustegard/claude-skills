# Haiku 4.5

## As author

Haiku 4.5 writes the prose most readers call AI-written, and the linter finds it.
In the model-register-drift run (`oaustegard/experiments`,
`model-register-drift/`, 2026-08-23) it won all eight of its blind
"which reads more like an AI wrote it" comparisons with Sonnet judges, topped the
same question with Opus judges, and scored highest on `declaude_lint.py`
(13.06 candidates per 1000 words on one sample against 4 to 7 for the other
models). On the staging question it sat mid-table (−0.10).

Its tics sit in the flat encyclopedic family plus drama beats:

| entry | count | what it looked like |
|---|---|---|
| 2 negation-first | 6 | "Our p99 had gotten worse—not by a little, but by 800ms." |
| 12 aphoristic closer | 6 | "Measure first, always." |
| 9 drama line break | 5 | "We tracked the wrong things." as its own paragraph |
| 3, 38 designation, announcement | 3 each | "Here's the thing nobody tells you:" |
| 25, 29, 30 | lint flags | participle tails, bolded inline-header lists, Title Case headers |

What this changes: the linter carries more of the pass than it does for any
other model. Work through its report first, then check isolated one-line
paragraphs (entry 9) and colon-announced payloads (8, 38), which it also flags.
Do not skip the sentence pass; the closers still need reading.

Evidence is two samples, one prompt; the hand count was retracted as a score.

## As editor

No declauding pass by Haiku has been measured. Given that its own drafts carry
the flat family, check its rewrites against entries 24 to 36 in particular, and
run step 5.
