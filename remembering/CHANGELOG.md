# Muninn Memory System - Changelog

All notable changes to the `remembering` skill (Muninn) are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.14.0] - 2026-01-04

### Added

- v0.14.0 - Remove embeddings, add Porter stemmer

## [0.13.1] - 2026-01-02

### Added

- Add browsing-bluesky skill and update remembering docs
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Fixed

- supersede() cache invalidation
- remembering skill cache invalidation and embedding warnings

### Other

- Update version to 0.13.1 in SKILL.md

## [0.13.0] - 2025-12-30

### Changed

- async cache warming, remove boot_fast
- remove boot_fast from public API, clean up version comments

### Fixed

- show complete profile + ops, remove changelog from CLAUDE.md
- show complete ops values, remove journal_n param

## [0.12.2] - 2025-12-30

- Release 0.12.2

## [0.12.1] - 2025-12-30

### Fixed

- **Strict Query Mode for therapy_scope() Bug Fix**
  - Fixed bug where `therapy_scope()` returned MOST RELEVANT therapy session instead of LATEST
  - Added `strict=True` parameter to `recall()` for timestamp-only ordering
  - Strict mode skips FTS5/BM25 ranking and uses plain SQL with `ORDER BY t DESC`
  - Updated `therapy_scope()` to use `strict=True` - now correctly returns newest session

### Technical Details

**Bug Background**:
- `recall()` always ordered by composite_rank (BM25 + salience + recency + access)
- When `therapy_scope()` asked for n=1, it got best-ranked match, not newest
- Example: Session #2 (2025-12-26) had composite_rank=-15.6, Session #4 (2025-12-28, newer) had composite_rank=-14.1
- Result: Muninn kept thinking sessions were older than they actually were

**Use Cases for Strict Mode**:
- `therapy_scope()`: Get newest therapy session by timestamp
- "All decisions from last week": Date filter + type, no ranking needed
- "Latest handoff": Tag match with timestamp order
- Any query where relevance ranking adds noise to chronological ordering

**API Changes**:
```python
# Strict mode: timestamp ordering, no ranking
sessions = recall(type="experience", tags=["therapy"], n=1, strict=True)

# Regular mode: composite ranking (BM25 + salience + recency + access)
sessions = recall(type="experience", tags=["therapy"], n=1)
```

## [0.12.0] - 2025-12-30

### Added

- **Query Logging for Retrieval Instrumentation (Phase 0)**
  - New `recall_logs` table in local cache tracks all recall() queries
  - Automatically logs: query text, filters, result counts, execution time, cache/semantic usage
  - Foundation for future relevance scoring and filtering (Phases 1-4)
  - Enables retrieval quality analysis and optimization

**Schema**:
```sql
CREATE TABLE recall_logs (
    id TEXT PRIMARY KEY,
    t TEXT NOT NULL,
    query TEXT,
    filters TEXT,              -- JSON: {type, tags, conf, tag_mode}
    n_requested INTEGER,
    n_returned INTEGER,
    exec_time_ms REAL,
    used_cache BOOLEAN,
    used_semantic_fallback BOOLEAN
);
```

**Usage**:
```python
# Query logs are written automatically by recall()
# View logs directly from cache DB at ~/.muninn/cache.db

import sqlite3
from pathlib import Path

conn = sqlite3.connect(str(Path.home() / ".muninn" / "cache.db"))
logs = conn.execute("SELECT * FROM recall_logs ORDER BY t DESC LIMIT 10").fetchall()
```

**Next Steps**: Phases 1-4 will add relevance scoring, filtering, outcome tracking, and calibration based on these logs.

## [0.11.0] - 2025-12-30

### Changed

- **Compressed Boot Output**
  - Modified `boot()` function to return formatted string instead of raw tuples
  - Output format: key + first line for config entries
  - Token reduction: ~4.3K chars (~1073 tokens) vs previous multi-line format
  - Simplified usage: `print(boot())` replaces 15-line boot_fast() + formatting block
  - Still populates local cache for fast subsequent recall() queries

**API Change**:
```python
# Old (v0.10.x and earlier)
profile, ops, journal, decisions = boot()
for p in profile:
    print(p['value'])

# New (v0.11.0+)
output = boot()
print(output)  # Shows compressed key + first line format

# Access full content when needed
from remembering import config_get
full_text = config_get("identity")
```

**Performance**:
- Execution: ~150ms (single HTTP request)
- Output: ~4.3K chars (~1073 tokens)
- Subsequent recall(): ~2ms via local cache

## [0.10.1] - 2025-12-29

### Added

- **Embedding Reliability Monitoring & Batch Retry**
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

## [0.10.0] - 2025-12-28

### Fixed

- Fixed cache auto-init bug: cache now auto-initializes on module import if DB exists
  - Fixes: remember() and recall() now work across bash_tool calls (different Python processes)
  - Impact: Eliminates "memory stored but not found" issues in multi-step workflows
