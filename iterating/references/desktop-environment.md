# Desktop Environment (Claude Desktop App)

This guide covers using the iterating skill in Claude Desktop (Windows/Mac), where state is persisted via DEVLOG.md in your working directory.

## User Acknowledgment

At session start, tell the user:
> "I'll track our progress in DEVLOG.md. Each session, I'll document key decisions, findings, and next steps."

## Environment Detection

Detect via `CLAUDE_CODE_REMOTE != 'true'` (has filesystem but not web). Can also check `sys.platform` for Windows/Mac.

## State Persistence: DEVLOG.md

Use DEVLOG.md in working directory (root or `.claude/` subdirectory). See SKILL.md for format template.

### File Location Options

**Root** (`DEVLOG.md`): Visible, easy to find
**.claude/** (`.claude/DEVLOG.md`): Hidden, organized

## Implementation

Same as web-environment.md with path parameter. Use `Path('DEVLOG.md')` or `Path('.claude/DEVLOG.md')`.

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

## Example

**Session 1:** "I'll track progress in DEVLOG.md. [Setup API] Updated: Express setup, TypeScript decision, next: endpoints."

**Session 2:** "From DEVLOG: setup complete. [Implements] Updated: GET/POST endpoints, validation, next: database."

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
