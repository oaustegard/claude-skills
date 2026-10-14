---
name: describing-products
description: >-
  Builds a product description repo for a software product - prose documents
  that say, feature by feature and event by event, what the user sees, what they
  can do, and exactly what happens when they do it, including when they stop
  halfway. Drafted from the code and tests, verified against the running product
  with hand checklists, and triaged into a bug list. Works for canvas editors, web
  apps, CLIs, chat products, mobile apps, and libraries or SDKs. Use when asked to "write a product
  description for X", "describe the user experience of X", "document how X
  behaves for the user", "make a behavior-spec repo", or for an event-by-event
  account of an app's behavior rather than API docs. Also resumes or extends an
  existing product description repo.
metadata:
  version: 0.2.0
---

# Describing products

A product description treats the product as a large state chart the user moves through with input. The repo describes that state chart feature by feature, in plain language, from the user's side, with one skeleton for every document so that gaps and inconsistencies show up by comparison. Documents are drafted from source and tests, verified by hand against the running product, and every suspected defect lands in one triage file.

Adjacent skills: `featuring` inventories what a codebase does, by capability; this skill specifies how each capability behaves under every input and interruption. A `_FEATURES.md` is a good seed for this repo's structure, not a substitute for it.

`{skill}` below is this skill's directory.

| File | Use |
| --- | --- |
| `references/product-kinds.md` | Map the template onto a canvas editor, web app, CLI, chat product, or library/SDK. Read in Phase 0. |
| `references/README-template.md`, `goal-template.md`, `glossary-guide.md` | Skeletons for the three files that steer the build. `goal-template.md` carries the writing rules. |
| `references/document-template.md` | The eight-section skeleton every feature document follows. |
| `references/verification-template.md`, `bug-triage-template.md` | Skeletons for the checking half. |
| `scripts/check_links.py` | Every relative link and heading anchor resolves (GitHub slug rules). Links to documents the coverage table lists as `not started` are reported as planned; `--strict` counts them as broken. |
| `scripts/check_structure.py` | Coverage table matches disk; sections in order; footer present; modifier, interrupt and concern rows identical across documents; no empty cells. `--exclude` names extra non-feature files. |

Both scripts are stdlib Python 3, take the repo root, and exit 1 on failure.

## Outputs

```
README.md            purpose, conventions, document template, method, structure, coverage table
goal.md              standing instructions for whoever drafts (you, subagents, a future session)
glossary.md          the vocabulary; source of truth for every term of art
AGENTS.md            "Read README.md, then goal.md. The coverage table in README.md is the work list."
CLAUDE.md            "Read @AGENTS.md."
{area}/{feature}.md  one document per feature, all on the same skeleton
verification/        README.md (protocol) + one checklist file per cluster of documents
bug-triage.md        every suspected defect, deduplicated, with repro, cause, severity, decision needed
```

## Phase 0: scope

Settle these before writing a file. Ask only for what the conversation and the source repo cannot answer; record the answers in the README's "Scope decisions".

