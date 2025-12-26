# Muninn Memory System - Claude Code Context

This repo contains the `remembering` skill for Muninn, a persistent memory system for Claude.

## Meta: Using Muninn During Development

**When working on this skill, USE IT for tracking development progress!** Examples:

```python
from remembering import remember, journal, semantic_recall

# Record design decisions
remember("Vector search uses DiskANN index for sub-100ms latency at scale", "decision",
         tags=["vector-search", "performance"], conf=0.9)

# Track implementation progress
journal(topics=["muninn-v0.1.0"],
        my_intent="Adding semantic search and export/import capabilities")

# Remember discovered issues
remember("Config read_only flag should be checked before updates", "anomaly",
         tags=["bug", "config"], conf=0.7)

# Recall related context when debugging
issues = semantic_recall("configuration constraints and validation")
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
| `EMBEDDING_API_KEY` | API key for embedding generation (OpenAI, for vector search) |

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
from remembering import remember, recall, forget, supersede, remember_bg, semantic_recall
from remembering import config_get, config_set, config_list, profile, ops
from remembering import journal, journal_recent, journal_prune
from remembering import muninn_export, muninn_import

# Store a memory (type required, with optional embedding)
id = remember("User prefers dark mode", "decision", tags=["ui"], conf=0.9)
id = remember("Quick note", "world", embed=False)  # Skip embedding

# Background write (non-blocking)
remember_bg("Project uses React", "world", tags=["tech"])

# Query memories - keyword search
memories = recall("dark mode")  # text search
memories = recall(type="decision", conf=0.8)  # filtered
memories = recall(tags=["ui"])  # by tag (any match)
memories = recall(tags=["urgent", "task"], tag_mode="all")  # require all tags

# Query memories - semantic search (requires EMBEDDING_API_KEY)
similar = semantic_recall("user interface preferences", n=5)
similar = semantic_recall("performance issues", type="anomaly")

# Soft delete
forget(memory_id)

# Version a memory (creates new, links to old)
new_id = supersede(old_id, "Updated preference", "decision")

# Config operations with constraints
config_set("identity", "I am Muninn...", "profile")
config_set("bio", "Short bio", "profile", char_limit=500)  # max length
config_set("rule", "Important rule", "ops", read_only=True)  # immutable
value = config_get("identity")
all_profile = profile()  # shorthand for config_list("profile")

# Journal (session summaries)
journal(topics=["coding"], my_intent="helped with refactor")
recent = journal_recent(5)

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
├── __init__.py      # Main API implementation
├── bootstrap.py     # Schema creation/migration
├── SKILL.md         # Documentation for Claude.ai
└── CLAUDE.md        # This file (for Claude Code)
```

## Development Notes

- Keep dependencies minimal (just `requests`)
- All timestamps are UTC ISO format
- Tags stored as JSON arrays
- Soft delete via `deleted_at` column
- `session_id` currently placeholder ("session")

## Recent Enhancements (v0.1.0)

✅ **Vector/Semantic Search**: `semantic_recall()` with OpenAI embeddings and DiskANN index
✅ **Tag Match Modes**: `tag_mode="any"` or `tag_mode="all"` in `recall()`
✅ **Config Constraints**: `char_limit` and `read_only` flags in `config_set()`
✅ **Export/Import**: `muninn_export()` and `muninn_import()` for portability

## Known Limitations

- Semantic search requires OpenAI API key (paid service)
- Vector index creation requires newer Turso versions (falls back to brute-force)
- Embeddings not automatically regenerated on import
- Session ID currently hardcoded to "session" (not per-conversation tracking)
