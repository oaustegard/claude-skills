# Glossary guide

`glossary.md` is the source of truth for every term of art. A document that uses a word the glossary does not define, or uses it differently, has a consistency bug. Expect it to grow to dozens of terms over the course of the build.

## Shape

```
# Glossary

The vocabulary used across these documents. When a document uses one of these words, it means exactly this.

## {Section: the surface}          e.g. The workspace / The terminal / The conversation
## {Section: the objects}          e.g. Records / Documents / Messages / Files
## {Section: state}                e.g. Selection and state
## {Section: modes}                e.g. Tools / Modes / Roles
## {Section: the interaction}      e.g. Gestures / Forms / Invocations / Turns
## {Section: input}                e.g. Input
## {Section: gesture endings}      e.g. Events that end or interrupt a gesture
## {Section: the document}         e.g. Document / Project / Session
## {Section: the interface}        e.g. Interface
## {Section: multi-user}           e.g. Collaboration
```

Each term is one paragraph:

```
**Term.** Definition in one to four sentences. Concrete numbers where they exist (a draft is kept for 30 days; the default page size is 50). The rule that makes the term load-bearing ("Archiving a project also revokes every share link; the two cannot be separated"). A related term in *italics* on first mention.
```

## Rules

- Define the *state words* with care: selected, hovered, editing, focused, active, locked, hidden, dirty, saved. These are where documents disagree most.
- Define the *gesture-ending words* as a section of their own (cancel, complete, interrupt, and what dispatches each). Every cancel/interrupt table in the repo relies on them.
- Define the units (screen vs. document coordinates, wall clock vs. frames, bytes vs. characters, local vs. server time) once, here.
- When a document needs a new term, add it in the right section with a full paragraph before using it. Do not coin a synonym for an existing term.
- Prefer the product's own UI wording when it has one ("Archive", "Share link") and say so; prefer a plain word over the code's identifier otherwise (say "draft", not `pendingMessageBuffer`).
- Revise the glossary in the consistency pass: read every definition against the documents that use the term and fix whichever is wrong.

Two entries, for the shape of a definition:

> **Dirty.** A record is dirty from the first edit that differs from what was last saved until the next successful save. A dirty record shows a dot in its tab title, and leaving the page asks for confirmation. Reverting every edit by hand does not clear it; only a save or an explicit *discard* does.

> **Safe to interrupt.** A command is safe to interrupt while it is still reading: nothing has been written and Ctrl+C leaves the working directory as it was. It stops being safe at the first write, which the command announces with a line beginning "Writing"; from then on Ctrl+C finishes the file in progress before exiting, and a second Ctrl+C exits at once and leaves that file partial.
