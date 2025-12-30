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
from remembering import recall_since, recall_between
from remembering import config_get, config_set, config_list, profile, ops, boot, boot_fast
from remembering import journal, journal_recent, journal_prune
from remembering import therapy_scope, therapy_session_count, decisions_recent
from remembering import group_by_type, group_by_tag
from remembering import handoff_pending, handoff_complete
from remembering import muninn_export, muninn_import
from remembering import strengthen, weaken  # v0.10.0 salience adjustment
from remembering import cache_stats  # v0.7.0 cache diagnostics
from remembering import embedding_stats, retry_embeddings  # v0.10.1 embedding reliability

# Store a memory (type required, with optional embedding)
id = remember("User prefers dark mode", "decision", tags=["ui"], conf=0.9)
id = remember("Quick note", "world", embed=False)  # Skip embedding

# Background write (non-blocking)
remember_bg("Project uses React", "world", tags=["tech"])

# Query memories - FTS5 ranked search (v0.9.0)
memories = recall("dark mode")  # FTS5 search, ranked by BM25
memories = recall(type="decision", conf=0.8)  # filtered
memories = recall(tags=["ui"])  # by tag (any match)
memories = recall(tags=["urgent", "task"], tag_mode="all")  # require all tags
memories = recall("concept", semantic_fallback=True)  # auto-fallback to semantic
memories = recall("exact term", semantic_fallback=False)  # FTS5 only

# Query memories - date-filtered
recent = recall_since("2025-12-01T00:00:00Z", n=50)  # after timestamp
range_mems = recall_between("2025-12-01T00:00:00Z", "2025-12-26T00:00:00Z")

# Query memories - semantic search (requires EMBEDDING_API_KEY)
similar = semantic_recall("user interface preferences", n=5)
similar = semantic_recall("performance issues", type="anomaly")

# Soft delete
forget(memory_id)

# Version a memory (creates new, links to old)
new_id = supersede(old_id, "Updated preference", "decision")

# Salience adjustment for memory consolidation (v0.10.0)
strengthen("memory-id", factor=1.5)  # Boost salience (default 1.5x)
weaken("memory-id", factor=0.5)      # Reduce salience (default 0.5x)

# Embedding reliability monitoring and retry (v0.10.1)
stats = embedding_stats()  # Check embedding coverage and failure rates
if stats['failure_rate'] > 5.0:
    result = retry_embeddings(limit=50)  # Batch retry failed embeddings (default: 100 per API call)
    # Or customize batch size: retry_embeddings(limit=200, batch_size=50)

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

# Boot sequence - fastest (recommended, ~130ms)
profile, ops, journal = boot_fast()  # single HTTP request, 3 queries
# Returns: (profile_list, ops_list, journal_list)

# Boot sequence - compressed output (~150ms, ~700 tokens)
output = boot()  # single HTTP request, returns formatted string
print(output)  # Shows profile/ops/journal with key + first line format

# Boot sequence - individual calls (SLOW: ~1100ms, 3 HTTP requests)
# Only use if you need fine-grained control
recent_decisions = decisions_recent(10, conf=0.7)  # recent decisions with conf >= 0.7
for d in recent_decisions:
    print(f"[{d['t'][:10]}] {d['summary'][:80]}")

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

## Recent Enhancements

### v0.10.1 (2025-12-29)
✅ **Embedding Reliability Monitoring & Batch Retry**:
- New `embedding_stats()` function for tracking embedding coverage and failure rates
  - Returns total/with/without embeddings counts
  - Calculates failure rate percentage
  - Provides 7-day timeline of embedding failures
  - Lists recent memories without embeddings
- New `retry_embeddings(limit, dry_run, batch_size)` function for batch-retrying failed embeddings
  - Uses OpenAI's batch embedding API (up to 2048 texts per request)
  - Processes memories that are missing embeddings (NULL in embedding column)
  - Useful after API outages (503 errors) or when API key was initially missing
  - Supports dry_run mode to preview what would be retried
  - Updates both Turso database and local cache
  - Benefits: Simpler retry logic (one batch retry vs many individual retries)

**Investigation Results**:
- Overall embedding failure rate: 20.9% (38 of 182 memories)
- Root causes identified:
  - Dec 22-24: 100% failure (23 memories) - EMBEDDING_API_KEY not configured
  - Dec 26-28: 7-19% failure - mix of API outages and intermittent 503 errors
- Recent days (Dec 27-28): 7-9% failure rate, still above 5% threshold
- Retry logic working correctly (exponential backoff: 1s, 2s, 4s)
- System gracefully degrades: FTS5 search continues working when embeddings fail

