---
name: remembering
description: Advanced memory operations reference. Basic patterns (profile loading, simple recall/remember) are in project instructions. Consult this skill for background writes, memory versioning, complex queries, and edge cases.
---

# Remembering - Advanced Operations

**Basic patterns are in project instructions.** This skill covers advanced features and edge cases.

## Two-Table Architecture

| Table | Purpose | Growth |
|-------|---------|--------|
| `config` | Stable operational state (profile + ops + journal) | Small, mostly static |
| `memories` | Timestamped observations | Unbounded |

Config loads fast at startup. Memories are queried as needed.

## Journal System

Temporal awareness via rolling journal entries in config. Inspired by Strix's journal.jsonl pattern.

```python
from remembering import journal, journal_recent, journal_prune

# Record what happened this interaction
journal(
    topics=["project-x", "debugging"],
    user_stated="Will review PR tomorrow",
    my_intent="Investigating memory leak"
)

# Boot: load recent entries for context
for entry in journal_recent(10):
    print(f"[{entry['t'][:10]}] {entry.get('topics', [])}: {entry.get('my_intent', '')}")

# Maintenance: keep last 40 entries
pruned = journal_prune(keep=40)
```

**Entry structure:**
- `t`: ISO timestamp
- `topics`: array of tags (enables filtering at scale)
- `user_stated`: commitments/plans user verbalized
- `my_intent`: current goal/task

**Key insight from Strix:** "If you didn't write it down, you won't remember it next message."

## Config Table

Key-value store for profile (behavioral), ops (operational), and journal (temporal) settings.

```python
from remembering import config_get, config_set, config_delete, config_list, profile, ops

# Read
config_get("identity")                    # Single key
profile()                                  # All profile entries
ops()                                      # All ops entries
config_list()                              # Everything

# Write
config_set("new-key", "value", "profile")  # Category: 'profile', 'ops', or 'journal'
config_set("skill-foo", "usage notes", "ops")

# Write with constraints (new!)
config_set("bio", "Short bio here", "profile", char_limit=500)  # Enforce max length
config_set("core-rule", "Never modify this", "ops", read_only=True)  # Mark immutable

# Delete
config_delete("old-key")
```

**Config constraints:**
- `char_limit`: Enforces maximum character count on writes (raises `ValueError` if exceeded)
- `read_only`: Prevents modifications (raises `ValueError` on attempted updates)

## Memory Type System

**Type is required** on all write operations. Valid types:

| Type | Use For |
|------|---------|
| `decision` | Explicit choices: prefers X, always/never do Y |
| `world` | External facts: tasks, deadlines, project state |
| `anomaly` | Errors, bugs, unexpected behavior |
| `experience` | General observations, catch-all |

Note: `profile` is no longer a memory type—use `config_set(key, value, "profile")` instead.

```python
from remembering import TYPES  # {'decision', 'world', 'anomaly', 'experience'}
```

## Background Writes (Agentic Pattern)

Fire-and-forget storage for non-blocking workflow:

```python
from remembering import remember_bg

# Returns immediately, writes in background thread
remember_bg("User's project uses Python 3.12 with FastAPI", "world")
remember_bg("Discovered: batch insert reduces latency 70%", "experience", tags=["optimization"])
```

Use `remember_bg()` when:
- Storing derived insights during active work
- Memory write shouldn't block response
- Agentic pattern where latency matters

Use blocking `remember()` when:
- User explicitly requests storage
- Need confirmation of write success
- Memory ID needed for references

## Memory Versioning (Patch/Snapshot)

Supersede without losing history:

```python
from remembering import supersede

# User's preference evolved
original_id = "abc-123"
supersede(original_id, "User now prefers Python 3.12", "decision", conf=0.9)
```

Creates new memory with `refs=[original_id]`. Original preserved but not returned in default queries. Trace evolution via `refs` chain.

## Complex Queries

Multiple filters, custom confidence thresholds:

