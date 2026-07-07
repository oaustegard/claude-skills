# Chat Environment (Claude.ai)

Claude.ai web/chat/native app - no direct file system access.

## Persistence

Save WorkLog to outputs for download:

```bash
cp worklog.md /mnt/user-data/outputs/[Project]-WorkLog-vN.md
```

Provide download link:
```
[Download WorkLog vN](computer:///mnt/user-data/outputs/[Project]-WorkLog-vN.md)
```

## Retrieval

**From uploaded file:**
- User uploads WorkLog file
- Located in `/mnt/user-data/uploads/`
- Find: `ls -1 /mnt/user-data/uploads/*WorkLog*.md | sort -V | tail -1`

**From pasted content:**
- User pastes WorkLog content directly
- Detect YAML frontmatter with `version:` and `status:`
- Parse and continue

**From Project Knowledge:**
- User-curated files mounted at `/mnt/project/`
- RAG system may also inject relevant content into context
- Check: `ls /mnt/project/*WorkLog*.md 2>/dev/null`
- Read directly if present, or rely on RAG-injected context
