# Bug triage template

`bug-triage.md` collects every suspected defect raised anywhere in the documents (bodies and "Open questions" sections), deduplicated by root cause, written up so a product team can decide each one without re-reading the documents. Expect the open questions across the set to collapse to roughly half as many entries once merged.

## Building it

1. Grep every document for "Open questions", "suspected", "looks like a bug", "may be worth treating as a bug", "inconsistent", "not handled", and read each "Open questions and verification" section in full.
2. Sort the raised items into *unconfirmed* (the document could not tell from the code; stays in the document's open questions) and *looks wrong* (the code does something a user would not expect; becomes a triage entry).
3. Merge by root cause. Fourteen documents saying "a reload mid-way loses the draft" is one entry with fourteen "Raised by" links. Two documents describing different symptoms of one missing handler is one entry.
4. For each entry, go back to the code and pin the cause to a file and line range. An entry without a cause is an observation, not a triage item.
5. Assign severity and the decision needed. Sort the summary table by severity, then by area.
6. Write the Summary paragraph last: how many were raised, how many remain after merging, how many are high, what the largest clusters are.

## Shape

```
# Bug triage

A consolidated list of the defects and inconsistencies that the feature documents raised in their "Open questions and verification" sections and in their bodies. Each entry is read from {the source repo} and tests; the {n} that have been confirmed {in the running product} carry a **Status** line. {If filed: Every entry was filed as an issue on the source repo on the date (#NNNN–#NNNN); the Issue lines link them.} The list exists so the product team can decide, item by item, whether to fix, to document as intended, or to leave.

## Summary

{One paragraph: counts, clusters, what the high ones have in common.}

| ID | Title | Severity | Area | Decision needed | Issue |
| --- | --- | --- | --- | --- | --- |
| B-01 | {Title as a statement of the wrong behavior} | high | {area} | fix | {link or —} |
| ... | | | | | |

## High

### B-01: {Title}

- **Where the user meets it:** {The situation, in user terms.}
- **What happens / what was expected:** {Both halves, plainly.}
- **Reproduce:** {Numbered or prose steps; name the device if one is needed.}
- **Why (from the code):** {File paths and line ranges; the missing handler, the wrong comparison, the order of operations.}
- **Severity:** `high` | `medium` | `low`. {One clause on why.}
- **Decision needed:** `fix` | `product call`. {What the fix would be, or what the call is.}
- **Raised by:** [{document}]({path}#open-questions-and-verification), [{document}]({path}#{anchor}), ...
- **Status:** {Only if a verification pass touched it: confirmed / not reproduced / document was wrong, on what date, by what means, with the checklist item IDs.}
- **Issue:** {Only if filed: [owner/repo#NNNN](url).}

## Medium

...

## Low

...
```

## Severity and decision

- **high**: loses work, leaves the user in a state they cannot get out of, makes one common action do two things at once, silently does something different from what was confirmed, or affects every feature (a missing global handler).
- **medium**: wrong but recoverable; an undo step missing; an inconsistency between two features that should match; a wrong result in an uncommon path.
- **low**: cosmetic, a copy slip, a quirk only an expert would notice. Group tiny slips into one entry ("Small copy and rendering slips") with a sub-list.
- **fix**: the expected behavior is obvious and the entry says what the fix is.
- **product call**: reasonable people could want either behavior; the entry states both and what each costs.

## Filing upstream

Outward-facing; do only when the user asks, after confirming the target repo and the issue format. One issue per entry, title from the table, body from the entry (omit the "Raised by" links unless the description repo is public), a label if the repo uses them. Then add the Issue line to each entry, the Issue column to the table, and the range to the intro paragraph. Commit as `docs: revise bug-triage.md with links to the filed issues ({owner}/{repo} #NNNN–#NNNN)`.
