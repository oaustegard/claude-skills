# Desktop Environment (Claude Desktop)

Claude Desktop app - may have file system access via tools.

## Persistence

**If you have write access to project directory:**
Write WorkLog.md to the project directory.

**Otherwise:**
Save to outputs for download:
```bash
cp worklog.md /mnt/user-data/outputs/[Project]-WorkLog-vN.md
```

## Retrieval

**If you have read access to project directory:**
Read WorkLog.md from the project directory.

**From Project Knowledge:**
- User-curated files mounted at `/mnt/project/`
- Check: `ls /mnt/project/*WorkLog*.md 2>/dev/null`
- Read directly if present

**From uploaded file:**
- User uploads WorkLog file
- Located in `/mnt/user-data/uploads/`
- Find: `ls -1 /mnt/user-data/uploads/*WorkLog*.md | sort -V | tail -1`

**Otherwise, from pasted content:**
- User pastes WorkLog content directly
- Detect YAML frontmatter with `version:` and `status:`
- Parse and continue
