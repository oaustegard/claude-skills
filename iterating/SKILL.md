---
name: iterating
description: Multi-conversation methodology for iterative stateful work with context accumulation. Use when users request work that spans multiple sessions (research, debugging, refactoring, feature development), need to build on past progress, or explicitly mention iterative work, development logs, project knowledge, or cross-conversation learning.
---

# Iterating

A methodology for conducting iterative stateful work across multiple conversations where progress and learnings accumulate through persistent context storage.

## Environment Detection

Detect your environment to choose the appropriate state persistence method:

```python
import os

is_web_environment = os.environ.get('CLAUDE_CODE_REMOTE') == 'true'

if is_web_environment:
    # Use development log in repository (DEVLOG.md)
    state_method = "devlog"
else:
    # Use Project Knowledge (user-curated files)
    state_method = "project_knowledge"
```

## Core Workflow

### CLI Environment (Project Knowledge)
```
Session N: Work → Structured Output → Human Curates → Project Knowledge
                                                              ↓
Session N+1: ←──────────── RAG Retrieval ────────────────────┘
             Continue with accumulated context
```

### Web Environment (Development Log)
```
Session N: Work → Update DEVLOG.md → Git Commit
                         ↓
Session N+1: ←─── Read DEVLOG.md ───┘
             Continue with accumulated context
```

## When to Use This Skill

**Trigger patterns:**
- "Let's continue working on X across multiple sessions"
- "Build on our previous work about..."
- "Track progress iteratively over time"
- "I'll add good findings/decisions to project knowledge"
- User explicitly enables/references Project Knowledge or development logs

**Task characteristics:**
- Multi-session development or research effort
- Accumulating knowledge/progress over time
- Need to avoid repeating unsuccessful approaches
- Building comprehensive understanding across conversations
- Pattern recognition from past work
- Complex debugging spanning multiple sessions
- Incremental feature development with learnings

## Session N: Initial Work

### 1. Detect Environment and Acknowledge

At the start, detect the environment and explain the approach:

**Web Environment:**
> "I'll track our progress in a development log (DEVLOG.md) in the repository. Each session, I'll document key decisions, findings, and next steps so we can build on this work in future conversations."

**CLI Environment:**
> "I'll structure my output so you can curate the best insights into Project Knowledge. In future sessions, I'll automatically retrieve relevant past work to build on what we've learned."

### 2. Perform Work

Execute the requested task:
- Research and investigation
- Code development and debugging
- Architecture decisions
- Problem-solving and experimentation
- Refactoring and optimization

### 3. Document Learnings

**For Web Environment (DEVLOG.md):**

Append to the development log using this format:

```markdown
## [YYYY-MM-DD HH:MM] - Session: [Brief Title]

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
- [Patterns to reuse]

### Ineffective Approaches
- [What didn't work and why]
- [Pitfalls to avoid]

### Open Questions
- [Unresolved issues]
- [Areas needing investigation]

### Next Steps
- [ ] [Specific next action]
- [ ] [Follow-up task]

---
```

**Implementation:**

