# Code CLI Environment

Claude Code CLI - writes to local filesystem in working directory.

## Persistence

Write directly to working directory:

```bash
cat > WorkLog.md << 'WORKLOG'
[content]
WORKLOG
```

Or update existing:
```bash
# Append new version entry
cat >> WorkLog.md << 'ENTRY'

## vN | YYYY-MM-DD HH:MM | Title
[content]
ENTRY

# Update frontmatter version
sed -i 's/^version: v[0-9]*/version: vN/' WorkLog.md
```

## Retrieval

Read from working directory:

```bash
if [ -f "WorkLog.md" ]; then
  cat WorkLog.md
elif [ -f "worklog.md" ]; then
  cat worklog.md
else
  # Find any WorkLog file
  find . -maxdepth 1 -name "*WorkLog*.md" -o -name "*WORKLOG*.md" | head -1
fi
```

Parse latest version from file content.
