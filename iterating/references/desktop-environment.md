# Desktop Environment (Claude Desktop App)

This guide covers using the iterating skill in Claude Desktop (Windows/Mac), where state is persisted via DEVLOG.md in your working directory.

## User Acknowledgment

At session start, tell the user:
> "I'll track our progress in DEVLOG.md. Each session, I'll document key decisions, findings, and next steps."

## Environment Detection

Claude Desktop runs in a code execution environment with filesystem access but no automatic Project Knowledge. Detect it by checking available features:

```python
import os
import sys

# Check if we're in Claude Code on the web
is_web = os.environ.get('CLAUDE_CODE_REMOTE') == 'true'

# Check if we have filesystem access (both web and desktop do)
has_filesystem = os.path.exists('.')

# Desktop environment: has filesystem but not web environment
# Also lacks automatic Project Knowledge like CLI
is_desktop = has_filesystem and not is_web

# Alternative: Check platform
is_windows = sys.platform == 'win32'
is_mac = sys.platform == 'darwin'
```

## State Persistence: DEVLOG.md

Use DEVLOG.md in your working directory (same as web environment). Since sessions don't automatically share state, maintain this file and read it at the start of each session.

### File Location Options

**Option 1: Root of working directory** (recommended)
```
DEVLOG.md
```

**Option 2: .claude directory** (organized)
```
.claude/DEVLOG.md
```

### Format

Compressed for AI parsing - same as web environment:

```markdown
# Development Log

---

## YYYY-MM-DD HH:MM | Title

**Prev:** [previous session context]
**Now:** [current goal]

**Work:**
+: [additions with file:line]
~: [changes with file:line]
!: [fixes with file:line]

**Decisions:**
- [what]: [why] (vs [alternatives])

**Works:** [effective approaches]
**Fails:** [ineffective, why]

**Open:** [questions]
**Next:** [actions]

---
```

## Implementation

### Setting Up the Progress File

```python
import os
from datetime import datetime
from pathlib import Path

def setup_devlog_file(location='working_dir'):
    """
    Set up the progress file in the specified location

    Args:
        location: 'working_dir', 'claude_dir', or custom path
    """
    if location == 'working_dir':
        devlog_path = Path('DEVLOG.md')
    elif location == 'claude_dir':
        claude_dir = Path('.claude')
        claude_dir.mkdir(exist_ok=True)
        devlog_path = claude_dir / 'DEVLOG.md'
    else:
        devlog_path = Path(location)

    # Create file if it doesn't exist
    if not devlog_path.exists():
        with open(devlog_path, 'w') as f:
            f.write("# Development Log\n\n")
            f.write("This log tracks progress, decisions, and learnings across development sessions.\n\n")
            f.write("---\n\n")

    return devlog_path

def update_devlog_file(devlog_path, content_dict):
    """Update progress file with new session entry"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {timestamp} | {content_dict['title']}\n\n"

    if content_dict.get('prev'):
        entry += f"**Prev:** {content_dict['prev']}\n"
    if content_dict.get('now'):
        entry += f"**Now:** {content_dict['now']}\n\n"

    if content_dict.get('added') or content_dict.get('changed') or content_dict.get('fixed'):
        entry += "**Work:**\n"
        if content_dict.get('added'):
            entry += "+: " + ", ".join(content_dict['added']) + "\n"
        if content_dict.get('changed'):
            entry += "~: " + ", ".join(content_dict['changed']) + "\n"
        if content_dict.get('fixed'):
            entry += "!: " + ", ".join(content_dict['fixed']) + "\n"
        entry += "\n"

    if content_dict.get('decisions'):
        entry += "**Decisions:**\n"
        for d in content_dict['decisions']:
            alt = f" (vs {d.get('alt', '')})" if d.get('alt') else ""
            entry += f"- {d['what']}: {d['why']}{alt}\n"
        entry += "\n"

    if content_dict.get('works'):
        entry += "**Works:** " + ", ".join(content_dict['works']) + "\n"
    if content_dict.get('fails'):
        entry += "**Fails:** " + ", ".join(content_dict['fails']) + "\n"
    if content_dict.get('works') or content_dict.get('fails'):
        entry += "\n"

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
def read_devlog_file(devlog_path=None):
    """Read progress file to get past context"""

    # Try common locations if no path specified
    if devlog_path is None:
        possible_paths = [
            Path('DEVLOG.md'),
            Path('.claude/DEVLOG.md'),
            Path('DEVLOG.md'),
            Path('.claude/DEVLOG.md')
        ]

        for path in possible_paths:
            if path.exists():
                devlog_path = path
                break

    if devlog_path and Path(devlog_path).exists():
        with open(devlog_path, 'r') as f:
            content = f.read()
        return content

    return None

# At session start
progress_content = read_devlog_file()
if progress_content:
    # Parse recent entries (last 3-5 sessions typically most relevant)
    # Extract key context, decisions, next steps
    print(f"Found progress file with {len(progress_content)} characters of history")
else:
    print("No progress file found - starting fresh")
```