**API Changes**:
```python
# Monitor embedding health
stats = embedding_stats()
print(f"Failure rate: {stats['failure_rate']:.1f}%")

# Batch retry missing embeddings
result = retry_embeddings(limit=50)
print(f"Successfully embedded {result['successful']} memories")
```

**Recommendation**: Run `retry_embeddings()` after extended API outages or when EMBEDDING_API_KEY is first configured. Monitor `embedding_stats()` during therapy sessions to track embedding health over time.

### v0.10.0 (2025-12-28)
✅ **Critical Bug Fixes**:
- Fixed cache auto-init bug: cache now auto-initializes on module import if DB exists
  - Fixes: remember() and recall() now work across bash_tool calls (different Python processes)
  - Impact: Eliminates "memory stored but not found" issues in multi-step workflows
- Fixed ambiguous column names in semantic_recall() vector search
  - All column references now qualified with table names (memories.*, m2.*)
  - Prevents SQL errors when JOIN queries include columns with same names
- Fixed VERSION file exclusion in release workflow
  - VERSION file now included in skill ZIP for runtime version detection
  - Enables version-aware features and handoff_complete() auto-versioning

✅ **Salience Decay & Composite Ranking (Biological Memory Model)**:
- New `salience` column for therapy-adjustable memory ranking multiplier (default 1.0)
- Composite ranking formula: `BM25 * salience * recency_weight * access_weight`
  - `recency_weight`: 1 / (1 + days_since_access / 30) - exponential decay over 30-day half-life
  - `access_weight`: ln(1 + access_count) - logarithmic boost for frequently accessed memories
  - `salience`: therapy-adjustable multiplier for manual consolidation
- Access tracking automatically updates both Turso and cache for ranking consistency
- New API functions for memory consolidation:
  - `strengthen(memory_id, factor=1.5)`: Boost salience for confirmed patterns
  - `weaken(memory_id, factor=0.5)`: Reduce salience for noise/obsolete memories

**Performance Impact:**
- recall() with search: <5ms (composite ranking adds negligible overhead)
- recall() without search: <5ms (composite score replaces simple time sort)
- strengthen()/weaken(): ~150ms (updates both Turso and cache)

**Migration**: Run `python bootstrap.py` to add salience column. Existing memories default to salience=1.0.

**Example - Therapy Session:**
```python
from remembering import therapy_scope, strengthen, weaken, remember

# Get unprocessed memories
cutoff, mems = therapy_scope()

# Identify patterns
for m in mems:
    if 'performance' in m.get('tags', []):
        strengthen(m['id'], factor=2.0)  # Reinforce performance insights
    elif m.get('confidence', 1.0) < 0.3:
        weaken(m['id'], factor=0.3)  # Downrank low-confidence memories

# Record therapy session
remember("Therapy: Strengthened performance patterns, weakened speculation",
         "experience", tags=["therapy"])
```

### v0.9.1 (2025-12-28)
✅ **Critical Bug Fixes**:
- Fixed tag filtering with `tag_mode="all"` - now correctly requires ALL tags to match
- Fixed FTS5 duplicate entries by using DELETE + INSERT pattern instead of INSERT OR REPLACE
- Added `tag_mode` parameter to `_cache_query_index()` for proper tag intersection

**Bug 1 - Tag Filtering**: The `_cache_query_index()` function didn't accept or respect the `tag_mode` parameter, always using OR logic for tags. Now correctly supports both `tag_mode="any"` (OR) and `tag_mode="all"` (AND).

**Bug 2 - FTS5 Duplicates**: FTS5 virtual tables don't support `INSERT OR REPLACE`, causing duplicate entries (212 FTS5 entries vs 107 memories = 1.98x ratio). Fixed by using `DELETE + INSERT` pattern, achieving 1.00x ratio.

**Architecture Verification**: Confirmed recall() implements hybrid-by-default search correctly:
- Primary: FTS5/BM25 local search (fast, <5ms)
- Fallback: Semantic search when FTS5 returns sparse results
- Tags work as filters on search results (correct SQL WHERE clause usage)

**Migration**: No schema changes. Existing caches will auto-fix on next write. Recommend clearing cache to remove FTS5 duplicates immediately: `rm -rf ~/.muninn/cache.db` then call `boot_fast()`.

### v0.9.0 (2025-12-28)
✅ **FTS5 Hybrid Search**:
- Replaced LIKE queries with FTS5 full-text search for ranked results
- Search results now ordered by BM25 relevance instead of recency
- Automatic semantic fallback when FTS5 returns few results
- New `_escape_fts5_query()` helper for safe query formatting

