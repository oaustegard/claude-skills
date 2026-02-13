---
name: remembering
description: Advanced memory operations reference. Basic patterns (profile loading, simple recall/remember) are in project instructions. Consult this skill for background writes, memory versioning, complex queries, edge cases, session scoping, retention management, type-safe results, proactive memory hints, GitHub access detection, and ops priority ordering.
metadata:
  version: 4.3.0
---

# Remembering - Advanced Operations

**Basic patterns are in project instructions.** This skill covers advanced features and edge cases.

For development context, see [references/CLAUDE.md](references/CLAUDE.md).

## Two-Table Architecture

| Table | Purpose | Growth |
|-------|---------|--------|
| `config` | Stable operational state (profile + ops + journal) | Small, mostly static |
| `memories` | Timestamped observations | Unbounded |

Config loads fast at startup. Memories are queried as needed.

## Boot Sequence

Load context at conversation start to maintain continuity across sessions.

```python
from remembering import boot
print(boot())
```

**Performance:** ~150ms (single HTTP request), populates local cache for fast subsequent `recall()`.

Boot includes a `# CAPABILITIES` section reporting GitHub access and installed utilities. See [references/advanced-operations.md](references/advanced-operations.md) for details.

## Memory Type System

**Type is required** on all write operations. Valid types:

| Type | Use For |
|------|---------|
| `decision` | Explicit choices: prefers X, always/never do Y |
| `world` | External facts: tasks, deadlines, project state |
| `anomaly` | Errors, bugs, unexpected behavior |
| `experience` | General observations, catch-all |

```python
from remembering import TYPES  # {'decision', 'world', 'anomaly', 'experience'}
```

## Core Operations

### Remember

```python
from remembering import remember, remember_bg, flush

# Blocking write (default)
id = remember("User prefers dark mode", "decision", tags=["ui"], conf=0.9)

# Background write (non-blocking)
remember("Quick note", "world", sync=False)

# Ensure all background writes complete before conversation ends
flush()
```

**When to use sync=False:** Storing derived insights during active work, when latency matters.
**When to use sync=True (default):** User explicitly requests storage, critical memories, handoffs.

### Recall

```python
from remembering import recall

# FTS5 search with BM25 ranking + Porter stemmer
memories = recall("dark mode")

# Filtered queries
decisions = recall(type="decision", conf=0.85, n=20)
tasks = recall("API", tags=["task"], n=15)
urgent = recall(tags=["task", "urgent"], tag_mode="all", n=10)

# Comprehensive retrieval (v4.1.0)
all_memories = recall(fetch_all=True, n=1000)  # Get all memories without search filtering

# Time-windowed queries (v4.3.0) - since/until with inclusive bounds
recent = recall("API", since="2025-02-01")
jan_memories = recall(since="2025-01-01", until="2025-01-31T23:59:59Z")

# Multi-tag convenience (v4.3.0)
both = recall(tags_all=["correction", "bsky"])    # AND: must have all tags
either = recall(tags_any=["therapy", "self-improvement"])  # OR: any tag matches

# Wildcard patterns are NOT supported - use fetch_all instead
# recall("*", n=1000)  # ❌ Raises ValueError
# recall(fetch_all=True, n=1000)  # ✅ Correct approach
```

Results return as `MemoryResult` objects with attribute and dict access. Common aliases (`m.content` -> `m.summary`, `m.conf` -> `m.confidence`) resolve transparently.

### Decision Alternatives (v4.2.0)

Track rejected alternatives on decision memories to prevent revisiting settled conclusions:

```python
from remembering import remember, get_alternatives

# Store decision with alternatives considered
id = remember(
    "Chose PostgreSQL for the database",
    "decision",
    tags=["architecture", "database"],
    alternatives=[
        {"option": "MongoDB", "rejected": "Schema-less adds complexity for our relational data"},
        {"option": "SQLite", "rejected": "Doesn't support concurrent writes at our scale"},
    ]
)

# Later: retrieve what was considered
alts = get_alternatives(id)
for alt in alts:
    print(f"Rejected {alt['option']}: {alt.get('rejected', 'no reason')}")
```

Alternatives are stored in the `refs` field as a typed object alongside memory ID references. The `alternatives` computed field is automatically extracted on `MemoryResult` objects for decision memories.

### Reference Chain Traversal (v4.3.0)

Follow reference chains to build context graphs around a memory:

```python
from remembering import get_chain

# Follow refs up to 3 levels deep (default)
chain = get_chain("memory-uuid", depth=3)
for m in chain:
    print(f"[depth={m['_chain_depth']}] {m['summary'][:80]}")

# Useful for understanding supersede chains, consolidated memory origins, etc.
```

Handles cycles via visited set. Max depth capped at 10.

### Forget and Supersede

