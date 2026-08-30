---
name: declauding
description: Removes LLM prose tics from drafts — staged reveals, "it's not X, it's Y", significance tags, abstraction agency, coy headers, fragment cadence, the flatter slop patterns (copula avoidance, participle tails, forced triads, chatbot residue), the flat-certainty patterns the pass itself produces (bare adverbs, juridical vocabulary, verification compounds, privative coinages), and the confiding-essayist patterns (announced honesty, stranded auxiliaries, retroactive significance, totalizing claims, obituary headlines) — and returns plain human technical prose. Use when text needs editing for register, when someone says "de-claude", "de-slop", "humanize this", "this reads like AI", "make this sound human", "remove the tics/claudisms", or asks for a voice/register pass on a post, README, report, PR description or essay. Also use before publishing any draft Claude wrote. Verifies the rewrite kept every claim. Produces either clean prose or an annotated HTML diff showing every edit with its original and reason.
metadata:
  version: 0.8.0
---

# Declauding

Turn LLM-shaped prose into prose a human technical writer would have written.

Two output modes:
- **clean** (default) — the rewritten text, nothing else.
- **annotated** — a single-file HTML artifact: rewritten text, every changed
  passage marked, each with the original, the tic name, and why it goes. A
  toggle hides the marks so the result can be read straight through.

Three ways it gets called, which change what you deliver:
- **Pasted text** (default) — the user gives text in the conversation. Return
  the rewrite, plus a short list of what changed if the edit was substantial.
- **File** — the user points at a path. Rewrite the file in place and report a
  summary in the conversation rather than pasting the whole result back. Edit
  prose only: leave code blocks, frontmatter, data, link targets and quoted
  specimens alone.
- **Embedded** — another skill or agent is calling this as one step of a larger
  job (a PR description, a commit message, a doc). Return the final text and
  nothing else. No preamble, no summary, no tic list.

## Do not invent specifics

The rewrite must not contain a fact, name, number, date, quote or citation that
is not in the source. This is the failure mode the skill invites rather than
prevents: the fix for a vague sentence is a specific one, and the specific has
to come from the source or from the author.

*Experts believe it plays a crucial role* becomes *the sources here do not say
who studies it*, or gets cut. It does not become *researchers at Lanzhou
University* unless the source says so. When a sentence needs real-world detail
to work, ask for it or write the plain version without it.

Opinions and stance count as voice rather than fact. Keeping the author's
judgment is required (see Overcorrection); adding a factual claim they did not
make is a defect even when the result reads more human.

## The one pattern

Almost every tic in `references/register.md` is a version of the same move:
**the sentence is built to make the reader feel a finding arrive, instead of
stating the finding.**

The generative test, applied per sentence: *am I saying the thing, or
performing having had the thought?* Say the thing.

Entries 24 to 36 are a second family — the flatter encyclopedic and chatbot
patterns, where nothing is being staged and the writing is just running on
defaults. Copula avoidance, participle tails, forced triads, chatbot residue.
Different mechanism, same pass. Entries 37 and 38 are back in the staging family
and sit last only because they arrived last.

Entries 43 to 47 are a third family, and they are this skill's own output. The
register a clean pass lands in — flat, concrete, verdict-shaped — is the
fastest-growing cluster of GitHub pull request descriptions there is: 0.70% of
early 2025, 39.5% of August 2026, with `plainly`, `quietly`, `refusal`,
`re-derived` and `byte-identical` among its highest-lift words.
`references/corpus.md` has the measurement. Flat certainty has tics of its own,
and the test is the same one register over: *am I stating the finding, or
performing having settled it?*

The response to that is not to put the staging back. It is to check that an
adverb, a hyphenated compound or an absolute negative is carrying evidence
rather than standing in for it.

