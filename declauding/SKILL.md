---
name: declauding
description: Removes LLM prose tics from drafts — staged reveals, "it's not X, it's Y", significance tags, abstraction agency, coy headers, fragment cadence, plus the flatter slop patterns (copula avoidance, participle tails, forced triads, chatbot residue, filler and hedging) — and returns plain human technical prose. Use when text needs editing for register, when someone says "de-claude", "de-slop", "humanize this", "this reads like AI", "make this sound human", "remove the tics/claudisms", or asks for a voice/register pass on a post, README, report, PR description or essay. Also use before publishing any draft Claude wrote. Produces either clean prose or an annotated HTML diff showing every edit with its original and reason.
metadata:
  version: 0.2.1
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

Opinions and stance are voice, not facts. Keeping the author's judgment is
required (see Overcorrection); adding a factual claim they did not make is a
defect even when the result reads more human.

## The one pattern

Almost every tic in `references/register.md` is a version of the same move:
**the sentence is built to make the reader feel a finding arrive, instead of
stating the finding.**

The generative test, applied per sentence: *am I saying the thing, or
performing having had the thought?* Say the thing.

Entries 24 to 36 are a second family — the flatter encyclopedic and chatbot
patterns, where nothing is being staged and the writing is just running on
defaults. Copula avoidance, participle tails, forced triads, chatbot residue.
Different mechanism, same pass. Entry 37 is back in the staging family and sits
last only because it arrived last.

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
```

It flags greppable tells with line numbers and categories. It has no judgment —
it finds candidates, it does not decide. Everything it flags still needs the
sentence-level test, and it misses every tic that is structural rather than
lexical. Treat a clean lint report as meaningless on its own.

**3. Sentence pass.** For every sentence, in order: stating or staging? Load
`references/register.md` for the catalogue of tells and their fixes.

**4. Structure pass.** Headers (are they labels or verdicts?), paragraph breaks
(is an isolated line a real pivot or a drum roll?), fragment runs, rhetorical
questions, and the closer (does the last paragraph paraphrase the subtext of
what preceded it? delete it).

**5. Check what the edit did.** Four failure modes, all of them common:
- Content lost. Every fact, number, caveat and hedge-with-content in the source
  must survive. A tic wrapping a real qualification is still a real
  qualification. Structure is free — merge or split paragraphs, compress the dull
  parts, dwell where the author would. When keeping the information and mirroring
  the original's shape pull against each other, the information wins.
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

Several banned shapes are legitimate in one specific circumstance. Check before
deleting:

| Shape | Banned when | Earned when |
|---|---|---|
| "X rather than Y" | You invented Y so you could reject it | The reader was genuinely holding Y — the draft proposed it, or it is the field's default |
| "Nobody noticed" | Unfalsifiable claim about others' inattention | You can name the mechanism and duration: "nobody noticed for six weeks because the dashboard only alarms on nulls" |
| Isolated one-line paragraph | Gravitas beat | Real pivot: new actor, category shift, time jump |
| Colon before the payload | Withholding for a beat | The payload is a list, a definition, or a code block |
| Short declarative closer | Compresses the section into a moral | States a fact: "Default retries are back to 3." |

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
