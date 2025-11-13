---
name: iterating
description: Multi-conversation methodology for iterative stateful work with context accumulation. Use when users request work that spans multiple sessions (research, debugging, refactoring, feature development), need to build on past progress, explicitly mention iterative work, work logs, project knowledge, cross-conversation learning, or when preparing handoffs between chat and code environments.
---

# Iterating

Maintain context across multiple sessions by persisting state in Work Logs.

## Core Concept

- **Web/Desktop** (Claude Code): WorkLog.md in repository
- **CLI** (Claude.ai): Documents for user-curated Project Knowledge
- **Handoffs**: Structured transfer between chat ↔ code environments

## Quick Start

Detect environment (`CLAUDE_CODE_REMOTE`) and see appropriate reference:

- **Web**: [references/web-environment.md](references/web-environment.md)
- **Desktop**: [references/desktop-environment.md](references/desktop-environment.md)
- **CLI**: [references/cli-environment.md](references/cli-environment.md)

## WorkLog Format

Compressed for AI parsing - maximize information density:

```markdown
---
version: v1
status: in_progress
---

# [Project Name] Work Log

## v1 | YYYY-MM-DD HH:MM | Title

**Prev:** [previous context]
**Now:** [current goal]

**Progress:** [X% complete OR milestone achieved]

**Files:**
- `path/to/file.ext` (Why this file matters)
  - L45-67: [What to examine/change here]
  - L123-145: [Another area, specific issue]

**Work:**
+: [additions with file:line]
~: [changes with file:line]
!: [fixes with file:line]

**Decisions:**
- [what]: [why] (vs [alternatives])

**Works:** [effective approaches]
**Fails:** [ineffective, why]

**Blockers:** [None OR specific blocker with owner/ETA]

**Next:**
- [HIGH] [Critical action item]
- [MED] [Important but not urgent]
- [LOW] [Nice to have]

**Open:** [questions needing answers]
```

## Version Management

**Simple incremental versioning:** v1 → v2 → v3 (not semantic versioning)

**Multiple WorkLogs:**
- If multiple found: use highest version number
- Format: `WorkLog v3.md` (optional in filename)
- Frontmatter: `version: v3` (required)
- Increment on each session update

**Finding WorkLogs:**
```bash
# Check for existing WorkLog
ls -1 WorkLog*.md WORKLOG*.md worklog*.md 2>/dev/null | sort -V | tail -1
```

## Core Workflow

**Session N:**
1. Detect environment and acknowledge approach to user
2. Check for existing WorkLog (use highest version)
3. Perform the work
4. Update WorkLog with progress, decisions, next steps
5. Increment version (v1 → v2)
6. Inform user what was documented

**Session N+1:**
1. Retrieve past context (read WorkLog or leverage Project Knowledge)
2. Acknowledge past work explicitly with version
3. Address HIGH priority items first
4. Check blockers and progress indicators
5. Continue documentation, increment version

## Status States

- **in_progress**: Active work continuing normally
- **blocked**: Waiting on external dependency, decision, or resource
- **needs_review**: Ready for human inspection/approval
- **completed**: Task finished, may archive

## Priority System

**Next steps must be prioritized:**

- **[HIGH]**: Critical items that block other work or must be done immediately
- **[MED]**: Important items that should be done soon
- **[LOW]**: Nice-to-have improvements or future considerations

**Claude should tackle HIGH priority items first** unless explicitly told otherwise.

## File References

**Format:**

```markdown
**Files:**
- `src/auth/oauth.ts` (OAuth implementation needs refactoring)
  - L45-67: Current token validation logic
  - L123-145: Refresh token handling (race condition on L134)
  - L200-220: Error handling for expired tokens
```

**Critical:** File paths must be relative to project root, NOT `/home/claude/` paths (each session has fresh compute environment).

**When to include code:**
- Small snippets (5-10 lines) for context
- Specific error messages
- Configuration examples

## Progress Tracking

**CRITICAL:** Always include progress indicators due to token/quota constraints.

**For short tasks (1-3 sessions):**
```markdown
**Progress:** 60% complete
```

**For long projects (5+ sessions):**
```markdown
**Progress:** Phase 2 of 3 | Auth complete ✅ | Payments 50% 🔄 | UI planned ⏳
```

**Why this matters:** User may run out of tokens/quota before completing full plan. Progress indicators help resume at the right point.

## What to Document

**Include:**
- Key decisions with rationale and alternatives
- Effective and ineffective approaches
- Important discoveries
- File references with line ranges
- Next steps with priorities
- Progress indicators
- Blockers with owner/ETA

**Don't include:**
- Minor code changes (use git for that)
- Obvious information
- Raw data dumps
- Implementation details (use code comments)

## Reference Documentation

- **[references/web-environment.md](references/web-environment.md)** - Web (git-tracked WorkLog)
- **[references/desktop-environment.md](references/desktop-environment.md)** - Desktop (local WorkLog)
- **[references/cli-environment.md](references/cli-environment.md)** - CLI (Project Knowledge)
- **[references/advanced-patterns.md](references/advanced-patterns.md)** - Multi-session patterns
