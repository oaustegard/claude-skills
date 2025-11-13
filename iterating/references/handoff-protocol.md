# Handoff Protocol: Chat ↔ Code

Structured context transfer between claude.ai chat and Claude Code environments.

## Core Concept

**Problem:** Moving between chat (planning/discussion) and code (implementation) loses context.

**Solution:** Work Log as portable context carrier with compressed state:
- Task objective and progress
- File references with line ranges
- Key decisions with rationale
- Prioritized next steps
- Status and blockers

## Token Optimization

**Traditional approach:** Replay entire conversation (~10,000+ tokens)

**Work Log approach:** Compressed state (~500-2,000 tokens)

**Key innovation:** File references instead of full contents:

```markdown
# Instead of pasting 500 lines of code:
**Files:**
- `src/auth/oauth.ts` (OAuth implementation needs refactoring)
  - L45-67: Current token validation logic
  - L123-145: Refresh token handling (race condition on L134)
```

**Token savings:** 40-95x reduction per file

## Chat → Code Handoff

### Trigger Patterns

User says:
- "implement this in Claude Code"
- "hand this off to Code"
- "ready to code this"
- "create handoff document"

### Workflow

1. **Extract state from conversation:**
   - What are we building? (task objective)
   - What decisions were made? (with rationale)
   - What files are involved? (with specific line ranges)
   - What's the implementation plan? (prioritized steps)

2. **Generate Work Log:**

```markdown
---
version: v1
status: in_progress
---

# [Project Name] Work Log

## v1 | YYYY-MM-DD HH:MM | [Task Title]

**Prev:** Starting new work
**Now:** [Clear description of what to implement]

**Progress:** 0% | Planning complete ✅ | Implementation pending ⏳

**Files:**
- `path/to/file` (Why this file matters for the task)
  - LX-Y: [What to implement or change here]
  - LA-B: [Another area that needs work]

**Decisions:**
- [Decision made]: [Rationale] (vs [alternative considered])
- [Another decision]: [Why this approach]

**Next:**
- [HIGH] [First critical implementation step]
- [HIGH] [Second critical step]
- [MED] [Important but not blocking]
- [LOW] [Nice to have]

**Blockers:** None

**Open:** [Any questions that need answering during implementation]
```

3. **Save to outputs:**
   ```bash
   cp worklog.md /mnt/user-data/outputs/[Project]-WorkLog-v1.md
   ```

4. **Provide download link:**
   > "I've created a Work Log for handoff to Claude Code. [Download WorkLog](computer:///mnt/user-data/outputs/Auth-WorkLog-v1.md)
   >
   > **To continue in Claude Code:**
   > 1. Download the Work Log
   > 2. Open your project in Claude Code
   > 3. Start a new conversation
   > 4. Paste the entire Work Log content
   > 5. I'll recognize the format and continue with HIGH priority items"

## Code → Chat Handoff

### Trigger: User Uploads Work Log

When user uploads or pastes a Work Log from Code session:

### Workflow

1. **Parse Work Log:**
   - Extract version: `version: vN`
   - Extract status: `status: in_progress|blocked|needs_review|completed`
   - Find latest entry (highest version number)
   - Identify progress, decisions, next steps

2. **Acknowledge explicitly:**
   > "I see you're continuing from Work Log v3, status: needs_review.
   >
   > **Summary:** [brief summary of what was accomplished]
   > **Progress:** [percentage or milestones]
   > **Remaining:** [HIGH priority items from Next section]"

3. **Determine mode:**

   **If status: needs_review**
   - Review the implementation
   - Examine code at referenced line ranges
   - Validate against decisions
   - Provide feedback or approve

   **If status: blocked**
   - Identify blocker from WorkLog
   - Help resolve (make decision, provide info, etc)
   - Update status to in_progress once unblocked

   **If status: in_progress**
   - Review progress
   - Discuss next HIGH priority items
   - Prepare updated Work Log for return to Code

   **If status: completed**
   - Confirm completeness
   - Archive or mark as done
   - Identify follow-up work if any

