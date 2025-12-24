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

# Delete
config_delete("old-key")
```

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

# Search with tag filter
tasks = recall("API", tags=["task"], n=15)
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

## Edge Cases

**Empty recall results:** Returns `[]`, not an error. Check list length before accessing.

**Search literal matching:** Current implementation uses SQL LIKE. Searches "API test" matches "API testing" but not "test API" (order matters).

**Tag partial matching:** `tags=["task"]` matches memories with tags `["task", "urgent"]` via JSON substring search.

**Confidence defaults:** `decision` type defaults to 0.8 if not specified. Others default to `NULL`.

**Invalid type:** Raises `ValueError` with list of valid types.

**Invalid category:** `config_set` raises `ValueError` if category not 'profile', 'ops', or 'journal'.

**Journal pruning:** Call `journal_prune()` periodically to prevent unbounded growth. Default keeps 40 entries.

## Implementation Notes

- Backend: Turso SQLite HTTP API
- Token: `/mnt/project/turso-token.txt`
- Two tables: `config` (KV) and `memories` (observations)
- HTTP API required (libsql SDK bypasses egress proxy)
- Thread-safe for background writes
