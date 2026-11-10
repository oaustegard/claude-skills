# declauding

declauding is a skill for Claude and other coding agents. It rewrites a draft
that reads as model-written into the plain technical prose that a person would
have written. Before handing the text back, it compares the rewrite with the
draft for any number, name, quotation, hedge or ranking that the edit dropped or
added, and resolves what it finds. Given text, it returns either the rewritten text or an annotated HTML file that shows each edit
beside the original and gives the reason for it.

"Register" here means the style a piece of prose is written in. The register
catalogue, [`references/register.md`](references/register.md), lists 56 tics
that mark prose as model-written. [`SKILL.md`](SKILL.md) holds the workflow,
[`references/exceptions.md`](references/exceptions.md) lists when a flagged shape
should stay, and [`CHANGELOG.md`](CHANGELOG.md) holds the version history.

## Installing and calling it

Install it from [oaustegard/claude-skills](https://github.com/oaustegard/claude-skills)
like any other skill, or run the scripts in `scripts/` directly. An agent with the
skill loads it before drafting prose that someone else will read, and also when
asked to "declaude", "de-slop" or "humanize" a text. Ask for the annotated version
by name; the clean rewrite is the default.

## Output modes

| Mode | Output | Use for |
|---|---|---|
| **clean** (default) | The rewritten text | Fixing your own draft before publishing |
| **annotated** | One self-contained HTML file: rewritten text, every changed passage marked, each with the original verbatim, the tic name, and why | Reviewing someone else's draft, teaching the register, arguing about a specific edit |

The annotated file has a toggle that hides the marks, so one file holds both the
review and the clean result. It opens from disk with no build step, CDN or
server.

How the skill is called changes what it returns. Pasted text gets the rewrite and
a short list of changes. A file is rewritten in place, with a summary in the
conversation. When another agent calls it as one step of a larger job (embedded
mode), it returns the final text with no commentary.

## Workflow

`SKILL.md` has the full steps. In short:

1. Read the whole draft before editing, and note any place where it contradicts
   itself.
2. State the draft's point in one sentence. If it has none, get one from the
   author and rebuild the draft around it instead of repairing sentences.
3. Run the linter, and optionally the sentence ranking, then the structural
   review in a context that did not write the draft (a subagent or a fresh
   session).
4. Go through the draft sentence by sentence, asking of each one whether it
   states a finding or builds up to it for effect (the sentence-level test), then
   check headers,
   paragraph breaks and closers.
5. When the draft describes something that just changed, have a reader who never
   saw the old version read it.
6. Run the preservation diff, and report contradictions to the author rather
   than fixing them.

## The register

Each entry in the catalogue gives the surface tell, why it marks model prose, the
fix, and a before-and-after from real text. Most entries describe a mechanism
rather than a phrase, because a phrase list misses the next paraphrase. Entries
are numbered in the order they were added, so a family does not always occupy a
contiguous range.

| Entries | Family | What the prose is doing |
|---|---|---|
| 1–23, 37–42 | Staging | Building the sentence so the reader feels a finding arrive instead of being told it |
| 24–36 | Encyclopedic and chatbot | Running on defaults with nothing staged |
| 43–47 | Flat certainty | Letting an adverb, a compound word or an absolute negative stand in for evidence |
| 48–52 | Confiding essayist | Staging aimed at the reader's trust |
| 53–56 | Compressed syntax | Packing a claim into fewer words than a reader can parse |

### Staging (entries 1–23 and 37–42)

The commonest staging tics:

| # | Tic | Example |
|---|---|---|
| 2 | Negation-first reveal | *It is not a wrong answer. It is a non-answer.* |
| 3 | Significance designation | *It is the leg that answers the actual question.* |
| 4 | Abstraction agency | *Median hides it.* / *The table shows it.* |
| 5 | Deferred noun | *Five of those six rows are one cluster. The sixth is not.* |
| 7 | Coy or thesis-shaped header | *What "exhausted" means* / *The one gap that does clear the bar* |
| 11 | Straw-man knockdown | *"It thinks twice as long" is the obvious reading, and it is wrong.* |
| 12 | Aphoristic closer | *It is the kind of number that looks like evidence and is not.* |
| 15 | Fragment cadence | *Six legs. One GPU, one server build, one sampler, one question set.* |
| 37 | Dressed metaphor | *That is information loss wearing the costume of a style fix.* |
| 38 | Announce-then-deliver | *One factual note, not fixed: X and Y both assert what people generally do.* |

Entries 39 to 42 came from an API reference page, where the prose describes a
system rather than arguing a point. The other staging entries rarely fire on
reference prose, so these four cover it:

| # | Tic | Example and what is wrong with it |
|---|---|---|
| 39 | Welded epigram | *…are dropped, so a child never carries a grant its parent lacks.* A maxim attached to a fact with *so* |
| 40 | Spec-ese | *That child holds no repository and waits for input.* Worded like a standards document rather than a person explaining |
| 41 | Nominalized header | *GitHub authorship in a sourced child.* A header turned into a noun pile |
| 42 | Contents-list standfirst | *The parameter surface, plus the behavior the schema leaves out.* An opening line built as one noun phrase plus another, listing the contents |

Entry 41 is the overcorrection of entry 7. A thesis-shaped header rewritten into
an abstraction passes the linter's header rule and is still not a plain label.

### Encyclopedic and chatbot patterns (entries 24–36)

These come from the Wikipedia AI Cleanup project's *Signs of AI writing*, by way
of [blader/humanizer](https://github.com/blader/humanizer). They appear in
encyclopedic summary, product copy, README boilerplate and pasted chat:

| # | Tic | Example |
|---|---|---|
| 24 | Copula avoidance | *Gallery 825 serves as the exhibition space and boasts 3,000 square feet.* |
| 25 | Participle tail | *…resonates with the region's beauty, symbolizing bluebonnets, reflecting the community's connection.* |
| 26 | Forced triad | *keynote sessions, panel discussions, and networking opportunities* |
| 27 | Elegant variation | *The protagonist… the main character… the central figure…* |
| 28 | False range | *from the Big Bang to the cosmic web, from stars to dark matter* |
| 29 | Inline-header list | *- **Performance:** Performance has been enhanced through optimized algorithms.* |
| 31 | Chatbot residue | *I hope this helps! Let me know if you'd like me to expand on any section.* |
| 32 | Filler and hedge stacking | *It could potentially possibly be argued that…* |
| 33 | Speculative gap-filling | *…not publicly available, suggesting she maintains a low profile.* |
| 34 | Diff-anchored documentation | *This function was added to replace the previous approach…* |
| 35 | Subjectless fragment | *No configuration file needed. The results are preserved automatically.* |

Several of these are phrase lists rather than mechanisms, as is the slop
vocabulary of entry 20 (*delve*, *tapestry*, *testament to*). The catalogue
states that as a limitation and keeps them because they are cheap to check.

### Flat certainty (entries 43–47)

A declauding pass tends to land in this register once the staging is gone. The
target is certainty with evidence behind it, and these entries catch certainty
that has none. `references/corpus.md` has the measurement behind this family.

| # | Tic | Example | Rewrite |
|---|---|---|---|
| 43 | Flat-certainty adverb | *The retry is provably safe.* | *The retry is idempotent: the handler keys on the request id.* |
| 44 | Juridical register | *The guard refuses any caller without standing.* | *The guard returns 403 when the token has no `write` scope.* |
| 45 | Verification-provenance compound | *The rewrite is byte-identical and mutation-checked.* | Name the check that ran and its result |
| 46 | Privative coinage | *Three of the paths are unguarded.* | *Three of the paths have no length check before the index.* |
| 47 | Exhaustive negation | *Nothing in the fit varies with time.* | *The fit has one parameter per cluster and none per week.* |

### Confiding essayist (entries 48–52)

In these entries the staging is aimed at the reader's trust:

| # | Tic | Example |
|---|---|---|
| 48 | Announced candour | *Let's be honest: I won't pretend the first run was clean.* |
| 49 | Stranded auxiliary | *The tool died; the data didn't.* A sentence that ends on a bare auxiliary for the beat |
| 50 | Retroactive significance | *That's why being able to open the environment mattered.* |
| 51 | Totalizing designation | *That's the whole point of the format.* / *the only release notes I trust* |
| 52 | Obituary headline | *Peer code review is dead* |

### Compressed syntax (entries 53–56)

These pack a claim into fewer words than a person would use, and the reader pays
for the saving in parse effort. The fix usually makes the sentence longer.

| # | Tic | Example |
|---|---|---|
| 53 | Noun stack | *New tests for paths with spaces, dry-run write prevention, and idempotent config reinstalls.* |
| 54 | Verbed noun | *…is quietly eating its own reader-patience budget — footnote it.* |
| 55 | Dropped *that* | *the others check behaviour the old code never reached* |
| 56 | Distant verb | *All five expression shapes — attribute access, subscript, calls, nested calls, string literals — leave current on NAME('b')* |

These four need a parse, which the linter does not do. Look for them in the
sentence pass.

## The linter

```sh
python3 scripts/declaude_lint.py DRAFT.md            # human-readable
python3 scripts/declaude_lint.py DRAFT.md --json     # machine-readable
python3 scripts/declaude_lint.py - --quiet-slop      # stdin, without the slop-vocabulary hits
python3 scripts/declaude_lint.py DOC.md --skip-quoted # ignore quoted specimens
```

The linter reads Markdown, plain text or HTML and uses only the standard library.
It flags the tells that can be matched as words or phrases, with line numbers and
categories. It also checks the shape of the text: header form, Title Case
headings, one-line paragraphs used as beats, fragment runs, forced triads (as a
comma list, as repeated openings, or as consecutive sentences built on one
skeleton), runs of
stacked rhetorical questions, inline-header bullets whose label restates the
item, em dashes that set up a closing clause, em-dash density overall, repeated
sentence openings and phrases, curly-quote and emoji counts, and sentence-length
monotony. HTML is flattened first, so `<h1>`–`<h6>` headings and `.subtitle`,
`.eyebrow` and `.post-meta` elements reach the header rules.

`--skip-quoted` blanks blockquotes, table rows, code (fenced and inline),
`*italic*` spans and `<q>` elements while keeping line numbers intact. Use it on
any document that quotes bad prose as a specimen, this README included.

The `corpus-register density` line is not a tell. It reports how many of the
draft's words, per 100, come from the 150 words most over-represented in the
GitHub pull request cluster described under [Provenance](#provenance), words such
as `nothing` and `measured`. That locates the register and says nothing about who
wrote the draft. Python standard-library docstrings score 0.08 at the median and
0.32 at worst. This skill's own files score between 1.1 and 3.2. The
human-written README of the repository the word list came from scores 1.51, which
is above this skill's `SKILL.md`. Above roughly 1.0, read entries 43 to 47 and
check that each flagged word has evidence behind it. Do not cut `nothing` or
`measured` on sight.
[`references/corpus.md`](references/corpus.md) has the figures and their limits.

The `reuse` block groups the hits the scan already produced and reports any
construction that the draft uses more than once. It adds no rules and costs
nothing to run. Reuse is the strongest evidence available that a construction is
a habit rather than a choice: one `the part that` is emphasis, and three is a
tic.

A hit is only a candidate and still needs the
sentence-level test. No regex reaches a staged paragraph shape or a staged
closer, so a clean report is not evidence that the draft is clean. It exits with
1 when it finds candidates and 0 when it finds none, so it can run as a
pre-commit hook.

## Structural review

```sh
python3 scripts/declaude_review.py DRAFT.md
python3 scripts/declaude_review.py DRAFT.md --emit-prompt   # print the prompt instead
python3 scripts/declaude_review.py DRAFT.md --slots         # show what it extracts
```

The review extracts the parts of a draft that regex cannot judge (headers, the
opening sentence, each closing sentence, isolated one-sentence paragraphs) and
sends only those to a model, together with the catalogue entries about headers,
openers, closers and paragraph shape. Sending those parts rather than the whole
document keeps the review cheap enough to run on every draft. It calls Gemini
when `GEMINI_API_KEY` is set and Claude when `ANTHROPIC_API_KEY` is set. With
neither, it prints the prompt for an agent to answer.

The linter and the review catch different things. The linter finds a
thesis-shaped header deterministically, and its forced-triad rule also
flags the comma list in a citation, which is a false positive. The model reads the list in
context, where it can tell a citation from a triad, and it finds the aphoristic
closer, which no regex reaches. Run the
review in a context that did not write the draft.

## Model profiles

`references/models/` has a file for each model family: Opus 5 and 5.5, Opus 4.6
and 4.8, Sonnet 4.6 and 5, Haiku 4.5, and Fable 5.1. Each file says what that
model's drafts tend to carry and how the model goes wrong when it runs the pass
itself. The agent reads the profile of the model that wrote the draft, when that
is known, and its own. The profiles draw on the model-register-drift run in
[`oaustegard/experiments`](https://github.com/oaustegard/experiments/tree/main/model-register-drift),
where six models wrote the same post with no voice instruction. Opus 5 was the
third-cleanest of the six on this linter, and the only model whose staging score
in the blind review was above zero. Its profile therefore tells the editor to
expect a clean lint report and to spend the pass on headers and paragraph
closers. Opus 5.5 has not been sampled for staging
and uses the Opus 5 profile.

## Preservation diff and sentence ranking

`scripts/declaude_diff.py` compares a draft with its rewrite and reports what the
edit lost and what it invented. It checks numbers, names, quotations, code and
link targets by presence, and it counts superlative, scope, negation and hedge
constructions. It counts constructions rather than words because a rewrite can
keep a word and lose its meaning: turning "the format that most invites staged
reveals" into "more than most formats do" keeps *most* and drops the ranking.
`--git PATH` compares the working tree with a ref, which is the form CI needs.
Like the linter, it uses only the standard library.

```sh
python3 scripts/declaude_diff.py SOURCE.md REWRITE.md
python3 scripts/declaude_diff.py --git blog/post.html --ref HEAD~1
```

An embedding cannot do this check. On three real cases the lossy rewrite had a
*higher* cosine similarity to the source than the faithful rewrite did, because
encoders are trained to ignore paraphrase.

`scripts/declaude_rank.py` sorts a draft's sentences from most to least staged,
as a shortlist for the sentence pass:

```sh
python3 scripts/declaude_rank.py DRAFT.md --top 15
```

It projects each sentence onto a fixed direction in the embedding space of
`all-MiniLM-L6-v2`. The direction is the mean difference between the staged
and plain sides of 41 before-and-after pairs in the catalogue.
Both sides of a pair say the same thing, so the direction tracks staging rather
than topic. Holding out one pair at a time, it put the staged side higher 76% of
the time, against 50% for chance. On one real editing pass, the nine sentences
that the pass changed had a median rank of 13 out of 53 (p = 0.031), and the
regex scan had found one of the nine. It ranks sentences only and gives no score
for a whole document. It needs torch and transformers.

It uses a fitted direction rather than a model judge because a judge needs a
prompt, and the rankings that two reasonable wordings of the same judging
question gave the same ten texts correlated at -0.50. [`references/preservation.md`](references/preservation.md)
has every number. It reports the negative results as well.

## False positives

`tests/sample-clean.md` is human-written prose and must lint to zero.
`tests/sample-tics.md` is a collection of real specimens and currently reports 173
candidates across 42 categories. Counts marked "reviewed" below are hits that were
read one by one and left in place, each for a reason given here.

```sh
python3 scripts/declaude_lint.py tests/sample-tics.md    # 173 candidates
python3 scripts/declaude_lint.py tests/sample-clean.md   # 0
python3 scripts/declaude_lint.py SKILL.md --skip-quoted  # 8, reviewed
python3 scripts/declaude_lint.py README.md --skip-quoted # 4, reviewed
python3 scripts/declaude_diff.py tests/sample-clean.md tests/sample-clean.md  # 0
python3 scripts/declaude_lint.py tests/sample-structure.html   # 10, HTML path
python3 scripts/declaude_review.py tests/sample-structure.md --slots  # 14 slots
```

The hits counted above were each read and left in place: proper names such as
`load-bearing`, lists with three real items, deliberate repetition of the kind
entry 27 protects, and the density line, which is not a tell.

Several rules are tuned down to keep `sample-clean.md` at zero, so the linter
misses some real coy headers and some real inline-header bullets. A linter that
fires on good writing gets ignored, and an ignored linter catches nothing. The
skill's own files are a second check: a rule that once fired seven times on
`SKILL.md` was treated as a bad rule.

## Overcorrection

The failure mode of this skill is prose stripped of confidence, rhythm and
personality until every sentence is the same length and the writer has no
opinions. That is worse than the tics, so `SKILL.md` writes the guard down rather
than leaving it to judgment:

- Keep certainty that has evidence behind it. *Class imbalance breaks the metric
  before overfitting does* is flat and certain, and should stay both.
- Keep first-person judgment. *I did not expect the overlap to survive a 3x range
  in bits per weight* is specific, falsifiable and human.
- Do not compress what remains. A rewrite that is shorter and takes longer to
  parse is worse than the draft (entries 53 to 56).
- Let sentence length vary with the content. Uniform length is a tell of its own.
- Keep digression and mild informality, and cut symmetry and antithesis.

Every entry fires on a shape, and sometimes the shape carries a claim. Cutting it
then removes content while appearing to remove only style.
`references/exceptions.md` lists, for each shape, when it is banned and when it is
earned. A phrase that a rule flags can hide a superlative, a ranking, a claim that
several things hold at once, a scope word, or the condition attached to a hedge.
*X rather than Y* is legitimate when the reader was already holding Y, and staged
when the writer supplied Y to reject it.

## Contradictions found while editing

Step 1 of the workflow is to read the whole piece before editing anything, and
the last step is to report contradictions to the author instead of fixing them.

A sentence built for shape is more likely than its neighbours to be wrong. In the
benchmark post that entries 1 to 23 came from, two significance designations
(*the leg that answers the actual question*, *the variable the fits exist to
test*) each pointed at the wrong thing, and the post contradicted both within two
paragraphs. Finding those was worth more than the register pass.

## Extending

The catalogue is a working document. To add to it, put the specimen in
`tests/sample-tics.md` verbatim, write the entry in `references/register.md` with
a real before-and-after, add a rule to `scripts/declaude_lint.py` if the tell can
be matched as words, confirm that `tests/sample-clean.md` still reports zero, and
bump `metadata.version` in `SKILL.md`.

Add a phrase to the catalogue only after it has appeared in two real drafts,
since a single sighting can be a choice.

## Invented specifics

The fix for a vague sentence is a specific one, and that is how a register pass
ends up fabricating. *Experts believe it plays a crucial role* may become *the
sources here do not say who studies it*, or it may be cut. It may not become
*researchers at Lanzhou University*. No name, number, date, quote or citation
enters the rewrite unless the source or the author put it there. Stance and
opinion are voice and stay. A factual claim the author did not make is a defect
even when the result reads more human.

## The author's writing sample

When the author supplies a sample of their writing, the skill matches its habits
and lets them override the rules here, the em-dash density check (entry 16) among
them. Scrubbing a tell that is the author's real voice makes the text less like
them without making it any more human.

## Scope

This skill edits register, checks that the edit kept the draft's claims, and
reports contradictions it finds in the draft. It does not check claims against
outside sources or improve the analysis. It is not for fiction, poetry, code or
quoted text.

## Provenance

| Entries | Source |
|---|---|
| 1–23 | A register pass on an external benchmark post, 2026-08-16 |
| 24–36 | [blader/humanizer](https://github.com/blader/humanizer) v2.9.1 (MIT) |
| 37, 38 | Found during this skill's own passes, versions 0.2.1 and 0.4.0 (claude-skills #761, #769) |
| 39–42 | The reference page for a `create_session` tool, 2026-08-23 |
| 43–47 | Louis Abraham's [load-bearing](https://github.com/louisabraham/load-bearing) clusters of pull request descriptions |
| 48–52 | Simon Willison's [llm-cliche-highlighter](https://github.com/simonw/tools/blob/main/llm-cliche-highlighter.html), 2026-08-27 update |
| 53–56 | Clark, Martin and Mahowald, [arXiv 2610.29162](https://arxiv.org/abs/2610.29162) |

The benchmark post had 34 passages carrying about 45 tic instances across ten
shapes, and every specimen for entries 1 to 23 comes from that published draft.

Humanizer packages the Wikipedia AI Cleanup project's
[Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
as a portable skill. Before entries 24 to 36 were ported from it, a probe file of
19 humanizer specimens produced 2 candidates from this linter, neither for the
right reason. It now produces 33 across 13 categories. The no-fabrication rule,
the precedence of the author's writing sample, embedded mode and the list of
human traits to leave alone also come from humanizer.

The `create_session` reference page had already been through a pass with
declauding 0.4.0 and linted clean. Two of its section headers were then flagged
as thesis-shaped, all four of its headers were rewritten as nominalizations, and
the linter passed the result. That overcorrection became entry 41, which is why
the entry describes itself as one.

load-bearing clusters GitHub pull request descriptions by vocabulary: 461,121 of
them across 85 whole weeks, in ten clusters. One cluster grew from 0.70% of early
2025 to 39.5% of August 2026, the fastest growth of any cluster in the corpus. The
words most over-represented in it are `load-bearing`, `plainly`, `quietly`,
`refusal`, `re-derived`, `asserted`, `nobody`, `genuinely`, `outright` and
`byte-identical`. They are not the slop vocabulary of entry 20. They belong to
the flat, verdict-shaped register that a declauding rewrite tends to land in.
Entries 43 to 47 and the linter's `corpus-register` line came from that cluster,
along with the measurement in [`references/corpus.md`](references/corpus.md) of
what the rate can and cannot support.

llm-cliche-highlighter marks LLM clichés in pasted text. Its 2026-08-27 update
added fifteen patterns and three structural detectors. Eight of the fifteen were
already covered here in some form and extended existing entries, such as *here's
the twist* under entry 3 and *batteries included* under entry 19. The other five
had no entry and became entries 48 to 52. Two of the three detectors were ported,
and the third was already the comma-list form of entry 26. They are the shapes an essay uses when
it addresses the reader directly. Several of the ported regexes are narrower here
than in the source, which is tuned for essays rather than technical prose, and
the catalogue entries say which ones and why.

Clark, Martin and Mahowald (October 2026) parsed chat, coding-session and essay
output from fourteen models, nine of them frontier or near-frontier, and compared
it with round-trip paraphrases and with human text from the same genres. The
frontier models used more of the constructions that psycholinguistics links to
slower reading. The authors trace this to post-training that rewards correct
answers rather than clear ones, and showed in a small model that a per-token
length penalty alone produces the shorter forms.

## Complements

- **[challenging](../challenging)** runs an adversary against a draft's voice
  through its `prose-register` profile. It evaluates and returns findings, where
  this skill edits and returns text. Run `challenging` on the result when the
  stakes justify it.
- **[blader/humanizer](https://github.com/blader/humanizer)** is broader on
  encyclopedic and promotional slop and ships as a single file that works in any
  harness. This skill goes further into staging, ships a linter that is held to
  zero hits on human prose, and treats a tic as a sign that the sentence may also
  be factually wrong. Both are worth reading.
- **[crafting-instructions](../crafting-instructions)** covers prompts and
  instructions, which have a different target register.
- **[composing-html](../composing-html)** builds general single-file HTML
  artifacts. This skill ships its own template because the annotated diff has one
  fixed shape and no reason to depend on another skill.

## Dependencies

The linter, the preservation diff and the annotated template need only Python
3.9 or later with the standard library. `declaude_rank.py` needs torch and
transformers, and downloads `all-MiniLM-L6-v2` on first use.
`declaude_review.py` needs a Gemini or Anthropic API key to call a model itself,
and otherwise prints its prompt.
