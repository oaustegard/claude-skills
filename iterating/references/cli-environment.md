# CLI Environment (Claude.ai with Project Knowledge)

This guide covers using the iterating skill in the CLI environment (claude.ai chat), where state is persisted via user-curated Project Knowledge files.

## User Acknowledgment

At session start, tell the user:
> "I'll create a structured Work Log document for you to curate into Project Knowledge. In future sessions, I'll automatically retrieve relevant context."

## Environment Detection

CLI environment lacks `CLAUDE_CODE_REMOTE` variable or it's not `'true'`.

## State Persistence: Project Knowledge

Create structured documents for users to curate into Project Knowledge. RAG system automatically retrieves context in future sessions.

## Document Format

Use WorkLog format with frontmatter for curated artifacts:

```markdown
---
title: [Descriptive Title] Work Log v1
date: YYYY-MM-DD
task: Research|Development|Debugging|Architecture|etc
version: v1
status: in_progress
---

# [Project Name] Work Log

## v1 | 2025-11-13 16:30 | Title

**Prev:** [previous context]
**Now:** [current goal]

**Progress:** [percentage OR milestone status]

**Files:**
- `path/to/file` (Why this file matters)
  - LX-Y: [Specific focus area]

**Work:**
+: [additions]
~: [changes]
!: [fixes]

**Decisions:**
- [what]: [why] (vs [alternatives])

**Works:** [effective approaches]
**Fails:** [ineffective approaches]

**Blockers:** [None OR specific blocker]

**Next:**
- [HIGH] [Critical action]
- [MED] [Important task]
- [LOW] [Nice to have]

**Open:** [questions needing answers]
```

**Key difference:** Curated artifact (user saves to Project Knowledge) vs running log (auto-appended in Code).

## Version Management

**In CLI environment:**
- Each document is standalone (not appended)
- User manually curates which versions to keep in Project Knowledge
- Versioning helps track evolution: "Auth Work Log v3" builds on "Auth Work Log v2"

## Project Knowledge Integration

### Automatic Retrieval

When Project Knowledge is enabled, the system automatically injects relevant context from:
- Past work documents user curated
- Previous findings marked as important
- Methodology notes and patterns
- Domain-specific knowledge accumulated over time

**You don't need to manually search project knowledge** - relevant content appears in your context automatically.

### Leveraging Retrieved Context

When you see project knowledge in context:

**Recognize it explicitly:**
```
"I see from project knowledge [Work Log v2] that we previously worked on..."
```

**Build on it:**
```
"Expanding on the v2 approach with improved file references..."
```

**Validate it:**
```
"Cross-referencing with current state to verify the decision from v1 still applies..."
```

**Update it if needed:**
```
"Previous work (v2) suggested X, but now we've learned Y. Creating v3 with updated approach..."
```

## Optimizing for RAG Retrieval

Structure outputs to maximize retrieval effectiveness:

**Good for retrieval:**
- Clear, descriptive titles ("JWT Authentication Work Log v2" not "Work Log Session 5")
- Key terms in topic sentences
- Self-contained insights (readable out of context)
- Explicit methodology notes
- Specific references to files/lines
- Version numbers in title for evolution tracking

**Poor for retrieval:**
- Vague headings ("Notes", "Work", "Session 5")
- Context-dependent pronouns ("it", "that", "the thing")
- Scattered insights across paragraphs
- Implicit assumptions
- No file/code references
- Missing version tracking

## Priority-Based Workflow

**When creating Work Log:**
1. Extract HIGH priority items prominently
2. User curates document to Project Knowledge
3. Next session: RAG retrieves context
4. Claude automatically focuses on HIGH priority items

**Example:**
```markdown
**Next:**
- [HIGH] Fix token refresh race condition (src/auth/oauth.ts:134)
- [HIGH] Implement login endpoint
- [MED] Add integration tests
- [LOW] Rate limiting
```

## Progress Tracking in CLI

**Critical for token/quota management:**

```markdown
**Progress:** Authentication 60% | Login ✅ | Refresh 🔄 | Tests ⏳

This helps if user runs out of tokens mid-session - they know exactly where to resume.
```

## Handoff to Code

**When user wants to implement in Claude Code:**

1. Generate comprehensive WorkLog with:
   - Clear task objective
   - File references with line ranges (relative paths)
   - Key decisions documented
   - HIGH priority next steps
   - Status: `in_progress`

2. Save to `/mnt/user-data/outputs/[Project]-WorkLog-v1.md`

3. Provide download link and instructions:
   > "I've created a WorkLog for implementation in Claude Code.
   > [Download WorkLog](computer:///mnt/user-data/outputs/[Project]-WorkLog-v1.md)
   >
   > To continue in Claude Code:
   > 1. Download the WorkLog
   > 2. Open your project in Claude Code
   > 3. Paste the WorkLog content at the start of your conversation
   > 4. Claude will recognize the format and start with HIGH priorities"

## Handoff from Code

**When user uploads WorkLog from Code:**

1. **Parse frontmatter:**
   - Extract version: `version: vN`
   - Extract status: `status: [in_progress|blocked|needs_review|completed]`

2. **Acknowledge explicitly:**
   > "From WorkLog v3, status: needs_review.
   > Summary: [what was completed]
   > Progress: [percentage or milestones]
   > Remaining: [HIGH priority items]"

3. **Status-based response:**
   
   **needs_review:** Review implementation, validate against decisions, provide feedback
   
   **blocked:** Identify blocker, help resolve (provide decision/info), update status to in_progress
   
   **in_progress:** Review progress, discuss next HIGH priority items, update decisions
   
   **completed:** Confirm completeness, archive or identify follow-up work

4. **Update WorkLog:**
   - Increment version (v3 → v4)
   - Add new decisions made in discussion
   - Update next steps based on review
   - Change status if appropriate

5. **Return updated WorkLog for continuation in Code**

## User Communication

After creating a document, prompt the user:

> "I've created Work Log v{N} with [summary]. Review the content and consider adding to your Project Knowledge. Key items to preserve:
> - [Decision about X]
> - [Effective approach for Y]
> - [HIGH priority next steps]
>
> In your next session, I'll automatically retrieve this context."

At the start of a new session, acknowledge retrieved context:

> "Based on project knowledge [Work Log v2], I can see we previously [summary]. Progress was at 60%. I'll continue with HIGH priority: [item]..."

## Example Flow

**Session 1 (Chat):**
User: "Help me design an authentication system"

Claude: [Research and decisions]

> "I've created 'Auth Architecture Work Log v1' documenting our JWT decision and file structure. Curate the key architectural decisions to Project Knowledge."

**Session 2 (Chat):**
> "From project knowledge [Auth Work Log v1], we decided on JWT with 1h/7d tokens. Ready to hand off to Code for implementation?"

User: "Yes"

Claude: [Creates handoff document]

> "Download this Work Log and open in Claude Code to implement."

**Session 3 (Code):**
User: [Pastes Work Log in Code]

Claude in Code: "From Work Log v1, implementing JWT auth. Starting with HIGH priority: token service..."

[Implements]

Claude in Code: "Updated Work Log v2 with implementation progress."

**Session 4 (Chat):**
User: [Uploads Work Log v2]

Claude: "From Work Log v2, token service complete (60% progress). Remaining HIGH priority: login endpoint and refresh logic. Ready to continue in Code or discuss approach first?"