```python
from remembering import forget, supersede

# Soft delete (sets deleted_at, excluded from queries)
forget("memory-uuid")

# Version without losing history
supersede(original_id, "User now prefers Python 3.12", "decision", conf=0.9)
```

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
config_set("bio", "Short bio here", "profile", char_limit=500)  # Enforce max length
config_set("core-rule", "Never modify this", "ops", read_only=True)  # Mark immutable

# Delete
config_delete("old-key")
```

For progressive disclosure, priority-based ordering, and dynamic topic categories, see [references/advanced-operations.md](references/advanced-operations.md).

## Journal System

Temporal awareness via rolling journal entries in config.

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

## Background Writes

Use `remember(..., sync=False)` for background writes. **Always call `flush()` before conversation ends** to ensure persistence.

```python
from remembering import remember, flush

remember("Derived insight", "experience", sync=False)
remember("Another note", "world", sync=False)

# Before conversation ends:
flush()  # Blocks until all background writes finish
```

`remember_bg()` still works as deprecated alias for `remember(..., sync=False)`.

## Memory Quality Guidelines

Write complete, searchable summaries that standalone without conversation context:

- **Good**: "User prefers direct answers with code examples over lengthy conceptual explanations"
- **Bad**: "User wants code" (lacks context, unsearchable)
- **Bad**: "User asked question" + "gave code" + "seemed happy" (fragmented)

## Edge Cases

- **Empty recall results:** Returns `MemoryResultList([])`, not an error
- **Tag partial matching:** `tags=["task"]` matches memories with tags `["task", "urgent"]`
- **Confidence defaults:** `decision` type defaults to 0.8 if not specified
- **Invalid type:** Raises `ValueError` with list of valid types
- **Tag mode:** `tag_mode="all"` requires all tags present; `tag_mode="any"` (default) matches any
- **Query expansion:** When FTS5 returns fewer than `expansion_threshold` results (default 3), tags from partial matches find related memories. Set `expansion_threshold=0` to disable.

## Implementation Notes

- Backend: Turso SQLite HTTP API
- Credential auto-detection (v3.8.0): Scans env vars, then `/mnt/project/turso.env`, `/mnt/project/muninn.env`, `~/.muninn/.env`
- FTS5 search: Porter stemmer tokenizer with BM25 ranking
- Local SQLite cache for fast recall (< 5ms vs 150ms+ network)
- Thread-safe for background writes
- Repo defaults fallback: `scripts/defaults/` used when Turso and cache are both unavailable

## Session Continuity (v4.3.0)

Save and resume session state for cross-session persistence:

```python
from remembering import session_save, session_resume, sessions

# Save a checkpoint before ending session
session_save("Implementing FTS5 search", context={"files": ["cache.py"], "status": "in-progress"})

# In a new session: resume from last checkpoint
checkpoint = session_resume("previous-session-id")
print(checkpoint['summary'])      # What was happening
print(checkpoint['context'])      # Custom context data
print(len(checkpoint['recent_memories']))  # Recent memories from that session

# List available session checkpoints
for s in sessions():
    print(f"{s['session_id']}: {s['summary'][:60]}")
```

## Memory Consolidation (v4.2.0)

Automatically cluster related memories and synthesize summaries, reducing retrieval noise while preserving traceability:

```python
from remembering import consolidate

# Preview what would be consolidated
result = consolidate(dry_run=True)
for c in result['clusters']:
    print(f"Tag '{c['tag']}': {c['count']} memories")

# Actually consolidate (creates summaries, demotes originals to background)
result = consolidate(dry_run=False, min_cluster=3)
print(f"Consolidated {result['consolidated']} clusters, demoted {result['demoted']} memories")

# Scope to specific tags
result = consolidate(tags=["debugging"], dry_run=False)
```

How it works:
1. **Clustering**: Groups memories by shared tags (minimum `min_cluster` memories per group)
2. **Synthesis**: Creates a `type=world` summary memory tagged `consolidated` containing all originals
3. **Archival**: Demotes original memories to `priority=-1` (background)
4. **Traceability**: Summary's `refs` field lists all original memory IDs

## Advanced Topics

For architecture details, see [_ARCH.md](_ARCH.md).

See [references/advanced-operations.md](references/advanced-operations.md) for:

- Date-filtered queries (`recall_since`, `recall_between`, `since`/`until` parameters)
- Priority system and memory consolidation (`strengthen`, `weaken`)
- Therapy helpers and analysis helpers
- Handoff convention (cross-environment coordination)
- Session scoping and continuity (`session_save`, `session_resume`, `sessions`)
- Retrieval observability and retention management
- Export/import for portability
- Type-safe results (MemoryResult) details
- Proactive memory hints (`recall_hints`)
- GitHub access detection and unified API
- Progressive disclosure and priority-based ordering
- Decision alternatives (`get_alternatives`) and memory consolidation (`consolidate`)
- Reference chain traversal (`get_chain`)
