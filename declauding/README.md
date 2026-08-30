# declauding

Removes LLM prose tics from a draft and returns plain human technical prose. The
input is text; the output is either the rewritten text or an annotated HTML diff
showing every edit with its original and its reason.

The register has four groups. Entries 1 to 23, 37 and 38 are one move: **the
sentence is built to make the reader feel a finding arrive, instead of stating
the finding.** The fix is always the same: put a real subject in the subject
slot, say the thing, stop. Entries 24 to 36 are the flatter slop patterns, where
nothing is being staged and the prose is running on defaults. Entries 39 to 42
are the register of reference prose — schema formality, and maxims welded onto
facts. Entries 43 to 47 are this skill's own output: the flat, verdict-shaped
register a clean pass lands in, which is now the fastest-growing cluster of
GitHub pull request descriptions there is. Numbering is chronological within the
file, so a group is not a contiguous range.

See [`SKILL.md`](SKILL.md) for the workflow, the overcorrection guard and the
earned-exception table. See [`references/register.md`](references/register.md)
for the catalogue and [`references/corpus.md`](references/corpus.md) for the
measurement behind entries 43 to 47. See [`CHANGELOG.md`](CHANGELOG.md) for
version history.

## Two output modes

| Mode | Output | Use for |
|---|---|---|
| **clean** (default) | The rewritten text, nothing else | Fixing your own draft before publishing |
| **annotated** | One self-contained HTML file: rewritten text, every changed passage marked, each with the original verbatim, the tic name, and why | Reviewing someone else's draft, teaching the register, arguing about a specific edit |

The annotated file has a toggle that hides the marks, so the same artifact
serves as both the review and the result. No build step, no CDN, no server.

Three call shapes change what comes back: pasted text returns the rewrite plus a
short change list, file mode rewrites in place and reports a summary, and
embedded mode (another agent calling this as one step) returns the final text
and nothing else.

## Tics it catches

Fifty-two entries. All of them except part of the 24-to-36 block are grouped by
mechanism rather than by phrase, since phrase blocklists miss the next
paraphrase. The ones that show up in nearly every draft:

| Tic | Example |
|---|---|
| Negation-first reveal | *It is not a wrong answer. It is a non-answer.* |
| Significance designation | *It is the leg that answers the actual question.* |
| Abstraction agency | *Median hides it.* / *The table shows it.* |
| Deferred noun | *Five of those six rows are one cluster. The sixth is not.* |
| Coy or thesis-shaped header | *What "exhausted" means* / *The one gap that does clear the bar* |
| Aphoristic closer | *It is the kind of number that looks like evidence and is not.* |
| Straw-man knockdown | *"It thinks twice as long" is the obvious reading, and it is wrong.* |
| Fragment cadence | *Six legs. One GPU, one server build, one sampler, one question set.* |
| Dressed metaphor | *That is information loss wearing the costume of a style fix.* |