```python
from remembering import recall

# High-confidence decisions only
decisions = recall(type="decision", conf=0.85, n=20)

# Recent anomalies for debugging context
bugs = recall(type="anomaly", n=5)

# Search with tag filter (any match)
tasks = recall("API", tags=["task"], n=15)

# Require ALL tags (tag_mode="all")
urgent_tasks = recall(tags=["task", "urgent"], tag_mode="all", n=10)
```

## Semantic Search (Vector Similarity)

Find memories by meaning, not just keywords. Requires `EMBEDDING_API_KEY` environment variable (OpenAI API key).

```python
from remembering import semantic_recall

# Find memories semantically similar to a concept
similar = semantic_recall("performance optimization strategies")

# With filters
similar_decisions = semantic_recall("user preferences", type="decision", n=3)
```

**How it works:**
- Stores 1536-dim embeddings (OpenAI `text-embedding-3-small`) with each memory
- Uses Turso's DiskANN vector index for efficient cosine similarity search
- Returns results with `similarity` field (0.0-1.0)
- Gracefully degrades if embeddings not available

**Enable semantic search:**
```bash
export EMBEDDING_API_KEY="sk-..."  # OpenAI API key
```

**Disable embeddings for a specific write:**
```python
remember("No embedding needed", "world", embed=False)
```

## Soft Delete

Remove without destroying data:

```python
from remembering import forget

forget("memory-uuid")  # Sets deleted_at, excluded from queries
```

Memories remain in database for audit/recovery. Hard deletes require direct SQL.

## Memory Quality Guidelines

Write complete, searchable summaries that standalone without conversation context:

✓ "User prefers direct answers with code examples over lengthy conceptual explanations"

✗ "User wants code" (lacks context, unsearchable)

✗ "User asked question" + "gave code" + "seemed happy" (fragmented, no synthesis)

## Export/Import for Portability

Backup or migrate Muninn state across environments:

```python
from remembering import muninn_export, muninn_import
import json

# Export all state to JSON
state = muninn_export()
# Returns: {"version": "1.0", "exported_at": "...", "config": [...], "memories": [...]}

# Save to file
with open("muninn-backup.json", "w") as f:
    json.dump(state, f, indent=2)

# Import (merge with existing data)
with open("muninn-backup.json") as f:
    data = json.load(f)
stats = muninn_import(data, merge=True)
print(f"Imported {stats['config_count']} config, {stats['memory_count']} memories")

# Import (replace all - destructive!)
stats = muninn_import(data, merge=False)
```

**Notes:**
- `merge=False` deletes all existing data before import (use with caution!)
- Memory IDs are regenerated on import to avoid conflicts
- Embeddings are preserved from export (not regenerated)
- Returns stats dict with counts and any errors

## Edge Cases

**Empty recall results:** Returns `[]`, not an error. Check list length before accessing.

**Search literal matching:** Current implementation uses SQL LIKE. Searches "API test" matches "API testing" but not "test API" (order matters).

**Tag partial matching:** `tags=["task"]` matches memories with tags `["task", "urgent"]` via JSON substring search.

**Confidence defaults:** `decision` type defaults to 0.8 if not specified. Others default to `NULL`.

**Invalid type:** Raises `ValueError` with list of valid types.

**Invalid category:** `config_set` raises `ValueError` if category not 'profile', 'ops', or 'journal'.

**Journal pruning:** Call `journal_prune()` periodically to prevent unbounded growth. Default keeps 40 entries.

**Semantic search without API key:** `semantic_recall()` raises `RuntimeError` if `EMBEDDING_API_KEY` not set. Regular `recall()` works without it.

**Tag mode:** `tag_mode="all"` requires all specified tags to be present. `tag_mode="any"` (default) matches if any tag present.

## Implementation Notes

- Backend: Turso SQLite HTTP API
- Token: `TURSO_TOKEN` environment variable or `/mnt/project/turso-token.txt`
- Embedding API: `EMBEDDING_API_KEY` environment variable (OpenAI)
- Two tables: `config` (KV) and `memories` (observations)
- Vector search: 1536-dim embeddings with DiskANN index
- HTTP API required (libsql SDK bypasses egress proxy)
- Thread-safe for background writes
