# Web Environment (Claude Code on the Web)

This guide covers using the iterating skill in Claude Code on the web environment, where state is persisted via DEVLOG.md in the repository.

## Environment Detection

In the web environment, the `CLAUDE_CODE_REMOTE` environment variable is set to `'true'`:

```python
import os

is_web_environment = os.environ.get('CLAUDE_CODE_REMOTE') == 'true'
```

## State Persistence: DEVLOG.md

In the web environment, maintain state across sessions using a development log in the repository.

### DEVLOG.md Format

```markdown
# Development Log

This log tracks progress, decisions, and learnings across development sessions.

---

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

## Implementation

### Updating the Development Log

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

### Reading Past Context

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

## Development Log Management

### When to Update

Update DEVLOG.md:
- **After significant progress**: Meaningful units of work, not every small step
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
- Links to relevant code/files (e.g., "See src/auth/middleware.ts:45")

**Don't include:**
- Every minor code change (that's what git commits are for)
- Obvious or trivial information
- Raw dumps of data or logs
- Implementation details (document those in code comments)

### Log Maintenance

Keep the log useful over time:

**Periodic summarization** (after 10-15 sessions):
- Create a summary section at the top
- Extract key decisions and patterns
- Highlight major milestones

**Archive old entries** (entries older than 30 days):
- Move to DEVLOG_ARCHIVE.md
- Keep recent context in DEVLOG.md for quick scanning

**Keep it scannable:**
- Use consistent formatting
- Clear, descriptive headings
- Bullet points over paragraphs

**Link to commits:**
- Reference git commits for code changes
- Example: "Implemented in commit abc123f"

### Example Maintenance Function

```python
from datetime import datetime, timedelta

def maintain_devlog():
    """Keep DEVLOG.md manageable by archiving old entries"""
    devlog_path = "DEVLOG.md"
    archive_path = "DEVLOG_ARCHIVE.md"

    if not os.path.exists(devlog_path):
        return

    with open(devlog_path, 'r') as f:
        lines = f.readlines()

    # Simple approach: Keep header and recent entries
    # More sophisticated: Parse dates and filter
    # This is left as an exercise - implement based on your needs

    # For now, if DEVLOG.md is over 1000 lines, suggest archiving to user
    if len(lines) > 1000:
        print("DEVLOG.md is getting large (>1000 lines). Consider archiving old entries.")
```

## Example Session

### Session 1: Initial Work

**User:** "Help me debug this performance issue with the data processing pipeline."

**Claude:**
```
I'll track our debugging progress in DEVLOG.md so we can build on this work across sessions.

[Investigates issue with profiling, testing different approaches]

I've updated DEVLOG.md with our findings:
- Identified bottleneck in the serialization step (900ms average)
- Tested 3 approaches:
  * Caching (ineffective - no repeated data)
  * Batching (moderate improvement to 650ms)
  * Streaming (needs implementation)
- Key decision: Switch to streaming approach based on profiling data
- Next steps: Implement streaming serialization, measure impact

In the next session, we can continue with the streaming implementation.
```

### Session 2: Continuing Work

**User:** "Let's continue the performance work."

**Claude:**
```
From DEVLOG.md, I can see we:
- Identified serialization as bottleneck (900ms avg)
- Tested batching (moderate improvement to 650ms)
- Decided to implement streaming approach for better performance

I'll now implement the streaming serialization we planned...

[Implements streaming approach, measures performance]

Updated DEVLOG.md with results:
- Implemented streaming serialization (see src/processor.py:145)
- Performance improved from 900ms to 120ms (87% reduction!)
- Trade-off: slight increase in memory usage (+15MB, acceptable)
- Next: Add monitoring to track performance in production
```

## Example DEVLOG Entry

```markdown
## [2025-11-09 14:30] - Session: Implementing User Authentication

### Context
Working on adding JWT-based authentication to the API. Previous session established the database schema and User model.

### Work Completed
**Added:**
- JWT token generation and validation middleware (src/middleware/auth.ts)
- Login endpoint with email/password verification (src/routes/auth.ts:45)
- Protected route decorator for securing endpoints

**Changed:**
- Updated User model to include password hashing with bcrypt
- Modified API error handling to return 401 for auth failures

**Fixed:**
- Password comparison was case-sensitive (now uses constant-time comparison)
- Token expiration not being checked properly

### Key Decisions
- **Decision:** Use JWT with 24-hour expiration and refresh tokens
  **Rationale:** Balance between security and user convenience; refresh tokens prevent frequent re-login while limiting access token exposure window
  **Alternatives considered:** Session-based auth (rejected - statelessness requirement), longer-lived tokens (rejected - security risk)

- **Decision:** Store passwords with bcrypt, cost factor 12
  **Rationale:** Industry standard, proven security, good performance tradeoff for our scale
  **Alternatives considered:** Argon2 (unnecessary complexity for our current needs)

### Effective Approaches
- Using middleware pattern kept auth logic DRY across routes
- Testing with actual API requests helped catch edge cases early
- Reviewing OWASP auth guidelines prevented common vulnerabilities

### Ineffective Approaches
- Initially tried custom token format (unnecessarily complex, switched to JWT standard)
- Attempted to use httpOnly cookies for API (problematic for mobile clients, switched to Bearer tokens)

### Open Questions
- Should we implement rate limiting on login endpoint?
- Do we need account lockout after failed attempts?
- How to handle password reset flow securely?

### Next Steps
- [ ] Implement password reset functionality
- [ ] Add rate limiting to prevent brute force attacks
- [ ] Write integration tests for auth flows
- [ ] Document API authentication in README

---
```

## User Communication

After updating DEVLOG.md, inform the user:

> "I've updated DEVLOG.md with this session's progress. The log now includes [brief summary of what was added]. In your next session, I'll read the log to continue from where we left off."

At the start of a new session, acknowledge past context:

> "From DEVLOG.md, I can see we previously [summary of past work]. I'll build on that work by [current session plan]..."