4. **Update Work Log:**
   - Increment version (v3 → v4)
   - Document new decisions made in chat
   - Update next steps
   - Update status if changed

5. **Return to user:**
   > "I've updated the Work Log to v4 with [changes made]. [Download updated WorkLog](computer:///mnt/user-data/outputs/Auth-WorkLog-v4.md)
   >
   > Ready to continue in Code, or shall we discuss further?"

## Status-Based Workflows

### in_progress → Chat

**User brings Work Log for discussion:**
- Review progress
- Discuss approach for next steps
- Make architectural decisions
- Update decisions and next steps
- Return to Code for continued implementation

### blocked → Chat

**User needs help unblocking:**
- Identify specific blocker
- Provide needed information or decision
- Update status to in_progress
- Return to Code to continue

### needs_review → Chat

**User wants review/approval:**
- Review implementation against decisions
- Check HIGH priority items completed
- Validate approach
- Either approve (→ completed) or request changes (→ in_progress)

## File References Best Practices

**DO:**
- Use relative paths from project root: `src/auth/oauth.ts`
- Include line ranges: `L45-67`
- Add specific notes: `(race condition on L134)`
- Explain relevance: `(OAuth implementation needs refactoring)`

**DON'T:**
- Use absolute paths: ~~`/home/claude/project/src/auth/oauth.ts`~~
- Reference ephemeral locations: ~~`/tmp/file.ts`~~
- Paste full file contents (defeats token optimization)
- Use vague references: ~~`auth file around line 100 somewhere`~~

**Why:** Each session has fresh compute environment. Absolute paths to working directory won't persist.

## Example: Complete Handoff Cycle

### Session 1: Chat (Planning)

User: "I need to implement JWT authentication"

Claude:
- Discusses approach
- Makes key decisions (JWT vs sessions, token lifetimes, etc)
- Plans architecture
- Identifies files and implementation steps

> "I've created a Work Log for handoff. [Download](computer://...)"

### Session 2: Code (Implementation)

User: [Pastes Work Log v1 in Code]

Claude in Code:
- Recognizes Work Log format
- Reads v1, status: in_progress
- Focuses on HIGH priority items
- Implements token service
- Updates Work Log to v2

> "Implementation 60% complete. Updated Work Log v2."

### Session 3: Chat (Review)

User: [Uploads Work Log v2]

Claude:
- Parses v2, status: needs_review
- Reviews implementation
- Suggests improvements
- Updates next steps
- Creates v3

> "Reviewed your implementation. Suggested some error handling improvements. [Download v3](computer://...)"

### Session 4: Code (Refinement)

User: [Pastes Work Log v3]

Claude in Code:
- Applies feedback
- Completes remaining HIGH priority items
- Updates status to completed
- Creates v4

> "All HIGH priority items complete. Work Log v4 marked as completed."

## Handoff Checklist

**Before Chat → Code:**
- [ ] Clear task objective stated
- [ ] Key decisions documented with rationale
- [ ] Files identified with line ranges
- [ ] Next steps prioritized (HIGH/MED/LOW)
- [ ] Status set to in_progress
- [ ] Progress indicator included

**Before Code → Chat:**
- [ ] Version incremented
- [ ] Progress updated
- [ ] New decisions added
- [ ] Status reflects current state
- [ ] HIGH priority items clear
- [ ] Blockers documented if any

## Troubleshooting

**Work Log not recognized:**
- Ensure frontmatter present with `version:` and `status:`
- Check format matches template
- Verify file is markdown

**Context seems lost:**
- Check file references use relative paths
- Verify decisions section comprehensive
- Ensure progress indicator present
- Review next steps for clarity

**Too many versions:**
- Archive completed Work Logs
- Focus on current/active only
- Use clear naming: `[Project]-WorkLog-v3.md`
