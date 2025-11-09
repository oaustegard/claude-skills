---
name: iterating
description: Multi-conversation methodology for iterative stateful work with context accumulation. Use when users request work that spans multiple sessions (research, debugging, refactoring, feature development), need to build on past progress, or explicitly mention iterative work, development logs, project knowledge, or cross-conversation learning.
---

# Iterating

Maintain context across multiple sessions by persisting state.

## Core Concept

- **Web/Desktop** (Claude Code): DEVLOG.md in working directory
- **CLI** (Claude.ai): Documents for user-curated Project Knowledge

## Quick Start

Detect environment (`CLAUDE_CODE_REMOTE`) and see appropriate reference:

- **Web**: [references/web-environment.md](references/web-environment.md)
- **Desktop**: [references/desktop-environment.md](references/desktop-environment.md)
- **CLI**: [references/cli-environment.md](references/cli-environment.md)

## DEVLOG Format

Compressed for AI parsing - maximize information density:

```markdown
## YYYY-MM-DD HH:MM | Title

**Prev:** [previous context]
**Now:** [current goal]

**Work:**
+: [additions with file:line]
~: [changes with file:line]
!: [fixes with file:line]

**Decisions:**
- [what]: [why] (vs [alternatives])

**Works:** [effective approaches]
**Fails:** [ineffective, why]

**Open:** [questions]
**Next:** [actions]
```

## Core Workflow

**Session N:**
1. Detect environment and acknowledge approach to user
2. Perform the work
3. Document learnings (append to DEVLOG.md or create curated document)
4. Inform user what was documented

**Session N+1:**
1. Retrieve past context (read DEVLOG.md or leverage Project Knowledge)
2. Acknowledge past work explicitly
3. Address open items from previous sessions
4. Continue documentation

## What to Document

**Include:**
- Key decisions with rationale and alternatives
- Effective and ineffective approaches
- Important discoveries
- Next steps and open questions
- Links to code/files

**Don't include:**
- Minor code changes (use git for that)
- Obvious information
- Raw data dumps
- Implementation details (use code comments)

## Reference Documentation

- **[references/web-environment.md](references/web-environment.md)** - Web (git-tracked DEVLOG.md)
- **[references/desktop-environment.md](references/desktop-environment.md)** - Desktop (local DEVLOG.md)
- **[references/cli-environment.md](references/cli-environment.md)** - CLI (Project Knowledge)
- **[references/advanced-patterns.md](references/advanced-patterns.md)** - Multi-session patterns