Entries 24 to 36 come from the Wikipedia AI Cleanup project's *Signs of AI
writing*, by way of [blader/humanizer](https://github.com/blader/humanizer).
They cover the register that shows up in encyclopedic summary, product copy,
README boilerplate and pasted chat:

| Tic | Example |
|---|---|
| Copula avoidance | *Gallery 825 serves as the exhibition space and boasts 3,000 square feet.* |
| Participle tail | *…resonates with the region's beauty, symbolizing bluebonnets, reflecting the community's connection.* |
| Forced triad | *keynote sessions, panel discussions, and networking opportunities* |
| Elegant variation | *The protagonist… the main character… the central figure…* |
| False range | *from the Big Bang to the cosmic web, from stars to dark matter* |
| Inline-header list | *- **Performance:** Performance has been enhanced through optimized algorithms.* |
| Chatbot residue | *I hope this helps! Let me know if you'd like me to expand on any section.* |
| Filler and hedge stacking | *It could potentially possibly be argued that…* |
| Speculative gap-filling | *…not publicly available, suggesting she maintains a low profile.* |
| Diff-anchored documentation | *This function was added to replace the previous approach…* |
| Subjectless fragment | *No configuration file needed. The results are preserved automatically.* |

Entries 39 to 42 came from a reference document — an API page, where the prose is
describing a system rather than making an argument. The staging entries mostly do
not fire on that kind of writing, and these four do:

| Tic | Example |
|---|---|
| Welded epigram | *…are dropped, so a child never carries a grant its parent lacks.* |
| Spec-ese | *That child holds no repository and waits for input.* |
| Nominalized header | *GitHub authorship in a sourced child* |
| Contents-list standfirst | *The parameter surface, plus the behavior the schema leaves out.* |

Entry 41 is the overcorrection from entry 7 and is written up as one. A verdict
header rewritten into an abstraction passes entry 7's regex and still fails entry
7's own test.

Entries 43 to 47 are the flat, verdict-shaped register a clean pass lands in —
the one this skill produces. `references/corpus.md` carries the measurement.

Entries 48 to 52 are the confiding-essayist voice, where the staging is aimed at
the reader's trust instead of at a finding:

| Tic | Example |
|---|---|
| Announced candour | *Let's be honest: I won't pretend the first run was clean.* |
| Stranded auxiliary | *The tool died; the data didn't.* |
| Retroactive significance | *That's why being able to open the environment mattered.* |
| Totalizing designation | *That's the whole point of the format.* / *the only release notes I trust* |
| Obituary headline | *Peer code review is dead* |

Each entry carries the surface tell, why it is a tic, the fix, and a
before-and-after. The first 23 come from a real published draft; the second block
keeps the Wikipedia specimens.

Several of the second block are phrase lists rather than mechanisms, which is a
real limitation and is stated as one in the register. They earn their place by
being cheap to check.

## The linter

```sh
python3 scripts/declaude_lint.py DRAFT.md            # human-readable
python3 scripts/declaude_lint.py DRAFT.md --json     # machine-readable
python3 scripts/declaude_lint.py - --quiet-slop      # stdin, minus vocabulary noise
python3 scripts/declaude_lint.py DOC.md --skip-quoted # ignore quoted specimens
```

Stdlib only. It flags the lexical tells with line numbers and categories, plus
header shape, Title Case headings, one-line-paragraph beats, fragment runs,
forced triads in all three of their comma-list, anaphora and echo forms, runs of
stacked rhetorical questions, inline-header bullets
whose label restates the item, per-instance em-dash drum rolls, em-dash density,
repeated sentence openings and phrases, curly-quote and emoji counts, and
sentence-length monotony.

One line is not a tell at all. `corpus-register density` reports how much of the
draft is the top-150 vocabulary of the load-bearing corpus cluster, which locates
the register and says nothing about the author: human stdlib docstrings run 0.08
median and 0.32 at worst, this skill's own files run 1.5 to 3.2, and the
human-written README of the repository the list came from scores 1.51, above this
skill's `SKILL.md`. Above roughly 1.0 the
cue is to read entries 43 to 47, never to cut `nothing` or `measured` on sight.
[`references/corpus.md`](references/corpus.md) has the figures and the limits.

The `reuse` block groups the hits the scan already produced and reports any
construction used more than once. It adds no rules and costs nothing, and reuse
is the strongest available evidence that a construction is a habit rather than a
choice: one `the part that` is emphasis, three is a tic.

HTML is flattened before scanning, so `<h1>`–`<h6>` and masthead
`.subtitle` / `.eyebrow` / `.post-meta` elements reach the header rules. Before
0.3.0 every header rule was silent on an HTML draft.

`scripts/declaude_review.py` is stage 2. It extracts the slots regex cannot judge
— headers, the opening sentence, each closing sentence, isolated one-sentence
paragraphs — and sends only those to a model with the structural register
entries. Slots rather than the whole document, so it is cheap enough to run every
time. The two stages are complementary rather than redundant: stage 1 catches the
verdict header deterministically and over-flags commas that belong to citations,
stage 2 reads the comma in context and catches the aphoristic closer that no
regex reaches.

`--skip-quoted` blanks blockquotes, table rows, code (fenced and inline),
`*italic*` spans and `<q>` elements while preserving line numbers. Use it on any
document that quotes bad prose as a specimen, this README included.

It finds candidates and does not decide. Every hit still needs the
sentence-level test, and no regex reaches a staged paragraph shape or a staged
closer, so **a clean report means nothing on its own.**

Exit code 1 when it finds candidates, 0 when it does not, which makes it usable
as a pre-commit hook.

## Preservation and rank

Two stages that are not the linter.

`scripts/declaude_diff.py` compares a draft against its rewrite and reports what
the edit lost and what it invented — numbers, names, quotations, code and link
targets by presence; superlative, scope, negation and hedge constructions by
count. Constructions rather than tokens, because rewriting "the format that most
invites staged reveals" as "more than most formats do" keeps the word and drops
the ranking. `--git PATH` compares the working tree against a ref, which is what
CI wants. Standard library, like the linter.

```sh
python3 scripts/declaude_diff.py SOURCE.md REWRITE.md
python3 scripts/declaude_diff.py --git blog/post.html --ref HEAD~1
```

An embedding does not do this job. On three real cases the lossy rewrite scores
*higher* cosine to the source than the faithful one, because paraphrase
invariance is what an encoder is trained for and dropping a ranking word is a
paraphrase by that measure.

`scripts/declaude_rank.py` is where an embedder does useful work: a fitted
direction in sentence-embedding space, the mean of `embed(was) - embed(now)` over
the 41 before/after pairs in `references/register.md`. Same content on both
sides, so the axis is staging and not topic. It sorts a draft's sentences and
stops there. 76% leave-one-out on the pairs; on one real pass it put all nine
edited sentences at a median rank of 13 of 53 (p = 0.031) where the regex scan
found one of nine. It cannot rank documents and does not offer a document score.
Needs torch and transformers; nothing else here does.

A fitted axis rather than a model judge because a judge takes a prompt, and two
defensible phrasings of one judging question ranked the same ten texts at -0.50
to each other. An axis has no question to phrase.
[`references/preservation.md`](references/preservation.md) has every number,
including the ones that came back negative.

## False positives

`tests/sample-clean.md` is human-written prose and must lint to zero.
`tests/sample-tics.md` is a corpus of real specimens and currently reports 167
candidates across 42 categories.

```sh
python3 scripts/declaude_lint.py tests/sample-tics.md    # 167 candidates
python3 scripts/declaude_lint.py tests/sample-clean.md   # 0
python3 scripts/declaude_lint.py SKILL.md --skip-quoted  # 15, all checked
python3 scripts/declaude_lint.py README.md --skip-quoted # 20, all checked
python3 scripts/declaude_diff.py tests/sample-clean.md tests/sample-clean.md  # 0
python3 scripts/declaude_lint.py tests/sample-structure.html   # 10, HTML path
python3 scripts/declaude_review.py tests/sample-structure.md --slots
```

One of the fifteen on `SKILL.md` is the `reuse` detector catching five parallel
table labels ("Staging shapes, entries…", "Encyclopedic shapes, entries…",
"Reference-prose shapes, entries…", "Flat-certainty shapes, entries…",
"Confiding-essayist shapes, entries…"). Five labels in a table series is the
deliberate repetition entry 27 protects, so it stays.

Three of the twenty on this README are `load-bearing`, which entry 19 does list
as a metaphor and which here is the name of a repository. A proper name is the
carve-out `SKILL.md` states and `--skip-quoted` cannot see. One is entry 49
firing on "Symmetry and antithesis are not" in the Overcorrection list, which is
the ordinary ellipsis the entry names as earned.

Several rules are deliberately tuned down to hold that zero, so the linter misses
some real coy headers and some real inline-header bullets. A linter that fires on
good writing gets ignored, and then it catches nothing. This skill's own prose is
the second clean corpus: a rule that fires seven times on `SKILL.md` is a bad
rule, and one did.

## Overcorrection

The failure mode of this skill is prose stripped of confidence, rhythm and
personality until every sentence is the same length and the writer has no
opinions. That is worse than the tics, so the guard is written into `SKILL.md`
rather than left to judgment:

- Flat is not hedged. *Class imbalance breaks the metric before overfitting
  does* is flat and certain.
- First-person judgment stays. *I did not expect the overlap to survive a 3x
  range in bits per weight* is specific, falsifiable and human.
- Sentence length varies with content. Uniformity is its own tell.
- Digression and mild informality are human. Symmetry and antithesis are not.

Every entry fires on a shape, and a shape sometimes carries a claim. Cutting it
then removes content while looking like it removed only style. `SKILL.md`
tabulates the earned form of 25 of the 47 entries, and names what hides inside a
watched phrase: superlatives, rankings, simultaneity, scope words, and the
condition attached to a hedge. *X rather than Y* is legitimate when the reader
was genuinely holding Y; it is staged when you supplied Y so you could reject
it.

## Tics carry factual errors

Step 1 of the workflow is to read the whole piece before editing anything, and
step 6 is to report contradictions separately rather than fix them.

A sentence built for shape is disproportionately likely to be wrong. In the
draft this skill was built on, two significance designations (*the leg that
answers the actual question*, *the variable the fits exist to test*) both
designated the wrong thing, and the draft contradicted each of them within two
paragraphs. Finding those is worth more than the register pass.

## Extending

The register is a working document. To add to it: put the specimen in
`tests/sample-tics.md` verbatim, write the entry with a real before-and-after,
add a lint rule if the tell is lexical, confirm `tests/sample-clean.md` still
reports zero, bump `metadata.version`.

Add a phrase to the register after two sightings in real drafts. One sighting
can be a choice; two is a habit.

## It must not invent specifics

The fix for a vague sentence is a specific one, which is exactly how a register
pass fabricates. *Experts believe it plays a crucial role* may become *the
sources here do not say who studies it*, or may be cut. It may not become
*researchers at Lanzhou University*. No name, number, date, quote or citation
enters the rewrite unless the source or the author put it there. Stance and
opinion are voice and stay; a factual claim the author did not make is a defect
even when the result reads more human.

## The author's own writing wins

Given a sample of the author's writing, match its habits and let it override the
rules here, including the em-dash density guard. Scrubbing a tell that is
actually someone's voice makes the text less like them and no more human.

## Provenance

Entries 1 to 23 came from a register pass on an external benchmark post
(2026-08-16), where 34 passages carried about 45 tic instances across ten shapes.
Every specimen in that half comes from a real published draft.

Entries 24 to 36 came from a comparison against
[blader/humanizer](https://github.com/blader/humanizer) (v2.9.1, MIT), which
packages the Wikipedia AI Cleanup project's
[Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
as a portable skill. Measured before porting: a probe file of 19 humanizer
specimens produced 2 candidates from this linter, neither for the right reason.
It now produces 33 across 13 categories. The no-fabrication rule, the
voice-sample precedence, the embedded invocation mode and the "leave these alone"
list are also from that skill.

Entries 43 to 47 came from a count instead of a draft. Louis Abraham's
[load-bearing](https://github.com/louisabraham/load-bearing) clusters GitHub pull
request descriptions by vocabulary — 461,121 of them across 85 whole weeks — and
one of its ten clusters went from 0.70% of early 2025 to 39.5% of August 2026.
Its highest-lift words are `load-bearing`, `plainly`, `quietly`, `refusal`,
`re-derived`, `asserted`, `nobody`, `genuinely`, `outright`, `byte-identical`:
not the slop vocabulary of entry 20, but the flat verdict-shaped register this
skill aims at. The five entries and the `corpus-register` line came out of that,
along with the measurement in
[`references/corpus.md`](references/corpus.md) of what the rate can and cannot
claim.

Entries 48 to 52 came from another tool rather than another corpus. Simon
Willison's
[llm-cliche-highlighter](https://github.com/simonw/tools/blob/main/llm-cliche-highlighter.html)
highlights LLM cliches in pasted text, and its 2026-08-27 update added fifteen
patterns and three structural detectors. Eight of the fifteen were already here
in some form and extended existing entries — "here's the twist" and "that's the
part" under entry 3, bare "Turns out" under 18, "batteries included" and "zero
config" under 19, stacked questions under 10, the echo run under 26. The other
five had no entry, and the shapes are the ones an essay reaches for when it is
addressing the reader directly. Several of the ported regexes are narrower here
than in the source, which is tuned for essays rather than for technical prose;
the register entries say which, and why.

Entries 39 to 42 came from a `create_session` reference artifact (2026-08-23)
that had already been through a 0.4.0 pass and reported clean. Two of its section
headers were flagged as verdict-shaped, all four were rewritten into
nominalizations, and the linter then passed the result — which is entry 41, and
the reason the entry names itself as an overcorrection.

The two skills cover different halves of the problem and both remain worth
reading. Humanizer is broader on encyclopedic and promotional slop and ships as a
harness-neutral single file; this one goes deeper on the staging mechanisms,
ships a linter with a false-positive budget, and treats a tic as a signal that
the sentence may also be factually wrong.

## Complements

- **[challenging](../challenging)** — its `prose-register` profile runs an
  adversary against a draft's voice. That one evaluates and returns findings;
  this one edits and returns text. Run `challenging` on the result if the stakes justify it.
- **[crafting-instructions](../crafting-instructions)** — writing prompts and
  instructions, where the target register is different.
- **[composing-html](../composing-html)** — general single-file HTML artifacts.
  This skill ships its own template because the annotated diff has one fixed
  shape and no reason to depend on another skill.

This skill edits register. It does not fact-check, restructure an argument, or
improve the analysis.

## Dependencies

None — Python 3.9+ and the standard library, with a self-contained HTML template.