- Fixed ambiguous column names in semantic_recall() vector search
  - All column references now qualified with table names (memories.*, m2.*)
  - Prevents SQL errors when JOIN queries include columns with same names
- Fixed VERSION file exclusion in release workflow
  - VERSION file now included in skill ZIP for runtime version detection
  - Enables version-aware features and handoff_complete() auto-versioning

### Added

- **Salience Decay & Composite Ranking (Biological Memory Model)**
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

## [0.9.1] - 2025-12-28

### Fixed

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

## [0.9.0] - 2025-12-28

### Added

- **FTS5 Hybrid Search**
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

## [0.8.0] - 2025-12-27

### Changed

- **Full Content at Boot**
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

## [0.7.1] - 2025-12-27

### Added

- **Async Cache Warming**
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

## [0.7.0] - 2025-12-27

### Added

- **Local SQLite Cache with Progressive Disclosure**
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

## [0.6.1] - 2025-12-27

### Added

- **Boot Performance Optimization**
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

## [0.6.0] - 2025-12-27

### Fixed

- Fixed ambiguous column error in `semantic_recall()` vector index query by qualifying all column references
- Fixed tag deserialization: all memory queries now return `tags`, `entities`, and `refs` as parsed lists (not JSON strings)

### Added

- **Unified Write API**
  - Added `sync` parameter to `remember()` (default `True` for backwards compatibility)
  - `sync=False`: Non-blocking background write, returns immediately
  - `sync=True`: Blocking write, waits for confirmation
  - Deprecated `remember_bg()` - now an alias for `remember(..., sync=False)`
  - Added `flush()` function to wait for all pending background writes

### Added

- **Batch Query Helper**
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

## [0.4.0] - 2025-12-27

### Added

- **Importance Tracking**: New `importance` parameter in `remember()` for memory prioritization (default 0.5)
- **Access Analytics**: Automatic tracking of `access_count` and `last_accessed` for all recall operations
- **Memory Classification**: `memory_class` field distinguishes episodic vs semantic memories
- **Bitemporal Tracking**: `valid_from` and `valid_to` columns for tracking when facts became/stopped being true
- **Enhanced supersede()**: Automatically sets bitemporal fields when updating memories
- **Retry Logic**: Exponential backoff (1s, 2s, 4s) for 503/429 errors in embedding generation
- **Schema Extensions**: Six new columns added to memories table for advanced memory management

**New Parameters in remember():**
- `importance`: Float 0.0-1.0, defaults to 0.5
- `memory_class`: 'episodic' or 'semantic', defaults to 'episodic'
- `valid_from`: Timestamp when fact became true, defaults to creation time

**Migration Required**: Run `python bootstrap.py` to add new columns to existing databases

## [0.3.1] - 2025-12-26

### Added

- **Boot Sequence**: `decisions_recent()` for loading high-confidence decisions at session start
- **Documentation**: Added comprehensive boot sequence guide in SKILL.md

## [0.3.0] - 2025-12-26

### Added

- **Date-filtered Queries**: `recall_since()` and `recall_between()` for temporal filtering
- **Therapy Helpers**: `therapy_scope()` and `therapy_session_count()` for reflection workflows
- **Analysis Helpers**: `group_by_type()` and `group_by_tag()` for memory organization
- **Agent Guidance**: Added comprehensive import troubleshooting in CLAUDE.md

## [0.1.0] - 2025-12-26

### Added

- **Vector/Semantic Search**: `semantic_recall()` with OpenAI embeddings and DiskANN index
- **Tag Match Modes**: `tag_mode="any"` or `tag_mode="all"` in `recall()`
- **Config Constraints**: `char_limit` and `read_only` flags in `config_set()`
- **Export/Import**: `muninn_export()` and `muninn_import()` for portability

---

## Summary

This changelog tracks the evolution of the Muninn memory system from its initial release (v0.1.0) through the current version (v0.12.1). Key themes include:

1. **Performance Optimization**: From initial implementation to local caching (v0.7.0), async warming (v0.7.1), and full content at boot (v0.8.0)
2. **Search Capabilities**: From basic queries to FTS5 hybrid search (v0.9.0) with semantic fallback
3. **Data Quality**: Bug fixes for caching (v0.9.1), embeddings (v0.10.1), and query ordering (v0.12.1)
4. **Advanced Features**: Salience decay (v0.10.0), batch embeddings (v0.10.1), query instrumentation (v0.12.0), and strict mode queries (v0.12.1)
5. **API Evolution**: From verbose boot sequences to compressed output (v0.11.0) and unified write API (v0.6.0)

For detailed API reference and usage examples, see [SKILL.md](SKILL.md) and [CLAUDE.md](CLAUDE.md).