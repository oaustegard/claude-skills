# informed-patient

**Written by [Cat Hicks](https://github.com/DrCatHicks). Original:
[DrCatHicks/informed-patient](https://github.com/DrCatHicks/informed-patient),
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).** This copy
is a structural adaptation, described below. The methodology, the interview
design, the evidence-evaluation framework and the red flags are hers.

Helps someone turn their own health experience into a document a clinician can
read: a structured symptom picture, a mini literature review with quality-tagged
sources, competing hypotheses, and questions the user picked from a list. The
output is a markdown file written to disk.

The skill does not diagnose, does not recommend treatments, and does not
substitute for a clinician. It fires only when asked for by name — never off a
health question or a symptom mention.

Cat Hicks is a psychologist and research scientist who studies how people learn
and reason. Her write-up of the design choices, the risk guardrails, the privacy
guidance for anyone using this with their own health data, and the reference
literature behind the symptom-elicitation methodology is in the
[upstream README](https://github.com/DrCatHicks/informed-patient#readme). Read it
before using this on your own health situation. Upstream also carries
[`EVALUATION.md`](https://github.com/DrCatHicks/informed-patient/blob/main/EVALUATION.md),
a 30-test suite covering search capability, literature-review quality, process
adherence and edge cases.

## Changes in this copy

Upstream ships one 34.6KB `SKILL.md` plus five reference files. Everything a
session needs — every interview question, every search-mode rule, every
hypothesis-framing branch — loads at trigger time, whether or not the session
reaches that phase.

This copy splits it into an 8.1KB resident core and three phase references that
load when the phase starts:

| file | bytes | loads |
|---|---|---|
| `SKILL.md` | 8.2K | on trigger |
| `references/phase-1-interview.md` | 6.4K | before the first interview question |
| `references/phase-2-search.md` | 12.0K | before the first search query |
| `references/phase-3-evaluation.md` | 6.4K | before drafting hypotheses |

Procedure text in the three phase files is upstream's, verbatim. The five
upstream references (`evidence-hierarchy`, `literature-search-strategy`,
`output-template`, `red-flags`, `symptom-inventory-methodology`) carry over with
one kind of edit: intra-directory links lost their `references/` prefix, since
the files that link to them now sit alongside them.

The core was rewritten. What it keeps is set by upstream's own tests: section 3
of `EVALUATION.md` checks that branching questions get asked, that a functional
impact statement is required, that red flags fire after the search rather than at
the end. Behavior an eval checks stays resident, so a reference that fails to
load costs quality rather than sequence or safety. Resident: scope boundaries,
the no-diagnose / no-treatment-recommendation / no-therapy rules, citation
integrity, "absence of evidence is a finding", the phase sequence with per-phase
entry conditions, the ten red-flag names, and the requirement that the artifact
be written to a file.

The trigger is unchanged from upstream: explicit request by name.

## Licence

This skill is CC BY 4.0, unlike the rest of this repository, which is MIT. The
full text is in `LICENSE.txt`. Attribution, the licence link and the statement of
changes are also in the `## Attribution` section of `SKILL.md`.