**Performance Impact:**
- FTS5 search: ~1.2ms (faster and ranked vs unranked LIKE)
- Boot time: ~1000ms (includes FTS5 table population)
- Semantic fallback: adds ~200ms when triggered (network round-trip)

**Implementation Changes:**
```python
# New FTS5 virtual table in cache
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    summary,
    tags
);

# Cache query now uses FTS5 MATCH with BM25 ranking
SELECT i.*, bm25(memory_fts) as rank
FROM memory_fts fts
JOIN memory_index i ON fts.id = i.id
WHERE memory_fts MATCH ?
ORDER BY rank;
```

**API Changes:**
```python
# recall() now has semantic fallback options
memories = recall("search term", n=5,
                  semantic_fallback=True,      # Enable semantic fallback (default)
                  semantic_threshold=2)        # Trigger when FTS5 < 2 results

# Disable semantic fallback for pure FTS5
memories = recall("search term", semantic_fallback=False)
```

**What triggers semantic fallback:**
- FTS5 returns fewer than `semantic_threshold` results (default: 2)
- Search term was provided
- `semantic_fallback=True` (default)
- EMBEDDING_API_KEY is configured

### v0.8.0 (2025-12-27)
✅ **Full Content at Boot**:
- `boot_fast()` now fetches all memory content in the initial batch query
- Eliminated async cache warming thread (no longer needed)
- Zero network calls after boot for any `recall()` query
- Simplified architecture: full content cached at boot, not lazy-loaded

**Performance Impact:**
- Boot time: ~566ms (vs ~130ms in v0.7.1, acceptable tradeoff for zero mid-conversation latency)
- All recall() queries: 1-3ms (guaranteed, no network variance)
- Network calls during conversation: 0 (was unpredictable in v0.7.0-v0.7.1)

**Implementation Changes:**
```python
# boot_fast() now fetches full memories in initial batch
results = _exec_batch([
    # ... profile, ops, journal ...
    ("SELECT * FROM memories WHERE deleted_at IS NULL ORDER BY t DESC LIMIT ?", [index_n]),
])
full_memories = results[3]

# Populate both index and full content immediately
_cache_populate_index(memory_index)
_cache_populate_full(full_memories)
# No async warm_cache thread needed
```

**Cache Sync Guarantee:**
- Added explicit guidance in SKILL.md: call `flush()` before conversation end if using `sync=False`
- Ensures all background writes persist before ephemeral container destruction

### v0.7.1 (2025-12-27)
✅ **Async Cache Warming**:
- `boot_fast()` now prefetches 20 recent full memories in background thread
- Cache warming happens during Claude's "thinking" time (non-blocking)
- Recall performance improved to ~1ms (vs ~300ms first-access in v0.7.0)
- Removed dead `_cache_clear()` call (unnecessary in ephemeral containers)

**Performance Impact:**
- Boot time: unchanged (~130ms)
- First recall after warming: ~1ms (299x improvement vs v0.7.0)
- Cache warming completes within ~3s in background

**Implementation:**
```python
# In boot_fast(), after populating index:
def _warm_cache():
    full_recent = _exec_batch([
        ("SELECT * FROM memories WHERE deleted_at IS NULL ORDER BY t DESC LIMIT 20", [])
    ])[0]
    _cache_populate_full(full_recent)

threading.Thread(target=_warm_cache, daemon=True).start()
```

### v0.7.0 (2025-12-27)
✅ **Local SQLite Cache with Progressive Disclosure**:
- New local cache in `~/.muninn/cache.db` for fast in-conversation queries
- `boot_fast()` now populates cache with memory index (headlines only)
- `recall()` queries local cache first (<5ms vs ~150ms network)
- Full content lazy-loaded from Turso on first access, then cached
- `remember()` writes to both cache and Turso (write-through)
- `cache_stats()` for cache diagnostics

**Performance Gains:**
- First recall after boot: ~300ms (fetches full content)
- Subsequent recalls: ~2ms (149x faster via cache hit)

**API Changes:**
```python
# boot_fast() now accepts cache parameters
profile, ops, journal = boot_fast(
    journal_n=5,       # journal entries
    index_n=500,       # memory headlines to cache
    use_cache=True     # enable local cache (default)
)

# recall() uses cache automatically
memories = recall(type="decision", n=5)  # Fast if boot_fast() was called

# Bypass cache if needed
memories = recall(type="decision", use_cache=False)

# Check cache status
stats = cache_stats()
# {'enabled': True, 'available': True, 'index_count': 79, 'full_count': 6, ...}
```

