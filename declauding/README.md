# declauding

Removes LLM prose tics from a draft and returns plain human technical prose. The
input is text; the output is either the rewritten text or an annotated HTML diff
showing every edit with its original and its reason.

Almost every tic it catches is one move: **the sentence is built to make the
reader feel a finding arrive, instead of stating the finding.** The register
catalogues the shapes that move takes. The fix is always the same: put a real
subject in the subject slot, say the thing, stop.

See [`SKILL.md`](SKILL.md) for the workflow, the overcorrection guard and the
earned-exception table. See [`references/register.md`](references/register.md)
for the catalogue. See [`CHANGELOG.md`](CHANGELOG.md) for version history.

## Two modes

| Mode | Output | Use for |
|---|---|---|
| **clean** (default) | The rewritten text, nothing else | Fixing your own draft before publishing |
| **annotated** | One self-contained HTML file: rewritten text, every changed passage marked, each with the original verbatim, the tic name, and why | Reviewing someone else's draft, teaching the register, arguing about a specific edit |

The annotated file has a toggle that hides the marks, so the same artifact
serves as both the review and the result. No build step, no CDN, no server.

## Tics it catches

Twenty-three entries in the register, grouped by mechanism rather than by
phrase, since phrase blocklists miss the next paraphrase. The ones that show
up in nearly every draft:

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

Each entry carries the surface tell, why it is a tic, the fix, and a real
before-and-after taken from a published draft.

## The linter

```sh
python3 scripts/declaude_lint.py DRAFT.md            # human-readable
python3 scripts/declaude_lint.py DRAFT.md --json     # machine-readable
python3 scripts/declaude_lint.py - --quiet-slop      # stdin, minus vocabulary noise
python3 scripts/declaude_lint.py DOC.md --skip-quoted # ignore quoted specimens
```

Stdlib only. It flags the lexical tells with line numbers and categories, plus
header shape, one-line-paragraph beats, fragment runs, em-dash density and
sentence-length monotony.

It finds candidates and does not decide. Every hit still needs the
sentence-level test, and no regex reaches a staged paragraph shape or a staged
closer, so **a clean report means nothing on its own.**

Exit code 1 when it finds candidates, 0 when it does not, which makes it usable
as a pre-commit hook.

## False positives

`tests/sample-clean.md` is human-written prose and must lint to zero.
`tests/sample-tics.md` is a corpus of real specimens and currently reports 29
candidates across 12 categories.

```sh
python3 scripts/declaude_lint.py tests/sample-tics.md    # 29 candidates
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

## Provenance

Built from a register pass on an external benchmark post (2026-08-16), where 34
passages carried about 45 tic instances across ten shapes. Every specimen in the
register and the test corpus comes from a real published draft.

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
