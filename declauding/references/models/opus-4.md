# Opus 4.6 and Opus 4.8

## As author

Opus 4.8 sits halfway along the Opus line's drift toward the aphorism and verdict
family. Its signature is the paragraph closer: 14 of its hand-adjudicated
violations across two samples were entry 12, more than any other entry for any
model in the model-register-drift run (`oaustegard/experiments`,
`model-register-drift/`, 2026-08-23).

| entry | count | what it looked like |
|---|---|---|
| 12 aphoristic closer | 14 | "We optimized the case that was already fine and taxed the case we cared about." |
| 2 negation-first | 5 | "The lesson wasn't 'caches are bad.' It was: measure the tail…" |
| 16 em-dash gotcha | 5 | "A cache miss isn't free — it's the full Postgres query plus a Redis round trip you didn't have before." |
| 29 inline-header list | 4 | bolded labels restating their item: "**Misses pay for the lookup twice.**" |
| 7 verdict header | 4 | "What the average hid" |
| 39 welded epigram | 3 | "Your tail lives in the misses, and misses cluster." |
| 37 dressed metaphor | 2 | "A cache adds a fixed tax to every request", then the tax reused (27) |

Unlike Opus 5, Opus 4.8 is not lint-clean. Its two samples scored 6.05 and 15.87
candidates per 1000 words, the second the highest in the set, carried by em
dashes, flat-certainty adverbs and triads. The linter does useful work here.
Its two samples also spread widely on blind staging judgments (+1.14 and +0.39),
so expect variance between drafts.

What this changes: run the linter and trust its em-dash and triad flags as a
start; then read every closing sentence, because entry 12 is where Opus 4.8
drafts spend most of their tics. Watch for one metaphor extended across several
paragraphs (the "tax" above became a running image), which is entries 37 and 27
together.

Opus 4.6 is the least staged Opus. Its violations spread across entries rather
than clustering (2, 12, 15, 16 at two or three each), only 30% fell in the
aphorism and verdict family, and its blind staging score sat below zero (−0.28).
It used Title Case on every header (entry 30) and the em-dash-as-pivot form of
entry 2: "the cache isn't a cache—it's a new dependency." A standard pass fits it.

Both rest on thin evidence: one Opus 4.6 sample, two Opus 4.8 samples, one
prompt. The hand count was retracted as a score; the entry composition and the
blind judgments are what stand.

## As editor

No declauding pass by an Opus 4.x model has been measured. Apply the general
workflow and the Opus 5 editor notes in `opus-5.md`, which describe the Opus
line, until a pass shows otherwise.