## Desktop-Specific Considerations

### File Location Management

**Advantages of each location:**

**Working Directory Root** (`DEVLOG.md`):
- ✅ Easy to find and edit
- ✅ Visible in file explorers
- ✅ Easy to share with team
- ❌ Can clutter root directory

**Hidden .claude Directory** (`.claude/DEVLOG.md`):
- ✅ Keeps root clean
- ✅ Standard hidden config pattern
- ✅ Can store multiple files (.claude/DEVLOG.md, .claude/NOTES.md)
- ❌ Hidden by default (may forget it exists)

**Custom Location** (e.g., Documents folder):
- ✅ Persists across projects
- ✅ Backed up with user documents
- ✅ User has full control
- ❌ Needs absolute path management

### Backup Recommendations

Since Desktop files are local (not in git):

1. **Use cloud sync**: Place in OneDrive, Dropbox, or Google Drive folder
2. **Regular backups**: Copy to backup location periodically
3. **Version control**: Optionally git-track the progress file
4. **Export important entries**: Save critical decisions to separate docs

### Multi-Project Management

For working on multiple projects:

```python
def get_project_devlog_file(project_name):
    """Get or create progress file for specific project"""

    # Option 1: Use project-specific subdirectories
    project_dir = Path('.claude') / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    devlog_path = project_dir / 'DEVLOG.md'

    # Option 2: Use single file with project sections
    # devlog_path = Path('.claude') / f'{project_name}_DEVLOG.md'

    if not devlog_path.exists():
        with open(devlog_path, 'w') as f:
            f.write(f"# Development Log - {project_name}\n\n")
            f.write("---\n\n")

    return devlog_path

# Usage
auth_progress = get_project_devlog_file('authentication')
api_progress = get_project_devlog_file('api_redesign')
```

## Session Workflow

### Starting a Session

At the beginning of each Claude Desktop session:

```python
# 1. Check for progress file
devlog_path = Path('DEVLOG.md')  # or .claude/DEVLOG.md

if devlog_path.exists():
    # 2. Read previous context
    with open(devlog_path, 'r') as f:
        previous_work = f.read()

    # 3. Summarize recent sessions
    print("Previous session summary:")
    # Parse and display last 2-3 entries

else:
    # First session
    print("Starting new project - will create progress file")
```

### Ending a Session

Before ending the session:

```python
# 1. Summarize session work
session_summary = {
    'title': 'Implementing Authentication',
    'context': 'Building JWT-based auth system',
    'added': ['JWT middleware', 'Login endpoint'],
    'decisions': [
        {'what': 'Use bcrypt for passwords', 'why': 'Industry standard security'}
    ],
    'next_steps': ['Add password reset', 'Write tests']
}

# 2. Update progress file
devlog_path = Path('DEVLOG.md')
update_devlog_file(devlog_path, session_summary)

# 3. Inform user
print(f"Updated {devlog_path} with session progress")
print("Next session: Continue with password reset implementation")
```

## User Communication

**At session start:**
> "I'll track our progress in DEVLOG.md in your working directory. This file will persist across sessions so we can build on previous work. Each session, I'll read the file to understand where we left off."

