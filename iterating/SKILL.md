---
name: iterating
description: Multi-conversation methodology for iterative stateful work with context accumulation. Use when users request work that spans multiple sessions (research, debugging, refactoring, feature development), need to build on past progress, or explicitly mention iterative work, development logs, project knowledge, or cross-conversation learning.
---

# Iterating

A methodology for conducting iterative stateful work across multiple conversations where progress and learnings accumulate through persistent context storage.

## Core Concept

Maintain context across multiple sessions by persisting state:
- **Web/Desktop** (Claude Code): DEVLOG.md in working directory
- **CLI** (Claude.ai): Documents for user-curated Project Knowledge

## Quick Start

Detect environment (`CLAUDE_CODE_REMOTE`) and choose persistence:

- **Web/Desktop**: DEVLOG.md (see [references/web-environment.md](references/web-environment.md) and [references/desktop-environment.md](references/desktop-environment.md))
- **CLI**: Curated documents (see [references/cli-environment.md](references/cli-environment.md))

## Core Workflow

**Session N:**
1. Detect environment and explain approach
2. Perform the work
3. Document learnings (append to DEVLOG.md or create curated document)
4. Inform user what was documented

**Session N+1:**
1. Retrieve past context (read DEVLOG.md or leverage Project Knowledge)
2. Acknowledge past work explicitly
3. Address open items from previous sessions
4. Continue documentation

## What to Document

**Do include:**
- Key decisions and their rationale
- Effective and ineffective approaches
- Important discoveries or insights
- Architectural choices
- Next steps and open questions
- Links to relevant code/files

