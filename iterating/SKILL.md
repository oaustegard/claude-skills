---
name: iterating
description: Multi-conversation methodology for iterative stateful work with context accumulation. Use when users request work that spans multiple sessions (research, debugging, refactoring, feature development), need to build on past progress, or explicitly mention iterative work, development logs, project knowledge, or cross-conversation learning.
---

# Iterating

A methodology for conducting iterative stateful work across multiple conversations where progress and learnings accumulate through persistent context storage.

## Core Concept

This skill enables you to maintain context and build on previous work across multiple sessions by:
- **Web environment**: Using DEVLOG.md in the repository for state persistence
- **CLI environment**: Creating documents for user-curated Project Knowledge

## When to Use This Skill

**Trigger patterns:**
- "Let's continue working on X across multiple sessions"
- "Build on our previous work about..."
- "Track progress iteratively over time"
- "I'll add findings/decisions to project knowledge"
- User explicitly references Project Knowledge or development logs

**Task characteristics:**
- Multi-session development or research effort
- Accumulating knowledge/progress over time
- Need to avoid repeating unsuccessful approaches
- Complex debugging spanning multiple sessions
- Incremental feature development with learnings

## Quick Start

### 1. Detect Environment

```python
import os
is_web_environment = os.environ.get('CLAUDE_CODE_REMOTE') == 'true'
```

### 2. Choose Persistence Method

- **Web (CLAUDE_CODE_REMOTE='true')**: Use DEVLOG.md in repository
  - See [references/web-environment.md](references/web-environment.md) for details
- **CLI (no CLAUDE_CODE_REMOTE)**: Create documents for Project Knowledge
  - See [references/cli-environment.md](references/cli-environment.md) for details

### 3. Acknowledge to User

**Web:**
> "I'll track our progress in DEVLOG.md in the repository. Each session, I'll document key decisions, findings, and next steps so we can build on this work in future conversations."

**CLI:**
> "I'll structure my output so you can curate the best insights into Project Knowledge. In future sessions, I'll automatically retrieve relevant past work to build on what we've learned."

## Core Workflow

### Session N: Initial Work

1. **Detect environment** and explain approach to user
2. **Perform the work** (research, coding, debugging, etc.)
3. **Document learnings**:
   - **Web**: Append entry to DEVLOG.md with context, decisions, approaches, next steps
   - **CLI**: Create structured document for user to curate
4. **Capture state** before ending session
5. **Inform user** about what was documented and next steps

### Session N+1: Continuing Work

1. **Retrieve past context**:
   - **Web**: Read DEVLOG.md and parse recent entries
   - **CLI**: Leverage automatically-injected Project Knowledge
2. **Acknowledge past work** explicitly to user
3. **Address open items** from previous sessions
4. **Build on previous decisions** and learnings
5. **Continue documentation** in same format

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

## Documentation Format

### Web Environment (DEVLOG.md)

```markdown
## [YYYY-MM-DD HH:MM] - Session: [Brief Title]

### Context
[What we're working on and why]

### Work Completed
**Added:** [New features, code, insights]
**Changed:** [Modifications]
**Fixed:** [Bugs resolved]

### Key Decisions
- **Decision:** [What]
  **Rationale:** [Why]
  **Alternatives considered:** [What else]

### Effective Approaches
- [What worked well]

### Ineffective Approaches
- [What didn't work and why]

### Open Questions
- [Unresolved issues]

### Next Steps
- [ ] [Specific next actions]
```

See [references/web-environment.md](references/web-environment.md) for complete format and implementation.

### CLI Environment (Project Knowledge)

```markdown
# [Topic/Task] - Session [N]

## Quick Summary
[2-3 sentences capturing essence]

## Methodology Notes
**Effective strategies:** [What worked]
**Ineffective approaches:** [What didn't]

## Key Progress
### [Area]
**What was done:** [Description]
**Key insight:** [Takeaway]
**Confidence:** [High/Medium/Low]

## Decisions Made
- **Decision:** [What]
  **Rationale:** [Why]

## Open Items
- [Unfinished work]

## Recommended Next Steps
- [Next actions]
```

See [references/cli-environment.md](references/cli-environment.md) for complete format and RAG optimization.

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

For detailed information on specific topics:

- **[references/web-environment.md](references/web-environment.md)** - Complete guide to using DEVLOG.md in Claude Code on the web
  - DEVLOG.md format and structure
  - Implementation code (update_devlog, read_devlog)
  - Development log management and maintenance
  - Detailed examples

- **[references/cli-environment.md](references/cli-environment.md)** - Complete guide to Project Knowledge in CLI
  - Document format templates
  - RAG optimization techniques
  - Project Knowledge integration
  - Detailed examples

- **[references/advanced-patterns.md](references/advanced-patterns.md)** - Advanced patterns for complex work
  - Multi-session feature development
  - Debugging across sessions
  - Architecture evolution tracking
  - Cross-session synthesis
  - Multi-session project templates
