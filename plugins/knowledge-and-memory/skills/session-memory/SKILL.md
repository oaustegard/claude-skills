---
name: session-memory
description: Maintains a structured running-notes document during long work sessions. Use when the user says "session notes", "update notes", "start session notes", "show session notes", or when you recognize the current session has accumulated enough state (decisions, corrections, files touched, errors) that it risks being lost under context pressure. Stores notes as a procedure memory tagged [session-memory, active] so they survive container death within the same session thread.
metadata:
  version: 0.1.0
---

# Session Memory - Running Notes

Maintain a single structured markdown document that tracks what is happening
**right now** in the current work session. This is within-session continuity,
distinct from `remember()` (cross-session semantic memory) and `stash`
(coarse checkpoint).

## When to Use

Invoke on any of these triggers:

- User says "session notes", "update notes", "start session notes",
  "show session notes", "note the session", "write it down"
- User indicates they want continuity across context compression:
  "before you forget", "write that down", "for when context gets compressed"
- You have independently completed a meaningful block of work (file edits,
  a bugfix, a design choice, a reversal after correction) and no note has
  been updated for a while

Do NOT invoke for:

- One-off answers with no follow-up
- Cross-session persistence — that's `remember()`
- Coarse checkpoints intended for another session to resume — that's `stash`

## Template (Fixed Sections)

Every session note uses exactly these sections, in this order, with these
headers. **Preserve the structure on every update. Never rename or reorder
sections.** Update the *content* within sections; leave empty sections present
with a single `_(nothing yet)_` placeholder.

```markdown
# Session: {short title, 3-8 words, derived from the initial task}

## Current State
_What is actively being worked on right now. Explicit next step._

## Task Specification
_What the user originally asked for. Constraints, acceptance criteria,
design decisions that framed the work._

## Files and Functions
_Important paths touched or referenced, one per line, with a one-line
note on what they contain and why they matter._

## Errors & Corrections
_Errors encountered and how they were fixed. User corrections to my
approach — these have priority over routine progress entries._

## Key Decisions
_Choices made during the session with their rationale. One bullet per
decision. Lead with the choice, then the why._

## Worklog
_Terse, append-only, chronological. One line per attempt or step.
Prefix with ✓ (done), ✗ (failed), → (in progress), or ↺ (reverted)._
```

## Storage

Persist as a `procedure` memory via the `remembering` skill, so notes
survive container death within the session thread.

```python
from remembering.scripts import remember, recall, supersede

# First write in a session: create the memory
note_id = remember(
    note_markdown,
    "procedure",
    tags=["session-memory", "active"],
    priority=1,
)

# Subsequent updates: find the active note and supersede it
existing = recall(tags_all=["session-memory", "active"], n=1)
if existing:
    note_id = supersede(existing[0].id, updated_markdown, "procedure",
                        tags=["session-memory", "active"], priority=1)
```

**Session boundary:** when the user says "session done", "wrap up",
"end session", or the conversation is clearly winding down, retag the
active note from `active` to `archived` by superseding it with the same
body and `tags=["session-memory", "archived"]`.

One note is active at a time. If `recall(tags_all=["session-memory",
"active"])` returns more than one, the oldest is stale — archive it before
updating the current one.

## Update Discipline

On each invocation:

1. **Read the existing note** (if any) via `recall(tags_all=["session-memory",
   "active"], n=1)`. Work from its current body — do not regenerate from
   scratch.
2. **Update in place.** Edit the relevant sections; append to `## Worklog`.
   Do not drop prior content unless it is now wrong (then move the correction
   to `## Errors & Corrections`).
3. **Prioritize user corrections.** When the user pushes back or corrects an
   approach, that goes into `## Errors & Corrections` *before* other updates.
4. **Deduplicate against stash and explicit memories.** If an item is already
   captured in a stash or a `remember()` call, reference it by ID rather
   than restating. Notes are *supplementary*, not duplicative.
5. **Supersede, don't append.** Write the full updated document back via
   `supersede()`. This keeps exactly one active note per session.

## Budget

Target ~12K tokens for the note document. Prefer concise phrasing, but do
not truncate substantive content to hit the target — trigger
`## Key Decisions` consolidation (collapse related bullets) before cutting.
If the document exceeds ~20K tokens, compress `## Worklog` first (merge
consecutive ✓ entries into a single summary line, keep corrections and
decisions intact).

*Rationale: we run on 200K–1M context models, so the original 2K budget
from the issue spec was over-constrained. 12K matches Claude Code's
upstream design and leaves ample room for the surrounding conversation.*

## Surface to User

When the user asks to "show session notes", print the current note body
verbatim in a fenced code block. Do not paraphrase.

When updating silently (you triggered it yourself), confirm with a single
line: `Updated session notes (note id: <short-id>).` Do not dump the full
body unsolicited.

## Invariants

- Section headers and order are fixed. Updates change content, not structure.
- User corrections take priority over routine progress in ordering and detail.
- Notes do not duplicate what is already in stash or explicit memories.
- Manual invocation always works. Automatic triggers are a convenience, not
  a requirement.
- Exactly one `session-memory + active` memory exists per session. Stale
  actives are archived, not left dangling.

## Related

- `remembering` — cross-session memory store (where these notes persist)
- stash-resume-protocol (ops) — coarse session checkpoints
- context-hygiene (ops) — when and what to offload from context