1. **Product and surface.** Which app, route, role or configuration, with what customization (usually none). One surface per repo.
2. **Source of truth.** Path to the source repo (read-only) and its commit. Every document footer cites `git rev-parse --short HEAD` of that repo.
3. **Where to run it.** The command and URL, binary, or account that brings the surface up for verification.
4. **Out of scope.** Name each exclusion and why, so readers do not take it for an omission.
5. **Where the repo goes.** A new directory with `git init` and a first commit `Initial commit`, or a directory inside an existing repo when the user keeps such work there (then follow that repo's conventions too, and pass its extra files, such as a `RESULTS.md`, to `check_structure.py --exclude`).
6. **The product's shape.** From `product-kinds.md`, decide once: the unit of interaction and its five phase names; the variant axis; the fixed interrupt list; the cross-cutting concerns and their order. These go into the README's "Document template" and the glossary before the pilot, and do not change afterwards without revisiting every document.

Then reconnoitre the source repo for: where interaction state lives (state machines, reducers, controllers, route handlers, command definitions), the behavior tests that read as executable specs of edge cases, the UI, and where defaults and thresholds are defined. Use `tree-sitting` or `exploring-codebases` for this when available rather than reading files whole. The findings fill the README's "Reference" section and goal.md's reading order.

## Phase 1: scaffold

Write, in order, from the templates:

1. **README.md** from `README-template.md`. The structure section is the plan: every expected document with a one-line gloss, grouped by how the user meets the feature (foundations, then the product's areas, then cross-cutting concerns), never by package or module. The coverage table lists every document as `not started`. Revise both as you learn; they must always mirror the files on disk.
2. **glossary.md** from `glossary-guide.md`. Start with the terms the foundations need and the interrupt words from Phase 0. A term used in a document but absent from the glossary is a consistency bug.
3. **goal.md** from `goal-template.md`. It drives all drafting. Its "Things already established" section starts empty.
4. **AGENTS.md** and **CLAUDE.md** with the contents shown under Outputs. AGENTS.md is what a fresh session reads first; never leave it empty.

Commit: `docs: add README, glossary, goal`.

## Phase 2: pilot, foundations, the hardest area

Do these yourself, in sequence. They fix the template, tone, depth and vocabulary everything else copies.

1. **Pilot.** One small, self-contained feature with a real interaction in it (`product-kinds.md` names one per kind), on the full eight-section template. Iterate until it is right. A small feature done properly runs 150–200 lines with every phase narrated, every variant and interrupt cell filled, and the cross-cutting list walked in full; a thin section means the feature has not been read closely enough. Run `check_structure.py` on the repo once the pilot exists; it is the reference shape from here on.
2. **Foundations.** The documents everything links to: the input or invocation model (events, thresholds, what cancels, completes, interrupts), the core object or data model, the mode, tool or navigation model, the viewport or session model. They own the facts other documents link to. As each lands, add its essential facts (numbers, defaults, rules) to goal.md's "Things already established".
3. **The hardest area.** The bulk of the experience (the selection tool, the main editor, the `build` command, the composer plus the streaming response). Read all of its state handling before writing any of its documents: the states hand off to each other and the documents must agree on where one ends and the next begins. Record which document owns which state in goal.md.

Commit after each document or coherent group: `docs: add {path}`.

## Phase 3: draft the rest in parallel

The remaining documents are independent. Fan out one document or small cluster per subagent, with this prompt:

> Read `goal.md`, `README.md`, `glossary.md`, `{pilot}`, and `{the foundation document this feature depends on}`. Write `{area}/{feature}.md` on the same skeleton, at the same depth. Use the glossary's words. Do not edit `glossary.md`, `README.md`, `goal.md` or any other existing document: if you need a term the glossary lacks, use it and list it in your report with a proposed definition and section. Do not modify the source repo. End with "## Open questions and verification" and the footer. Report what you could not determine from code and tests, and the proposed glossary terms.

Parallel drafters must not write shared files: two agents editing `glossary.md` at once lose each other's terms, and two coined definitions for one word are a consistency bug that surfaces only in Phase 4. Merge the proposed terms yourself, once, picking one word per concept, and fix the drafts that used the losing synonym.

Review every result before accepting it: glossary words used correctly, established facts not contradicted, interrupt table complete (every row, even "no effect"), suspected bugs stated plainly in "Open questions" rather than smoothed over. `check_links.py` and `check_structure.py --reference {pilot}` catch the mechanical half.

Update the coverage table to `drafted` as each lands. Commit in groups: `docs: add {paths}`.

## Phase 4: consistency pass

Mechanical, both must exit 0:

```sh
python3 {skill}/scripts/check_links.py {repo} --strict
python3 {skill}/scripts/check_structure.py {repo} --reference {pilot}
```

Without `--strict`, links to documents still `not started` are listed but do not fail; use that during Phases 2 and 3.

By reading, over the whole set:

- Same term for the same thing everywhere; every term of art defined in the glossary; glossary definitions agree with the documents.
- No two documents describe the same behavior differently. Where two documents touch, one owns the behavior and the other links.
- Variant and interrupt *answers* agree where the same mechanism is involved (the scripts check rows, not content).

Commit: `docs: revise the set after the consistency review`. Then deepen the documents whose open questions were thinnest; expect a second revision on a handful.

## Phase 5: verification checklists

Drafting reads the code; verification watches the product. From `verification-template.md`:

- `verification/README.md`: how to bring up the surface, confirm the commit, run a pass, record results, file failures, and when a document moves from `drafted` to `verified`.
- One checklist file per cluster of documents, one table per document, one row per observable claim: stable ID (`AREA-NN`), priority (P1 established fact or suspected bug, P2 ordinary claim, P3 a number, color or timing), what it needs (device, role, network condition), the claim linked to its section, setup, numbered steps, expected result, Result (`—` until run). Claims not checkable by hand go under "Not checkable by hand".

For a library or a CLI, every item is a short script: write `verification/run_pass.py` with one function per checklist ID, and probe claims with those scripts while drafting rather than after. Each automated item must assert the exact expected outcome (exception type and message, file names, values); a check that accepts any exception will pass a wrong claim.

If you can drive the product (Playwright or other browser automation, a console handle on the app, a shell for a CLI, a test harness), run a first pass on what that can observe, record results in the Result columns, and state in `verification/README.md` exactly what the pass did and did not cover (a scripted pass checks output, exit codes and stored state, not what was on screen or how long it took to appear). Never mark a document `verified` on an automated pass alone. A failed item is not automatically a product bug; sometimes the document is wrong, and the Status line says which.

## Phase 6: bug triage

From `bug-triage-template.md`: collect every suspected defect from every document's body and open questions, merge by root cause (one cause raised by many documents is one entry with many "Raised by" links), and write each up with where the user meets it, what happens vs. what was expected, reproduction steps, the cause in code with file and line, a severity, and the decision needed (`fix` or `product call`). Summary table on top, sorted by severity. Entries a verification pass touched carry a **Status** line.

**Filing upstream is outward-facing.** Offer it; never do it unasked. If the user wants issues filed, confirm the repo and format first, file them, then add an Issue line to each entry and a link column to the summary (`docs: revise bug-triage.md with links to the filed issues`).

## Resuming and extending an existing repo

A later session, or a request to add an out-of-scope feature, starts here rather than at Phase 0.

1. Read `AGENTS.md`, `README.md` (structure, coverage, scope decisions), `goal.md` (established facts) and `glossary.md`. Read the pilot to recalibrate depth. Run both scripts to see the repo's current state.
2. Confirm the source repo's commit. If it moved, decide with the user whether new documents cite the new commit (and say so in their footer) or the repo pins the old one. `check_structure.py` warns when documents cite more than one commit; never let that happen silently.
3. To add a document: add it to the README structure and coverage table first, write it, add its checklist table to the right `verification/` file (new ID prefix, numbered from 01), add any new triage entries with the next `B-NN`, and commit each step: `docs: add {path}`, `docs: add the {name} checklist ({PREFIX}-01 to {PREFIX}-NN) to verification/{cluster}.md`, `docs: add B-NN to B-MM to bug-triage.md from the {name} work`.
4. To revise after a verification pass: change the document, update the checklist row's Result and note, update the triage entry's Status, commit `docs: revise {path}`.
5. Never renumber checklist or triage IDs once a pass or an issue has used them.

## Writing rules

They live in `goal-template.md` and are copied into goal.md, which every drafter reads. The ones most often broken:

- Describe the experience, not the code: "the form stays disabled until the server answers", not "the mutation sets isPending". Mechanism goes only in `> Technical note:` block quotes, and only when it changes what the user would expect.
- Every table cell filled, "No effect." included. An empty cell is an unasked question.
- When code and tests cannot settle a behavior, write what they do settle, put the rest in "Open questions", and move on. Do not guess; do not block.
- Never modify the source repo.
- Follow the target repo's convention on AI attribution in commit messages.

## What never changes, whatever the product

The outside-in stance; one skeleton for every document; the interrupt list asked of every feature in the same order; a glossary that owns the words; foundations written first so they own the numbers; a pilot that sets the depth; drafting from code and tests, then verifying against the running product, then triaging what looks wrong. `product-kinds.md` covers what to rename; this list is what stays fixed.

---

Adapted from Steve Ruiz's `product-description` skill (gist.github.com/steveruizok/83ae5c53f2784ebf8f5fe0a3fb94480f), first used on a ~65-document description of a canvas editor.
