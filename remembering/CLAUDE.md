# Muninn Memory System - Claude Code Context

**BOOT ON LAUNCH:** Run `boot()` at the start of every session:
```python
import sys
sys.path.insert(0, '/home/user/claude-skills')
from remembering import boot
print(boot())
```

## Meta: Using Muninn During Development

**When working on this skill, USE IT for tracking development progress!** Examples:

```python
from remembering import remember, journal, recall

# Record design decisions
remember("FTS5 Porter stemmer handles morphological variants automatically", "decision",
         tags=["fts5", "search", "performance"], conf=0.9)

# Track implementation progress
journal(topics=["muninn-v0.13.0"],
        my_intent="Removed embeddings, added Porter stemmer and query expansion")

# Remember discovered issues
remember("Config read_only flag should be checked before updates", "anomaly",
         tags=["bug", "config"], conf=0.7)

# Recall related context when debugging
issues = recall("configuration", tags=["bug"], n=10)
```

This creates a **feedback loop**: improve the skill while using it to track improvements.

## Quick Reference

**Database**: Turso SQLite via HTTP API
**URL**: `https://assistant-memory-oaustegard.aws-us-east-1.turso.io`
**Auth**: JWT token in `TURSO_TOKEN` environment variable

## Environment Variables

Set these in Claude Code's environment settings:

| Variable | Purpose |
|----------|---------|
| `TURSO_TOKEN` | JWT auth token for Turso HTTP API (required) |

## Architecture

Two-table design:

### `config` table
Boot-time context loaded at conversation start.

```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT,
    category TEXT,  -- 'profile', 'ops', or 'journal'
    updated_at TEXT
);
```

Categories:
- `profile`: Identity and behavior (who is Muninn, memory rules)
- `ops`: Operational guidance (API reference, skill delivery rules)
- `journal`: Session summaries for cross-conversation context

### `memories` table
Runtime memories stored during conversations.

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    type TEXT,           -- decision, world, anomaly, experience
    t TEXT,              -- ISO timestamp
    summary TEXT,        -- the actual memory content
    confidence REAL,     -- 0.0-1.0
    tags TEXT,           -- JSON array
    entities TEXT,       -- JSON array
    refs TEXT,           -- JSON array (for versioning)
    session_id TEXT,
    created_at TEXT,
    updated_at TEXT,
    deleted_at TEXT      -- soft delete
);
```

## Core API

```python
from remembering import remember, recall, forget, supersede, remember_bg
from remembering import recall_since, recall_between
from remembering import config_get, config_set, config_list, profile, ops, boot
from remembering import journal, journal_recent, journal_prune
from remembering import therapy_scope, therapy_session_count, decisions_recent
from remembering import group_by_type, group_by_tag
from remembering import handoff_pending, handoff_complete
from remembering import muninn_export, muninn_import
from remembering import strengthen, weaken
from remembering import cache_stats

# Store a memory (type required)
id = remember("User prefers dark mode", "decision", tags=["ui"], conf=0.9)
id = remember("Quick note", "world")

# Background write (non-blocking)
remember_bg("Project uses React", "world", tags=["tech"])

# Query memories - FTS5 with Porter stemmer for morphological variants
memories = recall("dark mode")  # FTS5 search with BM25 ranking
memories = recall(type="decision", conf=0.8)  # filtered by type and confidence
memories = recall(tags=["ui"])  # by tag (any match)
memories = recall(tags=["urgent", "task"], tag_mode="all")  # require all tags
# v0.13.0: Query expansion fallback automatically extracts tags from partial results

# Query memories - date-filtered
recent = recall_since("2025-12-01T00:00:00Z", n=50)  # after timestamp
range_mems = recall_between("2025-12-01T00:00:00Z", "2025-12-26T00:00:00Z")

# Soft delete
forget(memory_id)

# Version a memory (creates new, links to old)
new_id = supersede(old_id, "Updated preference", "decision")

# Salience adjustment for memory consolidation
strengthen("memory-id", factor=1.5)  # Boost salience (default 1.5x)
weaken("memory-id", factor=0.5)      # Reduce salience (default 0.5x)

# Config operations with constraints
config_set("identity", "I am Muninn...", "profile")
config_set("bio", "Short bio", "profile", char_limit=500)  # max length
config_set("rule", "Important rule", "ops", read_only=True)  # immutable
value = config_get("identity")
all_profile = profile()  # shorthand for config_list("profile")

# Journal (session summaries)
journal(topics=["coding"], my_intent="helped with refactor")
recent = journal_recent(5)

# Therapy session helpers
cutoff, unprocessed = therapy_scope()  # get memories since last therapy session
session_count = therapy_session_count()  # count therapy sessions

