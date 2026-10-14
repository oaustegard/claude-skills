# README template

Placeholders are written `{like this}` and are usually an instruction or a menu of examples; replace every one with real prose (angle-bracket placeholders are not used because GitHub renders them as HTML and they vanish). Keep the section order. The "Structure" block and the "Coverage" table are the plan; keep them exact mirrors of the files on disk.

---

# {product} product description

A written description of the user experience of {product}: what the user sees, what they can do, and exactly what happens when they do it.

## Purpose

{product} is, from the user's point of view, a large state chart. The user moves through it with {the product's inputs: pointer events, drags, clicks, modifier keys, scrolls, keyboard shortcuts / taps and swipes / commands and flags / form submissions}. Most of that behavior is defined implicitly, spread across {where it lives in the code: state machines, reducers, handlers, tests, the UI}. There is no single place that says, in plain language, "when the user does X, this is what happens, and this is what happens if they do Y halfway through."

This project is that place. It describes the full experience a user has on {the surface being described: a specific route of the app / the default installation / the production site with a fresh account}, in {the default configuration, with nothing customized}.

The documents are for people who need to understand or change the product: designers, engineers, writers, testers, and anyone evaluating whether a behavior is intentional. They are written from the outside in. They describe the experience, not the implementation.

### What this is not