**Cache Architecture:**
```
~/.muninn/
└── cache.db          # Local SQLite mirror
    ├── memory_index  # Headlines: id, type, t, tags, summary_preview
    ├── memory_full   # Full content: lazy-loaded on demand
    └── config_cache  # Full config mirror
```

### v0.6.1 (2025-12-27)
✅ **Boot Performance Optimization**:
- New `boot_fast()` function for optimized boot sequence (~130ms vs ~1100ms)
- Batches profile + ops + journal queries in single HTTP request (8x faster)
- Use `boot_fast()` instead of calling `profile()`, `ops()`, `journal_recent()` separately

**API**:
```python
# Fast boot (recommended)
profile, ops, journal = boot_fast()  # ~130ms, 1 HTTP request

# With decisions (if needed)
profile, ops, journal, decisions = boot()  # ~200ms, 1 HTTP request

# Slow (avoid)
profile()  # ~485ms
ops()      # ~261ms
journal_recent()  # ~222ms
# Total: ~1100ms, 3 HTTP requests
```

### v0.6.0 (2025-12-27)
✅ **Bug Fixes**:
- Fixed ambiguous column error in `semantic_recall()` vector index query by qualifying all column references
- Fixed tag deserialization: all memory queries now return `tags`, `entities`, and `refs` as parsed lists (not JSON strings)

✅ **Unified Write API**:
- Added `sync` parameter to `remember()` (default `True` for backwards compatibility)
- `sync=False`: Non-blocking background write, returns immediately
- `sync=True`: Blocking write, waits for confirmation
- Deprecated `remember_bg()` - now an alias for `remember(..., sync=False)`
- Added `flush()` function to wait for all pending background writes

✅ **Batch Query Helper**:
- New `_exec_batch()` for executing multiple SQL statements in single pipeline request
- Reduces round-trip latency for multi-query operations
- Automatically parses JSON fields in all result sets

**Migration**: No schema changes, fully backwards compatible.

**API Changes**:
```python
# New unified API
remember("note", "world", sync=False)  # Background write
remember("important", "decision", sync=True)  # Blocking write
flush()  # Wait for pending writes

# Old API (still works, deprecated)
remember_bg("note", "world")  # Calls remember(..., sync=False)
```

### v0.4.0 (2025-12-27)
✅ **Importance Tracking**: New `importance` parameter in `remember()` for memory prioritization (default 0.5)
✅ **Access Analytics**: Automatic tracking of `access_count` and `last_accessed` for all recall operations
✅ **Memory Classification**: `memory_class` field distinguishes episodic vs semantic memories
✅ **Bitemporal Tracking**: `valid_from` and `valid_to` columns for tracking when facts became/stopped being true
✅ **Enhanced supersede()**: Automatically sets bitemporal fields when updating memories
✅ **Retry Logic**: Exponential backoff (1s, 2s, 4s) for 503/429 errors in embedding generation
✅ **Schema Extensions**: Six new columns added to memories table for advanced memory management

**New Parameters in remember():**
- `importance`: Float 0.0-1.0, defaults to 0.5
- `memory_class`: 'episodic' or 'semantic', defaults to 'episodic'
- `valid_from`: Timestamp when fact became true, defaults to creation time

**Migration Required**: Run `python bootstrap.py` to add new columns to existing databases

### v0.3.1 (2025-12-26)
✅ **Boot Sequence**: `decisions_recent()` for loading high-confidence decisions at session start
✅ **Documentation**: Added comprehensive boot sequence guide in SKILL.md

### v0.3.0 (2025-12-26)
✅ **Date-filtered Queries**: `recall_since()` and `recall_between()` for temporal filtering
✅ **Therapy Helpers**: `therapy_scope()` and `therapy_session_count()` for reflection workflows
✅ **Analysis Helpers**: `group_by_type()` and `group_by_tag()` for memory organization
✅ **Agent Guidance**: Added comprehensive import troubleshooting in CLAUDE.md

### v0.1.0
✅ **Vector/Semantic Search**: `semantic_recall()` with OpenAI embeddings and DiskANN index
✅ **Tag Match Modes**: `tag_mode="any"` or `tag_mode="all"` in `recall()`
✅ **Config Constraints**: `char_limit` and `read_only` flags in `config_set()`
✅ **Export/Import**: `muninn_export()` and `muninn_import()` for portability

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

- Semantic search requires OpenAI API key (paid service)
- Vector index creation requires newer Turso versions (falls back to brute-force)
- Embeddings not automatically regenerated on import
- Session ID currently hardcoded to "session" (not per-conversation tracking)
