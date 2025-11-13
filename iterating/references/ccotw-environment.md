# CCotw Environment (Claude Code on the Web)

Claude Code on the Web - writes to GitHub repository via built-in functionality.

## Persistence

Use standard file operations (writes commit to GitHub automatically):

```bash
# Create new
cat > WorkLog.md << 'WORKLOG'
[content]
WORKLOG

# Or update existing
# Read current WorkLog
# Increment version in frontmatter
# Append new entry
# Write back to WorkLog.md
```

Changes automatically committed to current branch via CCotw infrastructure.

## Retrieval

Read from repository:

```bash
if [ -f "WorkLog.md" ]; then
  cat WorkLog.md
else
  # Find WorkLog variants
  ls -1 WorkLog*.md WORKLOG*.md worklog*.md 2>/dev/null | sort -V | tail -1
fi
```

Parse latest version from file content.
