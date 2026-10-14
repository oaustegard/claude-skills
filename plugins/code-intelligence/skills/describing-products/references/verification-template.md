# Verification templates

Two kinds of file: `verification/README.md` (the protocol) and one checklist per cluster of documents. Clusters follow the README structure (for example: foundations + the hardest area, the other tools + objects, actions + UI, cross-cutting).

## verification/README.md

```
# Hand verification

The feature documents were written from the code and the tests. This directory is the protocol for checking them against the running product, one observable claim at a time.

## What is here

| File | Covers |
| --- | --- |
| [{cluster}.md]({cluster}.md) | `{area}/*` and `{area}/*` |
| ... | ... |

Each file has one table per document. Each row is an item with a stable ID (`INVITE-07`, `INIT-12`), a priority, what it needs (a device, a role, a network condition, a second user), the claim with a link to the document section, the setup, numbered steps, the expected result, and a Result column for the tester. Items that cannot be checked by hand (design questions, things that need a product decision) are listed under each document as "Not checkable by hand".

Priorities: **P1** is an established fact, a claim many documents depend on, or a suspected bug; **P2** is an ordinary claim; **P3** is a number, a color, or a timing.

## How to run a pass

1. {Bring up the surface: the command, the URL, how to get a clean state for the pass and clean up afterward.}
2. Confirm the commit. Every document says `Verified against {repo} commit {sha}`. Run `git rev-parse --short HEAD` in {the source repo}; if it differs, the documents describe a different build and some failures will be drift, not defects.
3. Keep the documents open beside the {product}. Read the linked section before each item; the item is a summary, the section is the claim.
4. Work through P1 first across all files, then P2, then P3.
5. Record `pass`, `fail`, or `blocked` in the Result column, with a note for anything other than a clean pass. A fail is something the document says that the product does not do; a blocked item could not be run (no device, no second user, a prior failure in the way).
6. File every fail in [`bug-triage.md`](../bug-triage.md): if the entry exists, add a Status line quoting the item ID; if not, add an entry with the item ID under "Raised by". A fail is not automatically a product bug; sometimes the document is wrong, and the fix is to the document. Say which in the Status line.
7. When every P1 and P2 item for a document has passed or been filed, change its row in the [coverage table](../README.md#coverage) from `drafted` to `verified`.

## Devices and conditions

{One bullet per value the Device column uses (mouse, keyboard, touch, pen, a second user, specific files to drop, a readonly account, an admin role, offline, a piped stdout, a second device), with how to get it and any trap (a second tab is not a second browser; an offline toggle in devtools does not fail an in-flight websocket the way pulling the cable does; a trackpad reports inertial scrolling that a mouse does not; `--no-color` and a pipe are not the same condition).}

## Driving the product from a console or script

{If the surface exposes a handle (a global app object in the browser console, an inspector, a state dump command), say what it is good for: setting up the starting state exactly, reading state back after a real interaction, the handful of items whose expected result is a state rather than something visible. The real input should still be real input where the item is about input; use the console to observe, not to gesture. Say what the console cannot do (overlays drawn on animation frames stop when the window is occluded; synthetic key events may not reach the shortcut layer). For a CLI, most items are commands with expected output and exit codes and can be run as a script; say which items are TTY-only (prompts, progress, color) and must be watched.}

## Results so far

{Nothing yet, or: what pass was run, when, on what, against which commit, by what means, how many items, how many passed and failed, which triage entries the failures map to, and what the pass did not cover. Be exact about limits: "with the window occluded (so nothing visual was checked)". Say which documents, if any, are marked verified and why none are if none.}
```

## A checklist file

```
# Verification: {cluster name}

How to run this file: {one paragraph: the fresh-state setup specific to this cluster, which preferences must be at defaults, how to clear between sections, what each value in the Device column (`mouse` / `keyboard` / `touch` / `pen` / `sync`, or `admin` / `offline` / `piped`) means}.

## {area}/{document}.md

| ID | P | Device | Claim | Setup | Steps | Expected | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {PREFIX}-01 | P1 | mouse | {One sentence, the claim as the document states it} ([{section name}](../{area}/{document}.md#{anchor})). | {The scene and mode to start from.} | 1. {Step.}<br>2. {Step.}<br>3. {Step.} | {What is seen or read back, specific enough that pass/fail is unambiguous.} | — |
| {PREFIX}-02 | P2 | keyboard | ... | ... | ... | ... | — |

Not checkable by hand:

- {A design question or product decision the document raised; link to it.}
```

### Rules for items

- One observable claim per row. If a document sentence contains two claims, it is two rows.
- IDs are `{PREFIX}-NN`, prefix per document (`INVITE`, `INIT`, `COMPOSE`), numbered in document order, never renumbered once a pass has used them.
- The claim links to the section it summarizes. The section is the authority; the row is the summary.
- Setup states the starting state precisely (which record, which role, which fields filled; which files on disk, which flags, which environment; how many objects, which selected, which mode, which preferences).
- Steps are numbered, imperative, and include exact distances, keys, and timings where the claim depends on them ("Type a 65-character name", "press Ctrl+C within 1 s of the first progress line", "drag 200 px right", "wait 500 ms before releasing").
- Expected describes what is seen *and* what is not ("the dialog closes, no toast, the list is unchanged"; "exit code 2, nothing on stdout, one line on stderr"). For suspected bugs, say "Record what happens" and mark the row "(suspected bug)".
- Every suspected bug in the document gets a P1 row, even if the tester can only record the result.
- Every cancel/interrupt table cell that is not "no effect" gets a row. Every modifier cell that is not "no effect" gets a row.
- Numbers, colors, and timings are P3 unless many documents depend on them (the threshold that separates the short path from the extended one is P1).
- The Result column is `—` until a pass fills it. Results are recorded in place, with a short note after anything other than `pass`.

Expect on the order of a few dozen items per document; the count is driven by the document, not a target.
