# Desktop Environment (Claude Code Desktop)

This guide covers using the iterating skill in Claude Code desktop environment, where state is persisted via local WorkLog.md files.

## User Acknowledgment

At session start, tell the user:
> "I'll track our progress in WorkLog.md locally. Each session, I'll document key decisions and next steps with version tracking."

## Environment Detection

Desktop environment has `CLAUDE_CODE_REMOTE` but it's not `'true'` (or may be absent).

## State Persistence: Local WorkLog.md

Maintain state across sessions using WorkLog.md in the project directory.

**Version management:**
- Check for existing WorkLog: `ls -1 WorkLog*.md 2>/dev/null | sort -V | tail -1`
- Parse version from frontmatter: `version: vN`
- Increment on each update: v1 → v2 → v3

## WorkLog Format

Same format as web environment - see [web-environment.md](web-environment.md) for complete details.

```markdown
---
version: v1
status: in_progress
---

# [Project Name] Work Log

## v1 | YYYY-MM-DD HH:MM | Title

**Prev:** [context]
**Now:** [goal]
**Progress:** [percentage or milestones]

**Files:**
- `path/to/file` (relevance)
  - LX-Y: [focus area]

**Work:** +: ~ : ! :
**Decisions:** - [what]: [why] (vs [alt])
**Works:** [effective]
**Fails:** [ineffective]
**Blockers:** [none or specific]
**Next:** - [HIGH/MED/LOW] [action]
**Open:** [questions]
```

## Key Differences from Web Environment

**Git tracking:**
- Desktop WorkLog.md is typically NOT git-tracked
- User manually backs up or commits if desired
- More ephemeral than web environment

**Persistence:**
- WorkLog persists on local machine
- Not automatically synced across devices
- User responsible for backup/transfer

## Priority-Based Workflow

Same as web environment:

**Session start:**
1. Read WorkLog.md
2. Parse HIGH priority items
3. Acknowledge: "From WorkLog v3, continuing with HIGH priority: [item]"
4. Execute HIGH items first

## Progress Tracking

**Always update progress indicators:**

```markdown
**Progress:** 60% | Token service ✅ | Login endpoint 🔄 | Tests ⏳
```

**Why:** If user runs out of tokens/quota, progress shows where to resume.

## Handoff Scenarios

### Desktop → Chat

**When user wants to discuss in claude.ai:**

1. User manually copies WorkLog.md content
2. Pastes into claude.ai chat
3. Claude recognizes WorkLog format
4. Continues from documented context

### Chat → Desktop

**When user pastes WorkLog from chat:**

1. **Detect handoff format:**
   - YAML frontmatter with `version:` and `status:`
   - WorkLog structure with task objective

2. **Parse and acknowledge:**
   > "I see you're starting from WorkLog v1, status: in_progress.
   >
   > Task: [objective]
   > HIGH priorities: [list HIGH items]
   >
   > Starting with first HIGH priority: [item]"

3. **Save to local WorkLog.md and begin work**

## Example Session

**Session 1:**
> "Creating WorkLog v1 for payment integration. HIGH priority: Stripe setup."

[Implements Stripe configuration]

> "Updated WorkLog v1: Stripe configured. Next HIGH: checkout endpoint."

**Session 2:**
> "From WorkLog v1, progress 30%. Continuing with HIGH priority: checkout endpoint."

[Implements checkout]

> "Updated WorkLog v2: Checkout complete (60% progress). Remaining: webhook handling and tests."

## User Communication

- **After update:** "Updated WorkLog v{N}. Progress: [summary]"
- **New session:** "From WorkLog v{N}, status: {status}. Last: [summary]. Continuing with HIGH: [item]"
- **Blocked:** "Updated WorkLog status to blocked: [reason]. Waiting on [owner/resource]."

## Backup Recommendations

Suggest to user:
> "Consider backing up WorkLog.md regularly, especially after major milestones. You can:
> - Copy to cloud storage
> - Commit to git (if using git)
> - Keep alongside project files"