# Boot - load context and populate cache
print(boot())

# Analysis helpers
mems = recall(n=50)
by_type = group_by_type(mems)  # {"decision": [...], "world": [...]}
by_tag = group_by_tag(mems)    # {"ui": [...], "bug": [...]}

# Handoff workflow (cross-environment coordination)
# Note: handoff_pending() queries for memories tagged ["handoff", "pending"]
# However, not all pending work is tagged this way - always check broader queries too
pending = handoff_pending()  # get formal pending handoffs (both tags required)
all_handoffs = recall(tags=["handoff"], n=50)  # broader search for all handoff work
handoff_complete(handoff_id, "COMPLETED: ...", version="0.5.0")  # mark done

# Export/Import
state = muninn_export()  # all config + memories as JSON
stats = muninn_import(state, merge=True)  # merge into existing
stats = muninn_import(state, merge=False)  # replace all (destructive!)
```

## Memory Types

| Type | Use For | Default Confidence |
|------|---------|-------------------|
| `decision` | User preferences, choices | 0.8 |
| `world` | External facts, project state | None |
| `anomaly` | Bugs, errors, unexpected behavior | None |
| `experience` | General observations | None |

## HTTP API Format

All database ops use Turso's HTTP pipeline API:

```python
POST /v2/pipeline
Headers: 
  Authorization: Bearer {TURSO_TOKEN}
  Content-Type: application/json

Body:
{
  "requests": [{
    "type": "execute",
    "stmt": {
      "sql": "SELECT * FROM memories WHERE type = ?",
      "args": [{"type": "text", "value": "decision"}]
    }
  }]
}
```

## Testing

Run the skill locally:

```python
import sys
sys.path.insert(0, '.')  # if in skill directory

from remembering import remember, recall

# Test write
id = remember("Test memory", "experience")
print(f"Created: {id}")

# Test read
results = recall("Test")
print(f"Found: {len(results)} memories")
```

## File Structure

```
remembering/
├── __init__.py      # Main API implementation (33 exports)
├── bootstrap.py     # Schema creation/migration (4 exports)
├── SKILL.md         # Documentation for Claude.ai
├── CLAUDE.md        # This file (for Claude Code)
└── _MAP.md          # Code map (generated by mapping-codebases skill)
```

**Quick Navigation**: See `_MAP.md` for a complete list of all exported functions from `__init__.py` and `bootstrap.py`. The map is generated by the mapping-codebases skill and provides a structural overview without needing to read the full source.

## Development Notes

- Keep dependencies minimal (just `requests`)
- All timestamps are UTC ISO format
- Tags stored as JSON arrays
- Soft delete via `deleted_at` column
- `session_id` currently placeholder ("session")
- **Always test changes before creating a PR**

## Lessons for Claude Code Agents

### ALWAYS Explore Before Executing

When working with this skill, follow this sequence:

1. **Check directory structure first**:
   ```bash
   ls -la /path/to/remembering/
   ```

2. **Identify the module location**:
   - In repo root: `/home/user/claude-skills/remembering/`
   - Skills symlink: `.claude/skills/remembering -> ../../remembering`
   - The actual module is in repo root, NOT in a `scripts/` subdirectory

3. **Read the code before running**:
   ```python
   # Use Read tool to examine __init__.py first
   # Then run code with proper import path
   ```

4. **Import correctly**:
   ```python
   import sys
   sys.path.insert(0, '/home/user/claude-skills')  # Repo root
   from remembering import recall, remember
   ```

### Common Mistakes to Avoid

❌ **DON'T** assume there's a `scripts/` directory
❌ **DON'T** try to import before checking file structure
❌ **DON'T** ignore symlinks - they tell you where code lives
❌ **DON'T** guess import paths

✅ **DO** use `ls` and `Read` tool first
✅ **DO** follow symlinks to find actual code
✅ **DO** verify imports work in a simple test first
✅ **DO** use absolute paths for sys.path

### Debugging Import Issues

If imports fail:
```bash
# 1. Find the actual module
find /home/user/claude-skills -name "remembering" -type d

# 2. Check what's in it
ls -la /home/user/claude-skills/remembering/

# 3. Verify __init__.py exists
test -f /home/user/claude-skills/remembering/__init__.py && echo "Found" || echo "Missing"

# 4. Test import
python3 -c "import sys; sys.path.insert(0, '/home/user/claude-skills'); import remembering; print('Success')"
```

## Known Limitations

- Session ID currently hardcoded to "session" (not per-conversation tracking)
- Query expansion fallback threshold is fixed at 3 results (not configurable)