Entries 48 to 52 are a fourth family and come from outside: Simon Willison's
[llm-cliche-highlighter](https://github.com/simonw/tools/blob/main/llm-cliche-highlighter.html),
updated 2026-08-27. They are the confiding-essayist voice — announced honesty, a
reversal landed on a bare auxiliary, a grade applied to a passage the reader has
already read, a part claimed as a whole, an obituary headline. Staging again, but
aimed at the reader's trust rather than at a finding.

## The author's own writing outranks this skill

If the user supplies a sample of their writing, read it before editing and match
its habits: sentence lengths, paragraph openings, punctuation, recurring
phrases, vocabulary level. Do not upgrade casual words, regularize deliberate
quirks, or apply a register rule the sample contradicts.

The sample wins over every rule here, including the em-dash density guard in
entry 16. If the author uses em dashes at three per hundred words, that is their
voice, and scrubbing the tell would make the text less like them and no more
human. The same holds for their existing published work when it is available and
the current draft is not.

## Workflow

**1. Read the whole piece before editing anything.** Tics carry factual errors.
A sentence written to sound important is disproportionately likely to be wrong,
because it was built for shape rather than for accuracy. Designations of the form
*the X that answers the real question* frequently designate the wrong X, and the
draft itself often contradicts them a paragraph later. Note contradictions now;
they are the most valuable thing this pass produces.

**2. Run the mechanical scan.**

```
python3 scripts/declaude_lint.py DRAFT.md
python3 scripts/declaude_lint.py DRAFT.html               # HTML is flattened automatically
python3 scripts/declaude_lint.py DRAFT.md --skip-quoted   # if the draft quotes bad prose
```

It flags greppable tells with line numbers and categories, plus four shapes that
are not lexical: forced triads in both their comma-list and anaphora forms,
one-line-paragraph beats, fragment runs, and constructions the document uses more
than once. The `reuse` block is the cheapest signal it produces, because a
construction used twice is a habit and counting is free.

It has no judgment. Everything it flags still needs the sentence-level test, it
reaches roughly two thirds of what a careful pass finds, and the third it misses
is the expensive third: staged paragraph shape, staged closers, dressed metaphor,
and every earned exception in the tables below. Step 2b takes part of that third;
the rest is yours. Treat a clean report as meaningless on its own.

Use `--skip-quoted` on any draft that quotes bad prose as a specimen. Without it
the scan reports the draft's own examples, which is how a real pass loses time.

HTML input is flattened before scanning: `<h1>`–`<h6>` become headings so the
header rules see them, and a `.subtitle`, `.eyebrow` or `.post-meta` element is
treated as a heading too, because a subtitle is a header by every test that
matters. Force with `--html`, disable with `--no-html`. Reported line numbers
refer to the flattened view.

The `corpus-register` density line locates a register. It does not detect an
author. Above roughly 1.0 per 100 words the draft sits in the cluster's register,
and a person who chooses that register scores there too, so the line is a cue to
read entries 43 to 47 and never a licence to cut `nothing` or `measured` on
sight. `references/corpus.md` has the figures.

Lint every string that reaches the reader, not only the body file. Page titles,
subtitles and deck headers are prose, and a builder that takes them as CLI
arguments rather than from the file will hide them from this scan.

**2a. Optionally, rank the sentences.**

```
python3 scripts/declaude_rank.py DRAFT.md --top 15
```

A fitted direction in embedding space — the mean of `embed(was) - embed(now)`
over the before/after pairs in `references/register.md` — that sorts sentences by
how staged they look. It reaches the structural third the regex scan cannot, and
it decides nothing: read each one and apply the sentence test. On the one pass it
has been measured against it put all nine edited sentences at a median rank of 13
of 53, where the regex scan had found one of the nine. It cannot rank documents
and does not offer a score for one. Needs torch and transformers; every other
stage is standard library. `references/preservation.md` has the numbers and the
failures.

**2b. Run the structural review.**

```
python3 scripts/declaude_review.py DRAFT.md
```

This is the third the scan cannot reach. It extracts the slots regex cannot
judge — every header, the opening sentence, each closing sentence, isolated
one-sentence paragraphs — and sends only those to a model with the structural
entries from `references/register.md`. Slots rather than the whole document,
because the payload stays small enough to run on every draft. Use
`--emit-prompt` where no API key is available, `--slots` to see the extraction
alone.

The two stages do not subsume each other. Stage 1 finds the flat verdict header
deterministically and over-flags commas, including the ones that belong to a
citation. Stage 2 reads a comma in context and finds the aphoristic closer, which
no regex reaches. Run both.

Run stage 2 in a context that did not write the draft. A model reviewing its own
prose is the actor that chose the words.

For a full-document register review against a named voice signature — positive
markers, drift across the piece, imposter test — use the `challenging` skill's
`prose-register` profile instead. This script is the cheap pass; that one is the
thorough one.

**3. Sentence pass.** For every sentence, in order: stating or staging? Load
`references/register.md` for the catalogue of tells and their fixes. On a draft
this skill or another model already cleaned, read entries 43 to 47 first — a
second pass over already-flat prose is where they live. On a personal essay, a
launch post, or anything addressed to the reader as a confidant, read 48 to 52
first instead.

**4. Structure pass.** Headers (are they labels or verdicts?), paragraph breaks
(is an isolated line a real pivot or a drum roll?), fragment runs, rhetorical
questions, and the closer (does the last paragraph paraphrase the subtext of
what preceded it? delete it).

**5. Check what the edit did.**

```
python3 scripts/declaude_diff.py SOURCE.md REWRITE.md
python3 scripts/declaude_diff.py --git path/to/draft.html --ref HEAD
```

Run this before reporting the pass done. It compares source against rewrite for
numbers, names, quotations, code and link targets by presence, and for
superlative, scope, negation and hedge constructions by count, and reports what
the edit lost and what it invented. Constructions rather than tokens, because
rewriting "the format that most invites staged reveals" as "more than most
formats do" keeps the word and drops the ranking.

An embedding similarity does not substitute for it: on the three real cases in
`references/preservation.md` the lossy rewrite scores *higher* cosine to the
source than the faithful one. Paraphrase invariance is what an encoder is trained
for, and dropping a ranking word is a paraphrase by that measure.

The script guards claims and not voice, and a finding is a question rather than a
verdict — a rephrasing it cannot see through takes a `--waive`. Four failure
modes, all of them common:
- Content lost. Ask it as a question and answer it claim by claim, not paragraph
  by paragraph: *does the rewrite drop a claim the source made?* A dropped
  superlative leaves the paragraph looking intact, which is why the
  read-through misses it. Every fact, number, caveat and hedge-with-content must
  survive; a tic wrapping a real qualification is still a real qualification.
  See Earned exceptions for what hides inside a watched phrase. Structure is
  free — merge or split paragraphs, compress the dull parts, dwell where the
  author would. When keeping the information and mirroring the original's shape
  pull against each other, the information wins.
- Claims changed. Rewriting "the drop is largest where chains are longest" into
  "long chains cause the drop" is an edit that invents a finding. Register only.
- Facts invented. Ask it directly: does the rewrite state any name, number, date
  or citation that is not in the source? See "Do not invent specifics" above.
- Mush. See Overcorrection below.

**6. Report factual problems separately.** Never silently fix a contradiction
found while editing. The author needs to know their draft disagreed with
itself, and only they can say which version is true.

## Overcorrection

The failure mode of this skill is prose stripped of confidence, rhythm and
personality until every sentence is the same length and the writer has no
opinions. That is worse than the tics.

- Flat is not hedged. "Class imbalance breaks the metric before overfitting
  does" is flat *and* certain. Target plain-and-sure, never plain-and-timid.
- Do not delete first-person judgment. "I did not expect the overlap to survive
  a 3x range in bits per weight" is exactly right — specific, falsifiable,
  personal. Human technical writers state preferences and surprise directly.
- Do not enforce uniform sentence length. Short for facts, compound for
  dependencies and caveats. Variation carries information; monotony is its own
  tell.
- Do not delete metaphor. Delete metaphor that is *doing significance work*
  where a plain noun fits. A metaphor that is the clearest available description
  stays.
- Digression, asides and mild informality are human. Symmetry, antithesis and
  balanced parallel clauses are not.

## Leave these alone

These are evidence of a person writing. Editing them out is how a register pass
makes a draft worse, and each one is easier to destroy than to put back.

- **Specific, hard-to-fabricate detail.** A street name, an odd quote, "the guy
  who used to run the build before he left". Models round specifics off; people
  hoard them.
- **Mixed feelings and unresolved tension.** *I think this is mostly right and it
  still bothers me and I cannot say why.* Clean takes are the model default.
- **Genuine self-interruption.** A parenthesis that corrects the sentence it sits
  in, an aside that goes nowhere. Models rarely interrupt themselves.
- **Repetition of a word** where a synonym would be worse. That is entry 27 read
  in the right direction.
- **Uneven depth.** Three paragraphs on the part the author cares about and one
  line on the part they do not is how people write.
- **Dated and subcultural references.** Slang or in-jokes pinned to a year.

Things that are not tells on their own, and should not be edited on their own:
polished grammar, formal vocabulary, a mixed casual-and-formal register, curly
quotes, a single em dash, one short emphatic sentence, an unsourced claim, a
salutation or sign-off. Look for **clusters**. One em dash is punctuation; em
dashes plus a forced triad plus *vibrant tapestry* plus a Conclusion section is a
confession.

Do not edit a watched phrase inside a quotation, a title, a proper name, or an
example where the phrase is being discussed rather than used. The linter's
`--skip-quoted` does this mechanically; do it by eye too.

## Earned exceptions

Every entry fires on a shape, and a shape sometimes carries a claim. Cutting it
then removes content while looking like it removed only style, and the result
reads fluently, so a read-through does not catch it. Check before deleting.

Staging shapes, entries 1 to 23 and 37:

| Shape | Banned when | Earned when |
|---|---|---|
| "X rather than Y" (2) | You invented Y so you could reject it | The reader was genuinely holding Y — the draft proposed it, or it is the field's default |
| "Nobody noticed" (3) | Unfalsifiable claim about others' inattention | You can name the mechanism and duration: "nobody noticed for six weeks because the dashboard only alarms on nulls" |
| Isolated one-line paragraph (9) | Gravitas beat | Real pivot: new actor, category shift, time jump |
| Colon before the payload (8) | Withholding for a beat | The payload is a list, a definition, or a code block |
| Short declarative closer (12) | Compresses the section into a moral | States a fact: "Default retries are back to 3." |
| Em dash (16) | The dash stages a beat before the punch | A genuine inline aside, or the author's sample uses them at that rate |
| Metaphor (6, 37) | It dresses a mechanism you could name | It is the clearest available description and no plain noun fits |

Encyclopedic shapes, entries 24 to 36:

| Shape | Banned when | Earned when |
|---|---|---|
| Participle tail (25) | The tail asserts significance the sentence has not earned | The clause carries a sourced claim — make it its own sentence rather than cutting it |
| Forced triad (26) | The count came from rhythm | There are genuinely three things, or a superlative or ranking rides on the phrasing |
| Elegant variation (27) | The same referent renamed for variety | The second term names a genuinely different thing |
| False range (28) | X and Y are not endpoints of any scale | A real range with real endpoints |
| Inline-header list (29) | The label restates the item | The label is a real index: a term being defined, an option name, a case name |
| Typographic tells (30) | Bold, emoji or Title Case scattered mechanically | Bold on a term at first use; the document already uses emoji; a house style requires Title Case |

Reference-prose shapes, entries 39 to 42:

| Shape | Banned when | Earned when |
|---|---|---|
| Welded epigram (39) | The second clause restates the first as a maxim | Both clauses carry distinct facts a reader can act on |
| Latinate state verb (40) | Register formality for a program doing nothing | The word is the system's own documented state — a queue whose states are `waiting` and `held` |
| Nominalized header (41) | It names a topic area instead of the content | The noun is a term this document defines, standing alone as its label — "Overcorrection", "Provenance" |
| Filler and hedging (32) | Hedges stack and none names a condition | One hedge names a real condition: "on the two runs that finished" |
| Diff-anchored (34) | The doc narrates the change that produced it | The document is version-scoped by design: changelogs, release notes, migration guides |
| Subjectless fragment (35) | The actor is known and matters | The register is clipped throughout — release notes, a feature table, a CLI help string |
| Predicate hyphenation (36) | Every pair is hyphenated in both positions | House style or a quoted source sets it |

Flat-certainty shapes, entries 43 to 47:

| Shape | Banned when | Earned when |
|---|---|---|
| Flat-certainty adverb (43) | It asserts the reader's reaction — "provably safe", "quietly dropped" | It names a contrast the reader can check: "silently" against a version that logs |
| Juridical vocabulary (44) | A program state described as an adjudication | It is the system's own documented word — a policy engine whose API says `deny` |
| Verification compound (45) | The method is compressed into an adjective and never shown | The number is beside it: "byte-identical" next to the diff, "mutation-checked" next to 14 of 15 |
| Privative coinage (46) | A minted adjective replaces the measurement | The field's term ("unsatisfiable"), or the absence is the finding and stated once |
| Exhaustive negation (47) | A universal negative stands in for the search | The scope is bounded and named: "none of the 46 chunks exceeds 0.57%" |

Confiding-essayist shapes, entries 48 to 52:

| Shape | Banned when | Earned when |
|---|---|---|
| Announced candour (48) | Sincerity claimed for a sentence that could have carried it | Reported speech, or one "to be clear" correcting a misreading the draft caused |
| Stranded auxiliary (49) | The verb is elided so the clause lands as a beat | Both halves are measured — "reads passed on all 12 shards, writes on none" |
| Retroactive significance (50) | It grades a passage the reader has already read | A "which is why" introducing a consequence the reader has not seen |
| Totalizing designation (51) | A part is claimed as the whole, or a superlative ranks an unnamed set | A real count of one over a named set — "the only one of the six runs that finished" |
| Obituary headline (52) | A verdict borrowed from a form built to overstate | The phrase belongs to something quoted or named |

**Modifiers inside a watched phrase carry content.** "The single most important
new build" ranks that item against every other item; "the important new build"
ranks nothing. "Simultaneously X, Y and Z" claims the three hold at once; "X, Y
and Z" does not. Superlatives, rankings, simultaneity, scope words, and the
condition attached to a hedge all live inside phrasings this skill cuts.

## Annotated mode

Read `references/annotating.md`. It specifies the artifact: markup for changed
spans and edit notes, the toggle, the tic-tally table, and how to handle
passages deliberately left alone.

Rules that make the annotation useful rather than decorative:
- Quote the original verbatim in every note. An edit the reader cannot check is
  an assertion.
- Name the tic using the register's vocabulary so the reader accumulates a
  vocabulary rather than 40 unrelated opinions.
- Say why *this instance* is a tic. Explaining the category teaches nothing
  about the text in front of the reader.
- Mark what was kept and why. A pass that only flags failures teaches avoidance.
- Bundle stacked tics into one note per passage. Do not split a sentence into
  four notes to inflate the count.

## Calibration

When a draft's register is genuinely unclear, read real prose in the target
genre before editing — the author's own earlier writing, or a well-known human
writer in that domain. Human technical prose runs on, digresses, states
preferences without justifying them, and repeats a word rather than reaching for
elegant variation. Its sentences vary because the thoughts vary.

## Scope

Applies to: blog posts, READMEs, PR and commit descriptions, reports,
documentation, essays, release notes, technical explainers.

Do not apply to: fiction and poetry (different register entirely), direct
quotations, other people's text being quoted, marketing copy where the client
wants the staging, or anything where the "tic" is the author's established
voice. Ask before running this on someone else's writing rather than a draft.

## Extending

The register is a working document, not a standard. Adding to it:

1. Add the specimen to `tests/sample-tics.md`, verbatim from real prose.
2. Add a register entry: tell, why, fix, and the real before/after. Entries
   without a before/after get argued about instead of applied.
3. If the tell is lexical, add a rule to `scripts/declaude_lint.py` and confirm
   `tests/sample-clean.md` still reports zero. That file is human-written prose;
   a rule that fires on it is a bad rule, and the false-positive budget is the
   thing that keeps the linter worth running.
4. Bump `metadata.version`.

Promote a phrase to its own register entry only after it appears twice in real
drafts. Reuse is the strongest evidence that a construction is a habit rather
than a choice, and a register that grows on single sightings becomes a phrase
blocklist that misses the next paraphrase.
