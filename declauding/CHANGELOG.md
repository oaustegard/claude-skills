# declauding - Changelog

All notable changes to the `declauding` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.8.0] - 2026-08-30

### Other

- declauding 0.8.0: content preservation and a fitted staging rank (#781)

## [0.8.0] - 2026-08-30

### Added

- `scripts/declaude_diff.py` — step 5 of the workflow as an exit code. Compares a
  draft against its rewrite and reports what the edit LOST and what it ADDED.
  Membership for numbers, names, quotations, code and link targets; counts for
  superlative, scope, negation and hedge constructions. Standard library only.
  `--git PATH --ref REF` compares a working tree against a ref.
- `scripts/declaude_rank.py` and `assets/staging-axis.json` — optional stage 1.5.
  A fitted direction in sentence-embedding space, the mean of
  `embed(was) - embed(now)` over the 41 matched pairs in `register.md`, that
  sorts a draft's sentences by how staged they look. Shortlists; decides nothing.
  `--fit` refits and reports leave-one-out. Needs torch and transformers, which
  no other stage does.
- `references/preservation.md` — the measurements behind both, negatives included.

### Provenance

Written after a pass over a published post dropped a claim three times. The
linter found 1 of the 8 tics in that draft; the editor caught the three
regressions on self-review and nothing else would have.

Measured before shipping:

- Cosine similarity cannot do the preservation job. On the three real cases the
  lossy rewrite scores 0.9396 against the source and the faithful rewrite 0.9128
  — inverted on the pair that matters, and a threshold passing the first would
  flag a register-only edit at 0.8914. Paraphrase invariance is what an encoder
  is trained for. Hence the lexical design.
- Counting superlative tokens misses the case the check exists for. "The format
  that most invites staged reveals" rewritten as "more than most formats do"
  keeps `most`. Counting constructions catches it; the first cut of the regex did
  not, and missed its own motivating case in testing.
- The rank axis is 76% leave-one-out on its own pairs, and on the pre-edit post
  put all nine subsequently-edited sentences at a median rank of 13 of 53 against
  a chance median of 26 (permutation, 200k draws, p = 0.031).
- It cannot rank documents: -0.26, p = 0.46 against ten human-graded samples. A
  cruder centroid axis scored -0.10, p = 0.79. The regex scan scores -0.37 on the
  same ten and the sign is negative, because its rate measures the flat lexical
  tells and the samples carrying those stage least. No document score is exposed.

### False-positive budget

`declaude_diff.py` is silent on a file against itself, on a register-only edit
that changes no claim, and on the shipped version of the post that motivated it.
It reports both real regressions from that pass. Presence rather than frequency:
a name used twelve times and now thirteen was not invented, and reporting it is
how a guard becomes noise.

## [0.7.0] - 2026-08-29

### Added

- Entries 48 to 52, a fourth group: the confiding-essayist register. 48
  performative candour ("let's be honest", sentence-initial "Honestly,", "you
  don't have to take my word for it"), 49 stranded auxiliary reversal ("The tool
  died; the data didn't."), 50 retroactive significance ("that's why X
  mattered"), 51 totalizing designation ("that's the whole point", "the only
  release notes I trust"), 52 obituary headline ("X is dead", "long live X").
  Each has an earned column.
- Lint categories `candour`, `reversal`, `retroactive`, `totalizing`,
  `obituary`, and an obituary check on header text. "X is dead" is left alone
  inline — a dead process is a dead process — and flagged only in a header.
- `_echo_runs`, entry 26's third shape: two consecutive sentences sharing a
  five-word run that covers at least half the shorter one. Anaphora keys on the
  opening words and the triad regex on the commas; neither reaches *A shopping
  cart is an object in the system. A chat room is an object in the system.*
- `_question_runs`, entry 10 without the fragment answer: two or more questions
  in a row where at least one after the first is clipped.
- Entries 50 to 52 added to `STRUCTURAL_ENTRIES` in `declaude_review.py`. A
  retroactive grade is only visible against the passage it grades, a totalizing
  claim is earned when the set is named nearby, and an obituary headline is a
  header. 48 and 49 are lexical and stage 1 reaches them.
- Specimens for all five entries plus the two detectors in
  `tests/sample-tics.md`, with four negatives that must stay silent.

### Changed

- Entry 3 gained the staged variants of its gesture: "here's the twist / catch /
  kicker / rub", "that's the part", "my favourite part of".
- Entry 10 gained the stacked-question run.
- Entry 18 gained bare sentence-initial "Turns out"; the rule only reached "it
  turns out".
- Entry 19 gained "batteries included", "zero config" and "small enough to fit
  in your head".
- Entry 26 is now three shapes rather than two.
- `is the whole point` moved off the `aphorism` rule; entry 51 owns it.

### Provenance

Simon Willison's
[llm-cliche-highlighter](https://github.com/simonw/tools/blob/main/llm-cliche-highlighter.html)
added fifteen patterns and three structural detectors on 2026-08-27, in
[simonw/tools#322](https://github.com/simonw/tools/pull/322) and
[#323](https://github.com/simonw/tools/pull/323). Eight of the fifteen were
already covered here in some form and extended existing entries. Five had no
entry and became 48 to 52. Two of the three detectors are ported; the third,
his colon-into-a-triple, is already the comma-list half of entry 26.

Several ported regexes are narrower than the source, which is tuned for essays
rather than for technical prose. His `x-is-dead` fires on any "X is dead"; here
it fires in headers only. His echo detector needs one shared four-gram; here it
needs five words covering half the shorter sentence. His question run needs two
questions; here one of them after the first must be clipped, because two full
questions in sequence is how a person changes subject.

### False-positive budget

`tests/sample-clean.md` still reports zero. It did not on the first cut: the
question-run rule fired on *So, what's next? Is this a project that starts and
ends with DeepSeek v4 Flash?*, which is antirez changing subject, and the
clipped-question condition came out of that.

On 180,929 words of Python stdlib docstrings the five new categories fire 4
times (0.022 per 1,000 words), all four on entry 49 and all four the ordinary
ellipsis the entry names as earned. `_echo_runs` fires 36 times (0.199 per
1,000), between the existing anaphora detector at 0.077 and fragment cadence at
0.298. The first cut of that detector, keyed on a shared five-gram alone, fired
91 times on phrases like "is the same as using" inside sentences that were
otherwise unalike; requiring the run to cover half the shorter sentence is what
took it to 36. `_question_runs` fires 0 times.

`tests/sample-tics.md` now reports 167 candidates across 42 categories,
`SKILL.md --skip-quoted` 13 and `README.md --skip-quoted` 18. The extra hit on
`SKILL.md` is the `reuse` detector counting a fifth parallel table label; one of
the eighteen on the README is entry 49 on "Symmetry and antithesis are not",
which is the earned ellipsis.

## [0.6.0] - 2026-08-28

### Other

- declauding 0.6.0: entries 43-47, the register the pass produces (#779)

## [0.6.0] - 2026-08-28

### Added

- Entries 43 to 47, a fourth group: the flat-certainty register this skill's own
  output lands in. 43 flat-certainty adverb ("provably safe", "quietly dropped"),
  44 juridical register (a linter that *rules*, a default that is a *carve-out*),
  45 verification-provenance compound ("byte-identical", "mutation-checked", the
  `re-` prefix claiming a second pass), 46 privative coinage ("unguarded",
  "unwired", "vacuous"), 47 exhaustive negation ("nothing in it does X",
  "nowhere else for it to be"). Each has an earned column; none is a blocklist.
- `references/corpus.md` — the measurement behind them, the method, and what the
  numbers do not support.
- Lint categories `flat-certainty`, `juridical`, `verification`, `privative`,
  `exhaustive`, and a `corpus-register` density line reporting the draft's rate
  of the cluster's top-150 vocabulary.
- Earned-exception rows in `SKILL.md` for entries 43 to 47, and specimens plus
  four must-stay-silent negatives in `tests/sample-tics.md`.
- Entry 47 added to `STRUCTURAL_ENTRIES` in `declaude_review.py`: an exhaustive
  negative is earned when its scope is named, and only the surrounding sentences
  say whether it is. 43 to 46 are lexical and stage 1 reaches them.

### Fixed

- `load_register` in `declaude_review.py` ended an entry only at the next
  *numbered* heading, so selecting the file's last entry pulled the trailing
  "Quick self-check" section into the prompt with it. Any `#`/`##` heading now
  closes the block. Latent until 47 became the last entry.

### Provenance

Louis Abraham's [load-bearing](https://github.com/louisabraham/load-bearing)
clusters GitHub pull request descriptions by vocabulary — 461,121 descriptions,
85 whole weeks, 2025-01-06 to 2026-08-17, ten clusters, no time parameter in the
fit. One cluster is 0.70% of the first eight weeks and 39.5% of the last four,
rising 1.24 points a week. Its highest-lift words are `load-bearing` 39x,
`plainly` 34x, `quietly` 30x, `refusal` 28x, `re-derived` 27x, `asserted` 25x,
`nobody` 25x, `genuinely` 24x, `outright` 23x, `byte-identical` 23x.

That is not the slop vocabulary of entry 20. It is the register this skill aims
at, and it is now the fastest-growing way of writing a pull request description
there is. A pass that removes 42 staging tics and lands here has traded one
detectable shape for another.

### False-positive budget

`tests/sample-clean.md` still reports zero. On 115,920 words of Python stdlib
docstrings the five new categories fire 18 times (0.16 per 1,000 words), ten of
them on `silently`. `is simply` was cut from the adverb rule for scoring two of
those and not appearing in the corpus list at all. `unsatisfiable` was cut from
the privative rule as a SAT term.

The `corpus-register` line is a register locator and not an authorship detector.
load-bearing's own human-written README scores 1.51 per 100 words of body prose,
above this skill's `SKILL.md` at 1.47, on `nothing` x9, `carries` x3, `alone` x2,
`never` x2 and `half` x2. Human stdlib docstrings run 0.08 median and 0.32 at
worst over 46 chunks of 2,500 words. The note on the line says this, because a
reader who takes it for a detector will cut `nothing` and `measured` out of
correct sentences.

`tests/sample-tics.md` now reports 136 candidates across 35 categories,
`SKILL.md --skip-quoted` 12 and `README.md --skip-quoted` 15 — the README's three
new `locator` hits are the repository's name, which entry 19 lists as a metaphor
and `--skip-quoted` cannot tell from a proper noun.

## [0.5.1] - 2026-08-23

### Other

- declauding 0.5.1: bring the README current, scope the header check (#772)

## [0.5.1] - 2026-08-23

### Changed

- README brought current. It described 37 entries and two register halves, which
  was already stale by one before this release — 0.4.0 added entry 38 without
  updating it. Now three groups, 42 entries, a table for 39 to 42, refreshed
  corpus counts, and the provenance of the new block.
- Nominalized-header check scoped to a prepositional tail ("Authorship in a
  sourced child") or a two-word modifier plus abstraction ("Spawn availability").
  A bare one-word nominalization is a legitimate label for a term the document
  defines, and the first cut fired on this skill's own `## Overcorrection` and
  `## Calibration`.

### Added

- Earned-exception rows in `SKILL.md` for entries 39 to 41, including the
  one-word-label carve-out the header check now honors.

## [0.5.0] - 2026-08-23

### Other

- declauding 0.5.0: entries 39-42 (#771)

## [0.5.0] - 2026-08-23

### Added

- Entry 39, welded epigram — a maxim joined to a fact with "and" or "so", inside
  one sentence. Entry 12 only catches the paragraph-final form.
- Entry 40, spec-ese — demonstrative subjects, reflexive emphatics, and latinate
  state verbs ("idles", "holds no", "awaiting input") for a program doing nothing.
- Entry 41, nominalized header — the standard overcorrection from entry 7.
  Fleeing a verdict header into an abstraction passes entry 7's regex and fails
  its table-of-contents test.
- Entry 42, contents-list standfirst — "X, plus the Y the docs leave out".
- `spec-ese` lint category, three new `aphorism` and two new `announce` patterns,
  and a nominalized/gerund header check.
- Two self-check questions covering the welded epigram and the read-aloud test.

Diagnosed on a create_session reference artifact whose four section headers were
all rewritten from verdict-shaped into nominalized by a single declauding pass,
after which the linter reported the document clean.

## [0.4.0] - 2026-08-21

### Other

- declauding 0.4.0: entry 38, announce-then-deliver (#769)

## [0.4.0] - 2026-08-21

### Added

- **Entry 38, announce-then-deliver.** A counted noun-phrase label standing in
  front of the content it names: "One factual note, not fixed:", "Two things I
  did not do.", "One judgment call left alone." The label carries nothing the
  content does not, and the fix is usually to delete it and start with the
  thing. Four `announce` rules in `declaude_lint.py` reach the regular forms;
  the bare "One note:" shape is left alone because a pattern for it over-fires
  on legitimate list intros.

  Found by an author flagging it in this skill's own output — an annotated
  register pass whose frame prose used the shape nine times, twice as a section
  header, in a document whose central finding was bad headers. None of the
  existing entries covered it: entry 5 is a placeholder *in* the subject slot,
  entry 17 narrates the writer's procedure rather than labelling the content,
  entry 29 is the bulleted cousin, and the `staging` rule at
  "announces a list before giving it" targets demonstratives (`Here is what X:`)
  rather than counted labels.

  Fired before trusting: 6 of 6 specimens caught, 6 of 6 negatives silent
  (including luria's "One decision, one thing." and the corrected form "One note
  I did not fix:"). Dropping the qualifier requirement from the first rule
  over-fires on the aphorism, which is what holds the precision. Zero new hits
  across all four existing test corpora.

### Fixed

- Register entry 37, *Dressed metaphor*, was written `# 37.` where every other
  entry is `## N.`, so it rendered as an H1 and fell out of any `^## [0-9]`
  count. Unrelated to the above; picked up while editing the file.

## [0.3.0] - 2026-08-17

### Other

- declauding v0.3.0 — two stages, folded from #762, #763 and the recall pass (#764)

## [0.3.0] - 2026-08-17

Three branches folded into one version: a recall pass on the linter, the
structural-pass work from #762, and the guard work from an unmerged 0.2.2. They
were three answers to the same complaint and shipping them separately would have
meant three 0.3.0s.

The shape that results is two stages. Stage 1 is `declaude_lint.py`, which now
sees HTML and detects triads, reuse and repetition. Stage 2 is
`declaude_review.py`, which sends only the slots regex cannot judge — headers,
opening sentence, closers, isolated lines — to a model. Neither subsumes the
other: stage 1 over-flags a comma that belongs to a citation, stage 2 reads it in
context; stage 1 finds a verdict header every time, stage 2 finds the aphoristic
closer no regex reaches.

Measured by scoring the linter against a hand annotation of the same 900-word
draft: 31 candidates, 24 of them real, against 68 instances a full
sentence pass found. Recall 35 percent, precision 77. After this release the same
draft reports 60 candidates, 45 real, for 66 percent recall at 90 percent
precision, with `tests/sample-clean.md` still at zero.

Every miss had the same cause. The rules were closed vocabulary lists, and real
prose used a word that was not on the list: the participle rule listed
`highlighting|underscoring|emphasizing` and walked past `hitting`, `genuinely`
had a six-word whitelist and walked past `genuinely considered`, and
`the (part|thing) that` required `matters|counts|transfers` and walked past
`the thing that made it slow`. Widening those to shapes rather than words
recovered 21 instances at zero cost to the clean corpus.

### Added

- **Forced triad detection**, category `triad`. Entry 26 had no rule at all, and
  it was the largest single category in the evaluation draft at seven instances.
  Two detectors: a comma list with negative lookaheads for relative pronouns, and
  an anaphora form covering three consecutive sentences or three consecutive
  clauses opening on the same two words. The anaphora form catches
  `It was a message. It was a permission slip. It was an out.` and
  `something to steer toward, something to be measured against, something to fear`,
  neither of which the comma rule can see. The new earned-exception row for entry
  26 is the guard on it, and entry 27 read in the right direction is the guard on
  the repetition statistics below.
- **`reuse` block.** Groups the hits already found and reports any construction
  used more than once, with its line numbers. No new rules, no new scanning. The
  evaluation draft used `the part that` three times and the linter previously
  reported three unrelated hits.
- **Per-instance em-dash gotcha**, category `em-dash`: a dash whose clause runs to
  the end of the sentence, which is the drum-roll shape rather than the aside.
  Density was already reported; the individual dashes were not. Entry 16 gains a
  demotion test: replace the dashes with commas, and see whether the aside
  survives. A beat does not, because the beat was the punctuation.
- **Document-level repetition statistics**: repeated sentence openings and
  repeated content trigrams. Uniformity is the tell, and it is measurable without
  a reference corpus, which is why this is a statistic rather than a model.
- Widened rules for participle tails at sentence end, `genuinely` as a
  self-grade, `the part/thing that`, `Nobody` claims, `Not X.` fragments,
  `represents a kind of X`, sentence-initial from-X-to-Y, `Here is what X:`,
  `which was this:`, `that's not quite right`, a doubled adverb, and
  `the entire architecture of the thing`.
- Specimens for all of the above in `tests/sample-tics.md`, which now reports 91
  candidates across 28 categories, up from 62 across 24.

Stage 2, from #762:

- `scripts/declaude_review.py`. Extracts headers, opening and closing sentences,
  and isolated one-sentence paragraphs, then judges only those against the
  structural entries in `references/register.md`. Gemini or Anthropic key,
  `--emit-prompt` fallback, `--slots` for extraction only. Against the structure
  fixture across four runs it caught the subtitle, both coy headers and the
  aphoristic closer every time, with zero false positives on the eight clean
  slots — including `EU AI Act, Article 50`, where the comma belongs to a
  citation and stage 1 flags it.
- Entry 26 added to its register slice. Stage 1 detects a triad deterministically
  but cannot judge whether the content had three things, and a closer is where
  the padded ones land.
- `tests/sample-structure.md` and `tests/sample-structure.html`, built from
  headers that shipped past a clean report.
- Workflow step 2b, with the warning not to run stage 2 in the context that wrote
  the draft. A model reviewing its own prose is the actor that chose the words.

From the folded 0.2.2 branch:

- Earned exceptions now covers 17 of the 37 entries, in two tables, with the
  entry number on every row. It covered 5, all from the first block, while the
  second block carried its exceptions as prose buried inside individual entries.
- The paragraph naming what hides inside a watched phrase: superlatives,
  rankings, simultaneity, scope words, and the condition attached to a hedge.
- A dropped-claim check in workflow step 5 and as self-check 11, asked as a
  question and answered claim by claim. A dropped superlative leaves the
  paragraph looking intact, which is why a read-through misses it.
- `Earned when` notes on entries 25, 27, 28, 29 and 34, which had none.

### Fixed

- A one-line paragraph that is a line of dialogue reported as a drama line break.
  `tests/sample-clean.md` now carries a four-line exchange as the regression
  control and still reports zero.
- `aphorism` was missing from `CATEGORY_ORDER`, so its hits sorted after the
  document-level density block instead of with the sentence-level tells.
- The `reuse` counter treated two rules matching the same span as two uses.
  Deduplicated on offset, so a genuine repeat on one line still counts twice.
- Entry 11 explained itself with "the negation-first shape wearing a costume",
  which is entry 37. The skill cannot ban a shape in one entry and use it in
  another. (From the folded 0.2.2 branch.)
- `declaude_lint.py` scanned markdown headings only, so every header rule was
  silent on an HTML draft: three thesis-shaped headers, a comma-clause header and
  a coy header shipped past a clean report. HTML is now flattened before
  scanning, and masthead `.subtitle` / `.eyebrow` / `.post-meta` elements are
  scanned as headings, because a subtitle is a header by every test that matters.
  Step 2 also now says to lint every string that reaches the reader, since a
  builder taking the subtitle as a CLI argument hides it from any file scan.
  (From #762.)

### Changed

- Workflow step 2 no longer claims the linter misses every structural tic, which
  stopped being true with this release. It now says which third it does miss:
  staged paragraph shape, staged closers, dressed metaphor, and every earned
  exception in the tables. That third is the expensive one and it stays with the sentence pass.
- Step 2 shows `--skip-quoted` alongside the bare invocation. The evaluation run
  did not use it and spent two of its seven false positives on the draft's own
  quoted specimens.

### Not shipped

A TF-IDF classifier over model-written and human-written corpora was considered
and rejected. Bag-of-n-grams is a strictly weaker feature space than regex plus
the positional checks already here, so it can surface no tic class this cannot;
its output is a score with no span and no register entry, which does not fit a
tool whose contract is candidates a reader can check; and it would learn "not
this author" rather than "machine-shaped", which conflicts with the rule that the
author's own writing outranks the register. It remains useful offline as a rule
miner: train it, read the coefficients, hand-pick the real ones, ship regexes.
The document-level repetition statistics above are the part of that idea that
survives, and they need no corpus and no training. The model-shaped part of the
problem it was aimed at is answered by stage 2 instead, which sends slots to a
model that can name the tic and cite the entry rather than returning a score.

A widened bolded-bullet rule was also cut. It caught one real instance in the
evaluation draft and fired seven times on this skill's own "Leave these alone"
list, where the labels are exactly the real index the folded branch wrote into
entry 29's earned form. The rule now tests for the restatement with a
backreference, which is entry 29's actual tell, and the looser shape stays with
the sentence pass. Two branches reached that boundary independently, one by
reading the register and one by watching a rule misfire.

## [0.2.1] - 2026-08-16

### Other

- declauding 0.2.1 — register entry 37, dressed metaphor (#761)

## [0.2.1] - 2026-08-16

### Added

- Register entry 37, dressed metaphor: a figure of speech standing in for a
  mechanism you could have named ("wearing the costume of", "dressed up as",
  visceral imagery on a mundane observation). Entry 6 covers the locational
  special case; this is the general one. The entry states that no regex reaches
  it, and both its specimens shipped past a clean lint report, one of them into
  a patch headed for another project.
- Lint rule for mid-paragraph `X is A, not B`. The existing rule anchors on
  end-of-line, so it caught the construction only as a closer.
- Three specimens for entry 37 in `tests/sample-tics.md`, which now reports 62
  candidates across 24 categories. Two of the three are invisible to the linter
  by design, which is the entry's point.

## [0.2.0] - 2026-08-16

### Other

- declauding v0.2.0 — absorb the encyclopedic and chatbot register from humanizer (#760)

## [0.2.0] - 2026-08-16

Absorbs what a comparison against [blader/humanizer](https://github.com/blader/humanizer)
v2.9.1 (MIT) showed this skill was missing. Humanizer packages the Wikipedia AI
Cleanup project's *Signs of AI writing*; its coverage of encyclopedic and chatbot
slop is broader than the two vocabulary entries this register had.

Measured before porting: a probe of 19 humanizer specimens produced 2 candidates
from `declaude_lint.py`, neither for the right reason. It now produces 33 across
13 categories.

### Added

- Register entries 24 to 36, in a second block that names itself as a different
  family from the staging mechanisms: copula avoidance, participle tail, forced
  triad, elegant variation, false range, inline-header list, typographic tells,
  chatbot residue, filler and hedge stacking, speculative gap-filling,
  diff-anchored documentation, subjectless fragment, predicate-position
  hyphenation. The block states that several of them are phrase lists rather than
  mechanisms and will leak.
- "Do not invent specifics" in `SKILL.md`, and a fourth failure mode in workflow
  step 5. De-vaguing a sentence is how a register pass fabricates, and the skill
  previously warned only against changing claims, not against supplying a name or
  number the source does not have.
- Voice-sample precedence. A sample of the author's writing outranks every rule
  here, including the em-dash density guard.
- Three invocation modes: pasted text, file, and embedded (another agent calling
  this as one step, which returns text and nothing else).
- "Leave these alone" section: the positive signals of human writing, and the
  things that are not tells on their own.
- Linter rules for the new lexical entries, plus Title Case heading detection and
  document-level curly-quote and emoji counts. Eleven new categories.
- 13 new specimens in `tests/sample-tics.md`, which now reports 58 candidates
  across 23 categories. `tests/sample-clean.md` stays at 0.

### Changed

- Content preservation now licenses structural rearrangement: every claim
  survives, but paragraphs may merge or split and depth need not be uniform.

### Fixed

- `--skip-quoted` blanked spans before lines, so a bold marker inside a table
  cell could mis-pair the italic regex across lines and leave that row's
  specimens visible. It also never blanked code, so a tell quoted in backticks
  reported as a hit. Fenced blocks and inline spans are blanked now, and the
  line pass runs first.
- The emoji count included U+2190 to U+21FF and U+2300 to U+23FF, so a plain
  arrow or a technical symbol in ordinary prose reported as decoration.
  Narrowed to the emoji-presentation blocks.

## [0.1.1] - 2026-08-16

### Other

- declauding v0.1.1 — add README, --skip-quoted, and the fixes that missed #755 (#756)

## [0.1.1] - 2026-08-16

### Added

- `README.md`. Missing from 0.1.0: the commits carrying it landed on the branch after the merge and were lost when the branch was deleted.
- `--skip-quoted` on the linter. Blanks blockquotes, table rows, `*italic*` spans and `<q>` elements while preserving line numbers, so a document that quotes bad prose as specimens does not report its own examples. Handles italics that wrap across lines.

### Fixed

- The `earns/wants/demands` agency rule fired on ordinary second-person prose ("if you want the noise"). Added a lookbehind for personal pronouns.
- Density checks counted headings, table rows and list bullets as sentences, inflating fragment density on any structured document.
- The skill's own prose failed its own linter: two coy headers, four `X, not Y` closers, one abstraction-agency subject, and a negation-first closer sitting directly beneath the sentence explaining why negation-first closers are a tic.

## [0.1.0] - 2026-08-16

### Added

- Initial release. Two modes: clean rewrite (default) and annotated HTML diff.
- `references/register.md`: 23 entries grouped by mechanism, each with surface tell, why, fix, and a before-and-after from a real published draft. Grouping is by mechanism rather than phrase because phrase blocklists miss the next paraphrase.
- `references/annotating.md`: spec for the annotated diff.
- `assets/annotated.template.html`: self-contained output template. No build step, no CDN, opens from `file://`.
- `scripts/declaude_lint.py`: stdlib-only scan for lexical tells plus header shape, one-line-paragraph beats, fragment runs, em-dash density and sentence-length monotony. Exits 1 on candidates.
- `tests/sample-tics.md` (29 candidates, 12 categories) and `tests/sample-clean.md` (0). The clean corpus is human-written prose and holding it at zero is the linter's design constraint.
- Overcorrection guard and earned-exception table in `SKILL.md`.
- Workflow steps 1 and 6: read the whole piece first, and report contradictions separately rather than fixing them silently.

### Other

- declauding v0.1.0 — LLM prose tics in, human technical prose out (#755)