- Not API documentation. {Say where that lives.}
- Not organized by package. {The product's packages or modules} are not described separately. A single behavior is described once, wherever the user encounters it.
- Not a technical design document. Where a technical detail is critical to understanding the experience, it appears in a block quote labeled `Technical note:` and nowhere else.

## Conventions

- Describe the experience, not the code. "{an experiential sentence}" rather than "{the same thing said about the code}".
- Technical detail goes in block quotes, prefixed with `Technical note:`. Use it only when the mechanism changes what the user would expect.
- Use sentence case for headings.
- Name the vocabulary consistently. The [glossary](glossary.md) is the source of truth for terms like {five or six of the product's load-bearing terms}.
- Every document ends with the commit of {the source repo} it was verified against and a list of open questions.
- When a behavior is surprising, say so and say why it is that way if the reason is known. Do not smooth it over.

## The work to be done

Each document describes one feature. Features are large things ({example of a big one}) or small things ({example of a tiny one}), but each is described in full, including its edge cases and its interactions with other features.

### Document template

Every feature document follows the same skeleton so that documents are comparable and nothing is skipped.

1. **Summary.** One paragraph describing the feature abstractly. For example: "{one-sentence summary of the pilot feature}."
2. **The simple case.** The common path in prose.
3. **The interaction, event by event.** The five phases of {the product's unit of interaction: a gesture / a page or form lifecycle / an invocation / a turn}: {name them in the product's words: starting; ending at once; becoming extended; while extended; finishing}. What starts it and what is captured, what happens if it ends at once, what is decided the moment it becomes extended, what updates live, and what is committed at the end. Include a small state diagram (Mermaid `stateDiagram-v2`) of the states the user passes through.
4. **Modifiers.** A table of {Shift, Alt/Option, Ctrl/Cmd, and Space / the product's variant axis: roles, record states, flags, modes}, and what each one does when set at the start and when changed *during* the interaction.
5. **Cancel and interrupt.** The same checklist in every document:
   - {The user's explicit abort: Escape, Stop, Ctrl+C, a Cancel button}
   - {The user doing something else mid-way: switching tools, modes, tabs, or conversations; navigating away; sending another message}
   - {The events the product treats as a clean "complete": a menu opening, undo or redo, a submit from elsewhere}
   - {The environment failing: window loses focus, network lost, request fails or times out, session expires}
   - {The page or process going away: reload, tab closed, terminal closed, app backgrounded}
   - {Something else changing the target: deleted, locked, edited by another user or tab, changed on disk}
   - {The input channel changing: a second input device, autofill, a pipe closing, touch cancel}
   {Rewrite this list for the product, drawing on the families in the skill's `product-kinds.md`: the user's explicit abort; the user doing something else mid-way; the events the product treats as a clean complete; the environment failing; the page or process going away; something else changing the target; the input channel changing. It must be identical, and in the same order, in every document.}
6. **Interactions with other systems.** {The product's cross-cutting concerns, in a fixed order: permissions, history or undo, containers or parents, locked or readonly state, offline, collaboration or multi-device, notifications, configuration and preferences.}
7. **Edge cases.** Anything a user could notice that is not covered above.
8. **Open questions and verification.** The {source repo} commit the document was verified against, and any behavior that could not be confirmed.

Item 5 matters most. Asking the same interrupt questions of every feature is how gaps and inconsistencies are found.

### Method

For each document:

1. Read {where the interaction state lives} and the relevant {domain objects}.
2. Read the matching tests in {test directory}. Files like {list the ones that read as executable specifications} are close to executable specifications of the edge cases.
3. Draft the document.
4. Try anything ambiguous {in the running product: URL, binary, or account}. Tests settle "what happens"; the running product settles how it feels, what is visible while the interaction is in progress, and what the timing is like.
5. Record the commit verified against.

### Verification

Drafting reads the code; verification watches the product. The `verification/` directory holds one checklist per cluster of documents, each item a single observable claim with setup, steps, expected result, a priority, and the device it needs. A tester runs them {on the surface}, records `pass`, `fail`, or `blocked` in the Result column, and files every failure in `bug-triage.md` with the item's ID. A document moves from `drafted` to `verified` in the coverage table only when every P1 and P2 item for it has passed or been filed.

`bug-triage.md` is the other half: every behavior the documents flagged as a likely defect, deduplicated, with reproduction steps, the reason in the code, a severity, and the decision the product team needs to make. Entries confirmed {in the running product} carry a Status line.

### Order of work

1. **Pilot: {the pilot feature}.** Small and self-contained. Used to settle the template, tone, and depth.
2. **Foundations: {the input model / the core model}.** Everything else refers to it.
3. **{The hardest area}.** The bulk of the experience and the hardest part. Written third so the template is already proven.
4. **Everything else.** Once the template and two exemplars exist, the remaining documents can be drafted in parallel, followed by a consistency pass and a verification pass across the whole set.

Progress is tracked in the [coverage table](#coverage) below.

### Scope decisions

- **{Excluded thing}.** {Why, and whether it gets a document later.}
- **{Concern described inside each document rather than separately}.** {Why: a separate document would drift.}
- **{Concern described once in a cross-cutting document rather than in every feature}.** {Why.}
- **Interaction shape.** The unit of interaction is {a gesture / a form lifecycle / an invocation / a turn} and its phases are {the five names}. The interrupt list and the order of cross-cutting concerns are fixed as written in the document template above.
- **Numbered rules.** These are prose documents, not numbered specifications. Stable heading anchors are enough for cross-references.

## Structure

```
README.md                        this file
goal.md                          the standing instructions for whoever drafts
AGENTS.md, CLAUDE.md             entry points for agents: read README.md, then goal.md
glossary.md                      shared vocabulary
bug-triage.md                    suspected defects collected from every document, with repro steps and decisions needed

verification/
  README.md                      how to run a hand-verification pass and record results
  {cluster}.md                   checklists for {area}/ and {area}/
  ...

foundations/
  {name}.md                      {one-line gloss, wrapping to a second indented line if needed}
  ...

{area}/
  {feature}.md                   {gloss}
  {sub-area}/
    {feature}.md                 {gloss}
  ...

cross-cutting/
  {concern}.md                   {gloss}
  ...
```

## Coverage

Status is one of `not started`, `drafted`, or `verified`.

| Document | Status |
| --- | --- |
| glossary.md | not started |
| bug-triage.md | not started |
| verification/ ({n} checklists) | not started |
| foundations/{name}.md | not started |
| ... | not started |

## Reference

The source of truth is {the source repo} at `{path or URL}`. The relevant locations are:

- `{path}`: {the surface this project describes}
- `{path}`: {where interaction state lives}
- `{path}`: {the domain objects}
- `{path}`: {the UI}
- `{path}`: {behavioral tests}
- `{path}`: {subsystems that shape the experience: hit testing, validation, scheduling, caching, sync, etc.}
