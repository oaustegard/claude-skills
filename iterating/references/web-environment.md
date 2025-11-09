# Web Environment (Claude Code on the Web)

This guide covers using the iterating skill in Claude Code on the web environment, where state is persisted via DEVLOG.md in the repository.

## User Acknowledgment

At session start, tell the user:
> "I'll track our progress in DEVLOG.md in the repository. Each session, I'll document key decisions, findings, and next steps."

## Environment Detection

Detect via `CLAUDE_CODE_REMOTE='true'` environment variable.

## State Persistence: DEVLOG.md

Maintain state across sessions using DEVLOG.md in the repository. See SKILL.md for format template.

## Implementation

### Updating DEVLOG

```python
from datetime import datetime

def update_devlog(data):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {ts} | {data['title']}\n\n"

    if data.get('prev'): entry += f"**Prev:** {data['prev']}\n"
    if data.get('now'): entry += f"**Now:** {data['now']}\n\n"

    if work := [data.get(k) for k in ['added','changed','fixed'] if data.get(k)]:
        entry += "**Work:**\n"
        if data.get('added'): entry += f"+: {', '.join(data['added'])}\n"
        if data.get('changed'): entry += f"~: {', '.join(data['changed'])}\n"
        if data.get('fixed'): entry += f"!: {', '.join(data['fixed'])}\n"
        entry += "\n"

    if data.get('decisions'):
        entry += "**Decisions:**\n" + "\n".join(
            f"- {d['what']}: {d['why']}" + (f" (vs {d['alt']})" if d.get('alt') else "")
            for d in data['decisions']) + "\n\n"

    if data.get('works'): entry += f"**Works:** {', '.join(data['works'])}\n"
    if data.get('fails'): entry += f"**Fails:** {', '.join(data['fails'])}\n"
    if data.get('works') or data.get('fails'): entry += "\n"

    if data.get('open'): entry += f"**Open:** {', '.join(data['open'])}\n"
    if data.get('next'): entry += f"**Next:** {', '.join(data['next'])}\n\n"

    entry += "---\n"

    with open("DEVLOG.md", 'a') as f:
        f.write(entry)
```

### Reading Past Context

```python
from pathlib import Path

# At session start, read DEVLOG.md
devlog = Path("DEVLOG.md")
if devlog.exists():
    context = devlog.read_text()
    # Focus on last 3-5 entries for recent context
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

## Example

**Session 1:** "I'll track progress in DEVLOG.md. [Works] Updated: tested batching (650ms), streaming planned."

**Session 2:** "From DEVLOG: batching tested. [Implements] Updated: streaming impl (src/processor.py:145), 900ms→120ms."

**User Communication:**
- After update: "Updated DEVLOG.md with [summary]"
- New session: "From DEVLOG: [past work]. Continuing with [plan]"