**After first update:**
> "I've created DEVLOG.md with this session's work. The file is located at [path]. In your next session, I'll read this file to continue from where we left off."

**At start of new session:**
> "From DEVLOG.md, I can see we previously [summary of past work]. Let me continue from where we left off..."

## Example Session

### Session 1: Initial Setup

**User:** "Help me build a REST API. I'm using Claude Desktop."

**Claude:**
```
I'll track our progress in DEVLOG.md in your working directory. This will help us maintain context across sessions.

[Works on initial API setup]

I've created DEVLOG.md and documented our work:
- Project structure setup (src/, tests/, config/)
- Express.js server configuration
- Basic routing skeleton
- Decision: Use TypeScript for type safety

Next session: Implement first endpoints and error handling

The progress file is in: C:\Users\You\Projects\my-api\DEVLOG.md
```

### Session 2: Continuing Work

**User:** "Let's continue building the API."

**Claude:**
```
Reading DEVLOG.md...

From our previous session, I can see we:
- Set up project structure with Express and TypeScript
- Created basic routing skeleton
- Decided on TypeScript for type safety
- Next step: Implement first endpoints

I'll continue by implementing the endpoints now...

[Implements endpoints]

Updated DEVLOG.md with this session:
- Implemented GET /users and POST /users endpoints
- Added request validation with Zod
- Set up error handling middleware
- Next: Add database integration

Progress file updated at: C:\Users\You\Projects\my-api\DEVLOG.md
```

## Integration with MCP Memory Servers (Optional)

For users who want more sophisticated memory, consider recommending MCP memory servers:

```
If you want more persistent memory across all your Claude Desktop sessions (not just this project), consider setting up the Claude Memory MCP server. It provides:
- Cross-project memory
- SQLite-backed storage
- Semantic search of past conversations
- User preferences and context

See: https://github.com/modelcontextprotocol/servers
```

## Windows-Specific Tips

### File Paths
```python
# Use pathlib for cross-platform compatibility
from pathlib import Path

devlog_path = Path('DEVLOG.md')  # Works on Windows and Mac

# Or use os.path
import os
devlog_path = os.path.join(os.getcwd(), 'DEVLOG.md')
```

### Windows Path Handling
```python
# Handle Windows backslashes
import os
from pathlib import Path

# Pathlib handles this automatically
devlog_path = Path('C:/Users/YourName/Projects/DEVLOG.md')

# Or normalize paths
devlog_path = os.path.normpath('C:\\Users\\YourName\\Projects\\DEVLOG.md')
```

### File Permissions
```python
# Check if file is writable
devlog_path = Path('DEVLOG.md')

if devlog_path.exists():
    if os.access(devlog_path, os.W_OK):
        print("Can write to progress file")
    else:
        print("Progress file is read-only - check permissions")
```

## Troubleshooting

### Can't Find Progress File

```python
import os
from pathlib import Path

# List all potential progress files
for root, dirs, files in os.walk('.'):
    for file in files:
        if 'PROGRESS' in file or 'DEVLOG' in file:
            print(f"Found: {os.path.join(root, file)}")
```

### File Encoding Issues

```python
# Always specify encoding on Windows
with open('DEVLOG.md', 'a', encoding='utf-8') as f:
    f.write(entry)

# Reading with encoding
with open('DEVLOG.md', 'r', encoding='utf-8') as f:
    content = f.read()
```

### Sharing Across Team

If multiple people use Claude Desktop on the same project:

1. **Commit to git**: Track DEVLOG.md in version control
2. **Use shared drive**: Place in OneDrive/Dropbox
3. **Merge strategy**: Use timestamps to merge multiple people's entries
4. **Separate files**: Each person has their own PROGRESS_[name].md

## Best Practices

1. **Consistent location**: Decide on one location and stick to it
2. **Regular reading**: Start each session by reading the progress file
3. **Backup important entries**: Save critical decisions elsewhere too
4. **Keep it focused**: Log meaningful progress, not every detail
5. **Archive periodically**: Move old entries to PROGRESS_ARCHIVE.md
6. **Use descriptive session titles**: Makes scanning easier
7. **Reference file locations**: Include file paths when documenting code changes
