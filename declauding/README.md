# declauding

Removes LLM prose tics from a draft and returns plain human technical prose. The
input is text; the output is either the rewritten text or an annotated HTML diff
showing every edit with its original and its reason.

The register has two halves. Entries 1 to 23 are one move: **the sentence is
built to make the reader feel a finding arrive, instead of stating the finding.**
The fix is always the same: put a real subject in the subject slot, say the
thing, stop. Entries 24 to 36 are the flatter slop patterns, where nothing is
being staged and the prose is running on defaults. Entry 37 returns to the first
half and sits last because it arrived last.

See [`SKILL.md`](SKILL.md) for the workflow, the overcorrection guard and the
earned-exception table. See [`references/register.md`](references/register.md)
for the catalogue. See [`CHANGELOG.md`](CHANGELOG.md) for version history.

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

Thirty-seven entries. The first 23, and entry 37, are grouped by mechanism rather
than by phrase, since phrase blocklists miss the next paraphrase. The ones that
show up in nearly every draft:

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
inline-header bullets, em-dash density, curly-quote and emoji counts, and
sentence-length monotony.

`--skip-quoted` blanks blockquotes, table rows, code (fenced and inline),
`*italic*` spans and `<q>` elements while preserving line numbers. Use it on any
document that quotes bad prose as a specimen, this README included.

It finds candidates and does not decide. Every hit still needs the
sentence-level test, and no regex reaches a staged paragraph shape or a staged
closer, so **a clean report means nothing on its own.**

Exit code 1 when it finds candidates, 0 when it does not, which makes it usable
as a pre-commit hook.

## False positives

`tests/sample-clean.md` is human-written prose and must lint to zero.
`tests/sample-tics.md` is a corpus of real specimens and currently reports 62
candidates across 24 categories.

```sh
python3 scripts/declaude_lint.py tests/sample-tics.md    # 62 candidates
python3 scripts/declaude_lint.py tests/sample-clean.md   # 0
```

Two rules are deliberately tuned down to hold that zero, so the linter misses
some real coy headers. A linter that fires on good writing gets ignored, and
then it catches nothing.

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

Several banned shapes have an earned form, tabulated in `SKILL.md`. *X rather
than Y* is legitimate when the reader was genuinely holding Y; it is staged when
you supplied Y so you could reject it.

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
