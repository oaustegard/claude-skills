# Web Environment (Claude Code on the Web)

This guide covers using the iterating skill in Claude Code on the web environment, where state is persisted via DEVLOG.md in the repository.

## User Acknowledgment

At session start, tell the user:
> "I'll track our progress in DEVLOG.md in the repository. Each session, I'll document key decisions, findings, and next steps."

## Environment Detection

In the web environment, the `CLAUDE_CODE_REMOTE` environment variable is set to `'true'`:

```python
import os

is_web_environment = os.environ.get('CLAUDE_CODE_REMOTE') == 'true'
```

## State Persistence: DEVLOG.md

In the web environment, maintain state across sessions using a development log in the repository.

### DEVLOG.md Format

Optimized for AI parsing - maximize information density:

```markdown
# Development Log

---

## YYYY-MM-DD HH:MM | Title

**Prev:** [Context from previous session]
**Now:** [Current session goal]

**Work:**
+: [additions with file:line]
~: [changes with file:line]
!: [fixes with file:line]

**Decisions:**
- [what]: [why] (vs [alternatives])

**Works:** [effective approaches]
**Fails:** [ineffective approaches, why]

**Open:** [unresolved questions]
**Next:** [action items]

---
```

## Implementation

### Updating the Development Log

```python
from datetime import datetime
import os

def update_devlog(content_dict):
    """Update DEVLOG.md with compressed entry"""
    devlog_path = "DEVLOG.md"

    # Create if doesn't exist
    if not os.path.exists(devlog_path):
        with open(devlog_path, 'w') as f:
            f.write("# Development Log\n\n---\n\n")

    # Prepare compressed entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {timestamp} | {content_dict['title']}\n\n"

    if content_dict.get('prev'):
        entry += f"**Prev:** {content_dict['prev']}\n"
    if content_dict.get('now'):
        entry += f"**Now:** {content_dict['now']}\n\n"

    # Work section with symbols
    if content_dict.get('added') or content_dict.get('changed') or content_dict.get('fixed'):
        entry += "**Work:**\n"
        if content_dict.get('added'):
            entry += "+: " + ", ".join(content_dict['added']) + "\n"
        if content_dict.get('changed'):
            entry += "~: " + ", ".join(content_dict['changed']) + "\n"
        if content_dict.get('fixed'):
            entry += "!: " + ", ".join(content_dict['fixed']) + "\n"
        entry += "\n"

    # Decisions - compact format
    if content_dict.get('decisions'):
        entry += "**Decisions:**\n"
        for d in content_dict['decisions']:
            alt = f" (vs {d.get('alt', '')})" if d.get('alt') else ""
            entry += f"- {d['what']}: {d['why']}{alt}\n"
        entry += "\n"

    # Works/Fails - single line each
    if content_dict.get('works'):
        entry += "**Works:** " + ", ".join(content_dict['works']) + "\n"
    if content_dict.get('fails'):
        entry += "**Fails:** " + ", ".join(content_dict['fails']) + "\n"
    if content_dict.get('works') or content_dict.get('fails'):
        entry += "\n"

    # Open/Next - compact
    if content_dict.get('open'):
        entry += "**Open:** " + ", ".join(content_dict['open']) + "\n"
    if content_dict.get('next'):
        entry += "**Next:** " + ", ".join(content_dict['next']) + "\n"
    if content_dict.get('open') or content_dict.get('next'):
        entry += "\n"

    entry += "---\n"

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

### Content Guidelines

Include: Key decisions (with alternatives), effective/ineffective approaches, discoveries, file:line refs, open questions, next steps

Skip: Minor changes (use git), obvious info, raw data dumps, implementation details (use code comments)

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

### Session Examples

**Session 1:**
```
I'll track progress in DEVLOG.md.

[Profiles, tests approaches]

Updated DEVLOG with: serialization bottleneck (900ms), tested caching (no effect), batching (650ms), decided on streaming approach. Next: implement streaming.
```

**Session 2:**
```
From DEVLOG: serialization bottleneck, tested batching (650ms), streaming planned.

[Implements streaming]

Updated: streaming impl (src/processor.py:145), 900ms→120ms (87% faster), +15MB memory (ok), next: monitoring.
```

## Example DEVLOG Entry

```markdown
## 2025-11-09 14:30 | JWT Authentication

**Prev:** User model + DB schema complete
**Now:** JWT auth flow implementation

**Work:**
+: JWT middleware (src/middleware/auth.ts), Login endpoint (src/routes/auth.ts:45), Protected route decorator
~: User model - add bcrypt password hash, API errors - return 401 for auth
!: Password comparison case-sensitive → constant-time, Token expiration not validated

**Decisions:**
- JWT 24h + refresh tokens: security/UX balance (vs session-based: breaks stateless req; vs long-lived: security risk)
- bcrypt cost=12: industry standard, proven (vs Argon2: unnecessary complexity)

**Works:** Middleware pattern (DRY), testing with real requests (caught edge cases), OWASP review (prevented vulns)
**Fails:** Custom token format (complex, switched to JWT), httpOnly cookies (mobile issue, switched to Bearer)

**Open:** Rate limiting on login? Account lockout strategy? Password reset flow?
**Next:** Password reset, rate limiting, integration tests, API docs

---
```

## User Communication

After updating DEVLOG.md, inform the user:

> "I've updated DEVLOG.md with this session's progress. The log now includes [brief summary of what was added]. In your next session, I'll read the log to continue from where we left off."

At the start of a new session, acknowledge past context:

> "From DEVLOG.md, I can see we previously [summary of past work]. I'll build on that work by [current session plan]..."