**Don't include:**
- Every minor code change (that's what git is for)
- Obvious or trivial information
- Raw dumps of data or logs
- Implementation details (document in code comments)

## Unified Documentation Format

**All environments use the same structure** (optimized for RAG retrieval):

```markdown
## [YYYY-MM-DD HH:MM] - Session: [Descriptive Title]

### Context
[What we're working on and why]

### Work Completed
**Added:**
- [New features, code, or insights]

**Changed:**
- [Modifications to existing work]

**Fixed:**
- [Bugs resolved, issues addressed]

### Key Decisions
- **Decision:** [What was decided]
  **Rationale:** [Why this approach]
  **Alternatives considered:** [What else was evaluated]

### Effective Approaches
- [What strategies/techniques worked well]

### Ineffective Approaches
- [What didn't work and why]

### Open Questions
- [Unresolved issues or areas needing investigation]

### Next Steps
- [ ] [Specific next action]
- [ ] [Follow-up task]
```

**Workflow differences:**
- **Web/Desktop**: Append to running log continuously
- **CLI**: Create polished, curated documents for user to save

**See reference files for implementation details.**

## Common Patterns

### Pattern: Incremental Implementation
- **Session 1**: Core functionality (get it working)
- **Session 2**: Error handling and edge cases
- **Session 3**: Testing and documentation
- **Session 4**: Optimization and refinement

### Pattern: Spike and Implement
- **Session 1**: Quick spike to validate approach
- **Session 2**: Implement properly based on learnings
- **Session 3**: Polish and production-readiness

### Pattern: Research and Apply
- **Session 1**: Research approaches and best practices
- **Session 2**: Apply learnings to implementation
- **Session 3**: Iterate based on results

See [references/advanced-patterns.md](references/advanced-patterns.md) for detailed patterns including:
- Multi-session feature development
- Debugging across sessions
- Architecture evolution tracking
- Cross-session synthesis

## Quality Standards

### For Initial Session
- [ ] Environment detected and appropriate persistence chosen
- [ ] Approach explained to user
- [ ] Work completed and documented
- [ ] Effective and ineffective approaches noted
- [ ] Decisions with rationale captured
- [ ] Next steps identified clearly
- [ ] State persisted (DEVLOG updated or document created)

### For Continuing Sessions
- [ ] Past context retrieved and acknowledged
- [ ] Built on (not repeated) previous work
- [ ] Addressed open items from previous sessions
- [ ] Cross-referenced with past decisions
- [ ] Updated or refined previous conclusions
- [ ] Maintained consistent documentation format

### For Documentation Quality
- [ ] Self-contained entries (readable alone)
- [ ] Clear headings with key terms
- [ ] Specific references to code/files
- [ ] Rationale for decisions explicit
- [ ] Confidence levels or status indicated
- [ ] Optimized for future retrieval

## Anti-Patterns to Avoid

**Don't:**
- Repeat work from previous sessions without acknowledging
- Ignore past decisions or learnings
- Create documentation in inconsistent formats
- Assume user remembers previous context
- Log every trivial detail
- Dump raw data into the log
- Forget to update state at session end

**Do:**
- Explicitly reference past work
- Build on previous decisions
- Maintain consistent documentation
- Re-state key context when continuing
- Log meaningful progress and decisions
- Curate signal over noise
- Always capture state before ending

## Example Usage

### Web Environment

**User (Session 1):** "Help me debug this performance issue."

**Claude:**
```
I'll track our debugging progress in DEVLOG.md.

[Investigates, tries approaches]

Updated DEVLOG.md with findings:
- Identified bottleneck in serialization (900ms)
- Tested 3 approaches: caching (ineffective), batching (moderate), streaming (best)
- Decision: Switch to streaming approach
- Next: Implement streaming serialization

In the next session, we can continue with the implementation.
```

**User (Session 2):** "Let's continue."

**Claude:**
```
From DEVLOG.md, I can see we:
- Identified serialization bottleneck (900ms)
- Decided on streaming approach

I'll implement the streaming serialization now...

[Implements]

Updated DEVLOG.md:
- Implemented streaming (120ms - 87% reduction!)
- Trade-off: +15MB memory (acceptable)
- Next: Add monitoring
```

### Desktop Environment

**User (Session 1):** "Help me build a REST API. I'm using Claude Desktop."

**Claude:**
```
I'll track our progress in DEVLOG.md.

[Works on API setup]

Created DEVLOG.md with this session's work:
- Project structure setup
- Express.js server configuration
- Decision: Use TypeScript for type safety
- Next: Implement first endpoints
```

**User (Session 2):** "Let's continue building the API."

**Claude:**
```
From DEVLOG.md:
- Set up project with Express and TypeScript
- Next: Implement endpoints

I'll implement the endpoints now...

[Implements]

Updated DEVLOG.md:
- Implemented GET /users and POST /users endpoints
- Added request validation with Zod
- Next: Add database integration
```

### CLI Environment

**User (Session 1):** "Research microservice patterns. I'll add findings to project knowledge."

**Claude:**
```
I'll structure my research for Project Knowledge curation.

[Researches]

Created document covering:
- Event-driven architecture recommended
- Message queues for reliability
- Avoid synchronous HTTP chains

Review and add insights to Project Knowledge. Next session, I'll retrieve this context automatically.
```

**User (Session 2):** "Let's design the event schemas."

**Claude:**
```
Based on project knowledge, we decided on event-driven architecture with message queues. I'll design schemas following those patterns...

[Designs schemas]

Created schemas building on our architecture decision. Adding to document for Project Knowledge.
```

## Working with Other Skills

- **updating-knowledge**: Use for complex queries requiring 10+ tool calls in single session. Iterating focuses on cross-session learning.
- **convening-experts**: Can be used within a session for multi-perspective analysis. Document the outputs.
- **docx/xlsx/pdf skills**: Create professional deliverables for project knowledge (CLI) or reference in DEVLOG (web).

## Success Metrics

Iterative work is successful when:
- Each session builds on (not repeats) previous work
- Context accumulates efficiently over time
- Patterns and learnings emerge naturally
- Time-to-completion decreases across sessions
- Understanding compounds across conversations
- Less time spent re-explaining context
- More time spent making progress

## Reference Documentation

- **[references/web-environment.md](references/web-environment.md)** - Web environment (git-tracked DEVLOG.md)
- **[references/desktop-environment.md](references/desktop-environment.md)** - Desktop environment (local DEVLOG.md)
- **[references/cli-environment.md](references/cli-environment.md)** - CLI environment (Project Knowledge)
- **[references/advanced-patterns.md](references/advanced-patterns.md)** - Multi-session patterns
