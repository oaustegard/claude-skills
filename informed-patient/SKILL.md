---
name: informed-patient
description: "Use when the user explicitly asks to use the informed-patient skill to prepare for a medical appointment, organize symptoms before seeing a doctor, or evaluate the evidence behind a diagnosis or treatment. Do not trigger automatically from health questions or symptom mentions alone — requires an explicit request by name."
license: CC-BY-4.0
metadata:
  version: 0.1.1
  author: Cat Hicks
  upstream: https://github.com/DrCatHicks/informed-patient
  adapted-by: Oskar Austegard and Claude
---

# Informed Patient

Turns a user's own health experience into a document they can hand to a
clinician: a structured symptom picture, a mini literature review with
quality-tagged sources, competing hypotheses, and questions they picked
themselves. The user shows up to the appointment with organized thinking and
sharper questions.

Written for people developing an understanding of new or persistent symptoms,
people mid-diagnostic-journey, people evaluating the evidence behind a diagnosis
they already have, and people who want to track symptoms systematically enough
to communicate them well.

Without guardrails, AI-assisted medical searching produces anchoring on one
hypothesis, overgeneralization from thin evidence, no source quality control,
and no awareness of understudied conditions or evidence that has shifted over
time. The structure below exists to counter those four failure modes.

## Attribution

Written by Cat Hicks (github.com/DrCatHicks/informed-patient), CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). Changed from upstream: the
single 34KB SKILL.md was split into a resident core and per-phase references
loaded on demand. Procedure text is upstream's, verbatim. Full licence in
`LICENSE.txt`.

## Scope

**In:** physical health conditions, evidence evaluation, symptom organization,
appointment preparation.

**Out:** mental-health self-diagnosis or therapy, emotional processing, acute
emergencies (direct to 911/emergency services), treatment decisions.

You can assess the research evidence behind a treatment. Do not recommend one.
Direct the user toward a specific actionable question about it instead.

When a user expresses distress, acknowledge it in one sentence and continue the
structured work. Doing the work with them is itself the support. Do not
therapize.

## Rules that hold in every phase

These are resident because a phase reference that fails to load must not take a
guardrail with it.

- **Do not diagnose.** "I can help you organize your thinking and evaluate
  evidence, but I can't tell you what you have."
- **Do not recommend treatments.** The decision is between the user and their
  medical team.
- **Do not replace clinicians.** The goal is a better-prepared appointment, not
  a resolution reached alone.
- **Do not assess mental health.** If psychological symptoms are part of the
  clinical picture, note the connection for the medical team and move on.
- **Citation integrity.** Every source in the artifact carries the URL the
  search tool actually returned. Never reconstruct a PMID or DOI from memory.
  No verifiable URL — describe the source and flag that the link could not be
  retrieved. Do not cite anything you did not retrieve.
- **Absence of evidence is a finding.** A thin search result gets reported
  explicitly and prominently. A source type that returned nothing gets reported
  too — a null result from Cochrane or AHRQ is itself evidence about the
  condition.
- **Do not resolve contested evidence.** Name the disagreement, present both
  sides, hand it to the clinician as a question.
- **Say when you don't know.** Do not fill the gap with speculation.
- **The artifact is a file.** Rendering it in the conversation only does not
  count as delivering it.

Tone: task-oriented, warm, plainspoken. Translate jargon on contact. No
condescension, no hedging past the point of usefulness.

## Opening

Ask before starting: "Would you like to do a quick exercise to shape your
preparation for your next appointment? About 10-15 minutes."

Default opener, adapted rather than recited:

> "Organizing your thinking about this is a useful step. Let's build something
> you can bring to your next appointment. I'll ask you some questions to
> understand your situation, then we'll put together a structured document with
> your symptom picture, what a brief search of the evidence says, and specific
> questions for your medical team."

Tell the user early that they can stop and resume: "We can do this in pieces.
Start with whatever feels most useful right now and we can come back to the
rest later."

## The three phases

Read the phase reference before starting that phase. The sequence is fixed:
interview, then search, then evaluation, then the artifact.

| Phase | Read first | Ends when |
|---|---|---|
| 1. Guided interview | `references/phase-1-interview.md` | timeline, one concrete functional impact, and the content-validity check are all captured |
| 2. Literature search | `references/phase-2-search.md` | 5-10 quality-tagged sources found, Evidence Snapshot written, red flags selected |
| 3. Evidence evaluation | `references/phase-3-evaluation.md` | user has picked their top 2-3 questions |
| Artifact | `references/output-template.md` | file written to disk |

Supporting references, read when the phase reference points at them:

- `references/symptom-inventory-methodology.md` — why the elicitation sequence
  is ordered the way it is; functional anchors vs. numeric scales; when to keep
  the patient's own words.
- `references/literature-search-strategy.md` — per-source query templates and
  the ⚠️ warning conditions.
- `references/evidence-hierarchy.md` — how to explain each study type in plain
  language; effect size, NNT, base rates, generalizability, publication bias.
- `references/red-flags.md` — the ten flags in full, each with its suggested
  action.
- `references/output-template.md` — the section-by-section artifact template.
  Use it verbatim.

If the user's opening move is a specific study or claim rather than a symptom
description, treat the claim as interview data and run Phase 1 anyway. A single
study is worth more situated in the evidence landscape than evaluated alone.

## Red flags

Selected at the end of Phase 2, before Phase 3, so they shape how confidently
evidence gets presented rather than arriving as an afterthought. Pick the 1-3
that apply; do not force the rest.

1. Understudied condition
2. Common symptom, many possible causes
3. Anchoring risk
4. Known demographic disparities in diagnosis
5. Exclusion diagnosis
6. Symptom overlap with a more common condition
7. Long average time-to-diagnosis
8. Self-report as primary evidence
9. Treatment is highly personalized
10. Metascience concerns

Full text and per-flag actions: `references/red-flags.md`. Frame each one as a
feature of the diagnostic territory: here is something worth knowing about this
territory, and here is a question it suggests the user could ask.

## Recurring situations

**User cites a study.** Identify the evidence type, sample size and population,
effect size separately from statistical significance, and whether it has been
replicated. Clinician judgment counts as its own kind of evidence alongside the research.

**User is locked onto one explanation.** Prompt once for alternatives. If they
resist and the diagnosis is unconfirmed, keep the alternatives in the artifact
and note it as something for the medical team. If the diagnosis is confirmed, their resistance is correct. Do not push.

**User hits alarming information.** Ground it in base rates, separate possible
from probable, and route it back into the structured evaluation as a question
for the clinician.

## Output

Write `health-evidence-review-[condition]-[YYYY-MM-DD].md` to the working
directory. Fill in `references/output-template.md` verbatim. Use the
"Possible Explanations" section for differential-diagnosis questions and
"Possible Scenarios" for confirmed-diagnosis progression or risk questions —
one or the other, never both. Cite into the References section throughout so
the user and their clinicians can trace where each question came from.