```python
from datetime import datetime
import os

def update_devlog(content_dict):
    """Update DEVLOG.md with new session entry"""
    devlog_path = "DEVLOG.md"

    # Create DEVLOG.md if it doesn't exist
    if not os.path.exists(devlog_path):
        with open(devlog_path, 'w') as f:
            f.write("# Development Log\n\n")
            f.write("This log tracks progress, decisions, and learnings across development sessions.\n\n")
            f.write("---\n\n")

    # Prepare entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{timestamp}] - Session: {content_dict['title']}\n\n"

    if content_dict.get('context'):
        entry += f"### Context\n{content_dict['context']}\n\n"

    if content_dict.get('added') or content_dict.get('changed') or content_dict.get('fixed'):
        entry += "### Work Completed\n"
        if content_dict.get('added'):
            entry += "**Added:**\n" + "\n".join(f"- {item}" for item in content_dict['added']) + "\n\n"
        if content_dict.get('changed'):
            entry += "**Changed:**\n" + "\n".join(f"- {item}" for item in content_dict['changed']) + "\n\n"
        if content_dict.get('fixed'):
            entry += "**Fixed:**\n" + "\n".join(f"- {item}" for item in content_dict['fixed']) + "\n\n"

    if content_dict.get('decisions'):
        entry += "### Key Decisions\n"
        for decision in content_dict['decisions']:
            entry += f"- **Decision:** {decision['what']}\n"
            entry += f"  **Rationale:** {decision['why']}\n"
            if decision.get('alternatives'):
                entry += f"  **Alternatives considered:** {decision['alternatives']}\n"
        entry += "\n"

    if content_dict.get('effective'):
        entry += "### Effective Approaches\n"
        entry += "\n".join(f"- {item}" for item in content_dict['effective']) + "\n\n"

    if content_dict.get('ineffective'):
        entry += "### Ineffective Approaches\n"
        entry += "\n".join(f"- {item}" for item in content_dict['ineffective']) + "\n\n"

    if content_dict.get('questions'):
        entry += "### Open Questions\n"
        entry += "\n".join(f"- {q}" for q in content_dict['questions']) + "\n\n"

    if content_dict.get('next_steps'):
        entry += "### Next Steps\n"
        entry += "\n".join(f"- [ ] {step}" for step in content_dict['next_steps']) + "\n\n"

    entry += "---\n"

    # Append to DEVLOG.md
    with open(devlog_path, 'a') as f:
        f.write(entry)

    return devlog_path
```

**For CLI Environment (Project Knowledge):**

Create structured documents optimized for human curation:

```markdown
# [Topic/Task] - Session [N]

## Quick Summary
[2-3 sentences capturing essence of work]

## Methodology Notes
**Effective strategies:**
- [What approaches worked well]
- [Which techniques were most valuable]

**Ineffective approaches:**
- [What didn't work and why]

## Key Progress

### [Area 1]
**What was done:** [Description]
**Key insight:** [Main takeaway]
**Confidence:** [High/Medium/Low] - [Reasoning]

### [Area 2]
[Same structure]

## Decisions Made
- **Decision:** [What]
  **Rationale:** [Why]

## Open Items
- [What remains unfinished]
- [What requires further investigation]

## Recommended Next Steps
- [Logical next actions]
- [Areas for deeper work]
```

### 4. Prompt for Persistence

**Web Environment:**
After updating DEVLOG.md, inform the user:

> "I've updated DEVLOG.md with this session's progress. The log now includes [summary of what was added]. In your next session, I'll read the log to continue from where we left off."

**CLI Environment:**
After creating document, prompt user:

> "I've created a structured document. Review the content and consider adding valuable insights to your Project Knowledge. Include:
> - Effective strategies that worked
> - Key decisions and their rationale
> - Patterns or learnings that will help future work
>
> In your next session, I'll automatically retrieve relevant context from your Project Knowledge."

## Session N+1: Continuing Work

### 1. Retrieve Past Context

**Web Environment:**

```python
def read_devlog():
    """Read DEVLOG.md to get past context"""
    devlog_path = "DEVLOG.md"

    if os.path.exists(devlog_path):
        with open(devlog_path, 'r') as f:
            content = f.read()
        return content
    return None

# At session start
devlog_content = read_devlog()
if devlog_content:
    # Parse recent entries (last 3-5 sessions typically most relevant)
    # Extract key context, decisions, next steps
    pass
```

**CLI Environment:**

Check for relevant Project Knowledge (automatically injected by RAG):

```markdown
Based on project context about [topic], I can see we previously:
- [Key progress from past work]
- [Effective strategy from past work]

I'll build on these findings...
```

### 2. Acknowledge Past Work

Reference specific past progress:
- "Building on our previous session where we..."
- "Using the approach that worked last time..."
- "Avoiding the strategy that didn't yield results..."
- "Continuing from where we left off with..."

### 3. Address Open Items

Explicitly tackle unfinished work from previous sessions:

```markdown
From our previous session, we identified:
1. [Open item 1] - I'll address this now
2. [Open item 2] - Still requires investigation
3. [Next step from last time] - Executing this now
```

### 4. Synthesize Across Sessions

When you have multiple sessions of accumulated knowledge:
- Cross-reference findings across time periods
- Identify patterns or trends in the work
- Note contradictions and investigate them
- Build comprehensive understanding
- Track evolution of decisions

### 5. Continue Documentation

Maintain consistent documentation format so context continues to accumulate effectively.

## Development Log Management

### When to Update the Log

Update DEVLOG.md:
- **After significant progress**: Don't log every small step, but meaningful units of work
- **After key decisions**: Architecture choices, approach changes, important tradeoffs
- **After learning something**: Discoveries about the codebase, effective/ineffective approaches
- **Before ending session**: Capture state and next steps for continuity

### What to Include

**Do include:**
- Key decisions and their rationale
- Effective and ineffective approaches
- Important discoveries or insights
- Architectural choices
- Next steps and open questions
- Links to relevant code/files/docs

**Don't include:**
- Every minor code change (that's what git is for)
- Obvious or trivial information
- Raw dumps of data or logs
- Implementation details (document those in code comments)

### Log Maintenance

Keep the log useful:
- **Periodic summarization**: After 10-15 sessions, create a summary section
- **Archive old entries**: Move entries older than 30 days to DEVLOG_ARCHIVE.md
- **Keep it scannable**: Use consistent formatting and clear headings
- **Link to commits**: Reference git commits for code changes

### Example Maintenance

```python
def maintain_devlog():
    """Keep DEVLOG.md manageable"""
    # After many entries, create summary
    # Move old entries to archive
    # Keep recent context readily available

    # Read current log
    with open('DEVLOG.md', 'r') as f:
        content = f.read()

    # Extract entries older than 30 days
    # ... logic to parse and separate entries ...

    # Write recent to DEVLOG.md, old to DEVLOG_ARCHIVE.md
    pass
```

## Project Knowledge Integration (CLI Only)

### What Gets Retrieved Automatically

When Project Knowledge is enabled, the system automatically injects relevant context from:
- Past work documents user curated
- Previous findings marked as important
- Methodology notes and patterns
- Domain-specific knowledge accumulated over time

**You don't need to manually search project knowledge** - relevant content appears in your context automatically.

### How to Leverage Retrieved Context

When you see project knowledge in context:

```markdown
**Recognize it explicitly:**
"I see from project knowledge that we previously worked on..."

**Build on it:**
"Expanding on that approach with..."

**Validate it:**
"Cross-referencing with current state to verify..."

**Update it if needed:**
"Previous work suggested X, but now we've learned Y..."
```

### Optimizing for RAG Retrieval

Structure outputs to maximize retrieval effectiveness:

**Good for retrieval:**
- Clear, descriptive headings
- Key terms in topic sentences
- Self-contained insights (readable out of context)
- Explicit methodology notes
- Specific references

**Poor for retrieval:**
- Vague headings ("Notes", "Work")
- Context-dependent pronouns
- Scattered insights across paragraphs
- Implicit assumptions

## Output Templates

### Development Log Entry (Web Environment)

```markdown
## [2025-11-09 14:30] - Session: Implementing User Authentication

### Context
Working on adding JWT-based authentication to the API. Previous session established the database schema.

### Work Completed
**Added:**
- JWT token generation and validation middleware
- Login endpoint with email/password verification
- Protected route decorator

**Changed:**
- Updated User model to include password hashing
- Modified API error handling for auth failures

**Fixed:**
- Password comparison was case-sensitive (now uses constant-time comparison)

### Key Decisions
- **Decision:** Use JWT with 24-hour expiration and refresh tokens
  **Rationale:** Balance between security and user convenience; refresh tokens prevent frequent re-login
  **Alternatives considered:** Session-based auth (rejected due to statelessness requirement)

- **Decision:** Store passwords with bcrypt, cost factor 12
  **Rationale:** Industry standard, good security/performance tradeoff
  **Alternatives considered:** Argon2 (unnecessary complexity for our scale)

### Effective Approaches
- Using middleware pattern kept auth logic DRY
- Testing with actual requests helped catch edge cases early
- Reviewing OWASP auth guidelines prevented common vulnerabilities

### Ineffective Approaches
- Initially tried custom token format (unnecessarily complex, switched to JWT standard)
- Attempted to use httpOnly cookies for API (problematic for mobile clients)

### Open Questions
- Should we implement rate limiting on login endpoint?
- Do we need account lockout after failed attempts?
- How to handle password reset flow?

### Next Steps
- [ ] Implement password reset functionality
- [ ] Add rate limiting to prevent brute force
- [ ] Write integration tests for auth flows
- [ ] Document API authentication in README

---
```

### Progress Document (CLI Environment)

```markdown
---
title: Authentication Implementation - Session 2
date: 2025-11-09
task: Feature Development
---

# User Authentication Implementation - Session 2

## Quick Summary
Implemented JWT-based authentication with secure password hashing. System now supports user login, token validation, and protected routes. Open items: password reset, rate limiting, comprehensive testing.

## Methodology Notes
**Effective strategies:**
- Middleware pattern for auth logic provided clean separation
- Early testing with real requests caught edge cases
- OWASP guidelines review prevented security issues

**Ineffective approaches:**
- Custom token format added unnecessary complexity (switched to JWT)
- httpOnly cookies problematic for API clients (using Bearer tokens)

## Key Progress

### Authentication System
**What was done:** Implemented JWT token system with login endpoint and protected route middleware
**Key insight:** Refresh tokens essential for balancing security and UX - users stay logged in without compromising security
**Confidence:** High - follows industry standards and security best practices

**Code locations:**
- src/middleware/auth.ts - JWT validation middleware
- src/routes/auth.ts - Login endpoint
- src/models/User.ts - Password hashing

### Security Decisions
**Decision:** bcrypt with cost factor 12 for password hashing
**Rationale:** Industry standard, proven security, good performance tradeoff
**Alternatives:** Argon2 (rejected - unnecessary complexity for our scale)

**Decision:** 24-hour access tokens + refresh tokens
**Rationale:** Limits exposure window while maintaining good UX
**Alternatives:** Longer-lived tokens (rejected - security risk), sessions (rejected - statelessness requirement)

## Open Items
- Rate limiting on login endpoint to prevent brute force
- Account lockout mechanism after failed attempts
- Password reset flow implementation
- Comprehensive integration testing

## Recommended Next Steps
- Implement password reset (next critical feature)
- Add rate limiting (security requirement)
- Write integration tests for auth flows
- Document authentication in API docs
```

## Advanced Patterns

### Multi-Session Feature Development

For complex features spanning many sessions:

**Session 1:** Design and architecture planning
**Session 2-N:** Incremental implementation with learnings
**Session N+1:** Testing, refinement, documentation

Track feature status in the log:

```markdown
### Feature Status: [Feature Name]
**Progress:** 60% complete
**Completed:**
- [Component A]
- [Component B]

**In Progress:**
- [Component C] - 50% done, blocked by [issue]

**Not Started:**
- [Component D]
- [Component E]
```

### Debugging Across Sessions

When debugging complex issues:

```markdown
### Bug Investigation: [Bug Description]

**Hypothesis 1:** [Theory about cause]
**Status:** Refuted
**Evidence:** [What disproved it]
**Session:** [When tested]

**Hypothesis 2:** [Theory about cause]
**Status:** Confirmed
**Evidence:** [What proved it]
**Solution:** [How it was fixed]
**Session:** [When resolved]

**Hypothesis 3:** [Theory about cause]
**Status:** In Progress
**Next test:** [What to try next]
```

### Architecture Evolution

Track how architecture decisions evolve:

```markdown
### Architecture: [Component Name]

**Version 1** (Session 1-3):
- [Approach]
- **Why:** [Rationale]
- **Issue:** [What we learned]

**Version 2** (Session 4-6):
- [New approach]
- **Why:** [Improvement rationale]
- **Result:** [Outcome]

**Current** (Session 7+):
- [Final approach]
- **Lessons learned:** [Key insights]
```

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

## Common Patterns

### Pattern: Incremental Implementation

Session 1: Core functionality (get it working)
Session 2: Error handling and edge cases
Session 3: Testing and documentation
Session 4: Optimization and refinement

### Pattern: Spike and Implement

Session 1: Quick spike to validate approach
Session 2: Implement properly based on learnings
Session 3: Polish and production-readiness

### Pattern: Research and Apply

Session 1: Research approaches and best practices
Session 2: Apply learnings to implementation
Session 3: Iterate based on results

## Anti-Patterns to Avoid

**Don't:**
- Repeat work from previous sessions without acknowledging
- Ignore past decisions or learnings
- Create documentation in inconsistent formats
- Assume user remembers previous context
- Miss opportunities to synthesize across sessions
- Log every trivial detail
- Dump raw data into the log
- Forget to update state at session end

**Do:**
- Explicitly reference past work
- Build on previous decisions
- Maintain consistent documentation
- Re-state key context when continuing
- Actively synthesize new with old
- Log meaningful progress and decisions
- Curate signal over noise
- Always capture state before ending

## Working with Other Skills

**updating-knowledge:** Use for complex queries requiring 10+ tool calls in single session. Iterating focuses on cross-session learning.

**convening-experts:** Can be used within a session for multi-perspective analysis. Document the expert panel outputs.

**docx/xlsx/pdf skills:** Use these to create professional deliverables that can be added to project knowledge (CLI) or referenced in DEVLOG (web).

## Example Usage

### Web Environment Example

**User (Session 1):** "Help me debug this performance issue with the data processing pipeline."

**Claude:**
```
I'll track our debugging progress in DEVLOG.md so we can build on this work across sessions.

[Investigates issue, tries various approaches]

I've updated DEVLOG.md with our findings:
- Identified bottleneck in the serialization step (900ms avg)
- Tested 3 approaches: caching (ineffective), batching (moderate improvement), streaming (needs more work)
- Key decision: Switch to streaming approach based on profiling data
- Next steps: Implement streaming serialization, measure impact

In the next session, we can continue with the streaming implementation.
```

**User (Session 2):** "Let's continue the performance work."

**Claude:**
```
From DEVLOG.md, I can see we:
- Identified serialization as bottleneck (900ms)
- Decided to implement streaming approach
- Batching showed moderate improvement but streaming should be better

I'll now implement the streaming serialization we planned...

[Implements streaming approach]

Updated DEVLOG.md with results:
- Implemented streaming serialization
- Performance improved from 900ms to 120ms (87% reduction!)
- Trade-off: slight increase in memory usage (acceptable)
- Next: Add monitoring to track performance in production
```

### CLI Environment Example

**User (Session 1):** "Research microservice communication patterns for our architecture."

**Claude:**
```
I'll structure my research for curation into Project Knowledge.

[Conducts research]

I've created a research document covering:
- Synchronous vs asynchronous patterns
- Event-driven architecture analysis
- Service mesh considerations
- Recommended pattern: Event-driven with message queue for our use case

Review the document and add valuable insights to Project Knowledge. Next session I'll automatically retrieve this context.
```

**User (Session 2):** "Let's design the event schema for the services."

**Claude:**
```
Based on project knowledge, we decided on event-driven architecture with message queues. I'll now design event schemas following those patterns...

[Designs schemas]

I've created event schema definitions building on our architecture decision. Adding this to a document you can curate into Project Knowledge for future reference.
```

## Success Metrics

Iterative work is successful when:
- Each session builds on (not repeats) previous work
- Context accumulates efficiently over time
- Patterns and learnings emerge naturally
- Time-to-completion decreases across sessions
- Understanding compounds across conversations
- Less time spent re-explaining context
- More time spent making progress
