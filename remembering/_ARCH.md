# Remembering - Architecture Reference

> Generated for developer orientation. Reduces repeated archaeology sessions.

## Schema Overview

### Remote Database (Turso SQLite via HTTP)

Two tables, no joins at query time:

```
config                              memories
├── key TEXT PK                     ├── id TEXT PK (UUID)
├── value TEXT                      ├── type TEXT (decision|world|anomaly|experience|interaction)
├── category TEXT (profile|ops|     ├── t TEXT (ISO timestamp, creation time)
│   journal)                        ├── summary TEXT (content)
├── updated_at TEXT                 ├── confidence REAL (0.0-1.0)
├── char_limit INTEGER              ├── tags TEXT (JSON array)
├── read_only BOOLEAN               ├── refs TEXT (JSON array: memory IDs + typed objects)
├── boot_load INTEGER (0|1)         ├── priority INTEGER (-1 bg, 0 normal, 1 important, 2 critical)
└── priority INTEGER                ├── session_id TEXT
                                    ├── created_at TEXT
Indexes:                            ├── updated_at TEXT
  idx_config_category               ├── deleted_at TEXT (soft delete)
                                    ├── valid_from TEXT
                                    ├── access_count INTEGER
                                    └── last_accessed TEXT

                                    Indexes:
                                      idx_memories_t (t DESC)
                                      idx_memories_priority (priority DESC, t DESC)
                                      idx_memories_session_id (session_id)
```

### Local Cache (~/.muninn/cache.db)

SQLite with FTS5. Populated at boot, updated on writes.

```
memory_index          memory_full           memory_fts (FTS5)
├── id TEXT PK        ├── id TEXT PK        ├── id UNINDEXED
├── type              ├── summary           ├── summary
├── t                 ├── refs              └── tags
├── tags (JSON)       ├── valid_from        tokenize='porter unicode61'
├── summary_preview   ├── access_count
├── confidence        └── last_accessed     config_cache
├── priority                                ├── key TEXT PK
├── session_id        recall_logs           ├── value
├── last_accessed     ├── id TEXT PK        ├── category
├── access_count      ├── t, query          └── boot_load
└── has_full (0|1)    ├── filters (JSON)
                      ├── n_requested       cache_meta
                      ├── n_returned        ├── key TEXT PK
                      ├── exec_time_ms      └── value
                      ├── used_cache
                      └── used_semantic_fallback
```

## Module Map

```
remembering/
├── __init__.py              Re-exports from scripts/ (thin shim)
├── SKILL.md                 User-facing docs + frontmatter
├── _ARCH.md                 This file
│
└── scripts/
    ├── __init__.py          API export manifest (~100 lines)
    ├── state.py             Module globals, constants, session ID
    │                        Zero imports from other modules (breaks cycles)
    ├── turso.py             Turso HTTP API: _exec(), _exec_batch(), credential loading
    ├── cache.py             Local SQLite + FTS5: init, query, populate, stats
    ├── memory.py            Core CRUD: remember, recall, forget, supersede, get_chain
    ├── config.py            Config CRUD: get/set/delete/list
    ├── boot.py              Boot sequence, journal, therapy, handoff, session continuity
    ├── hints.py             Proactive memory surfacing (recall_hints)
    ├── result.py            Type-safe MemoryResult/MemoryResultList wrappers
    ├── utilities.py         Runtime utility code injection from memories
    └── defaults/
        ├── ops.json         Fallback ops config
        └── profile.json     Fallback profile config
```

### Import Dependency Graph

```
state.py (no internal imports)
  ↑
turso.py (imports state)
  ↑
cache.py (imports state, turso)
  ↑
config.py (imports state, turso, cache)
  ↑
memory.py (imports state, turso, cache, config, result)
  ↑
boot.py (imports state, turso, cache, memory, config, utilities)
hints.py (imports state, turso, cache, memory)
result.py (no internal imports)
utilities.py (imports state, turso)
```

## Data Flow

### Boot Sequence

```
boot()
  ├─ _init_local_cache()          Create/open ~/.muninn/cache.db
  ├─ _load_ops_topics()           Load topic mapping from config
  ├─ _exec_batch([profile, ops])  Single HTTP request for both
  │    └─ _cache_config()         Write-through to local cache
  ├─ Thread → _warm_cache()       Background: fetch 500 recent memories
  │    ├─ _cache_populate_index()  Headlines only
  │    └─ _cache_populate_full()   Full content + FTS5 index
  ├─ detect_github_access()       Check gh CLI + tokens
  ├─ install_utilities()          Materialize utility-code memories to disk
  └─ _format_boot_output()        Markdown with organized sections
```

### Write Path (remember)

```
remember(what, type, ...)
  ├─ Validate type ∈ TYPES
  ├─ Generate UUID, timestamp
  ├─ _cache_memory()              Write-through: index + full + FTS5
  ├─ if sync: _write_memory()     Blocking HTTP to Turso
  │  else: Thread → _write_memory()  Background write
  └─ Update recall-triggers config  Auto-append novel tags
```

### Read Path (recall)

```
recall(search, ...)
  ├─ Resolve tags_all/tags_any → tags + tag_mode
  ├─ if cache available:
  │    ├─ _cache_query_index()    FTS5 MATCH + BM25 + recency + priority
  │    ├─ if few results:         Query expansion via tags
  │    ├─ _fetch_full_content()   Lazy-load from Turso for cache misses
  │    └─ _cache_populate_full()  Update cache with fetched content
  ├─ else: _query()              Direct Turso SQL (LIKE search)
  ├─ _update_access_tracking()   Background: increment counters
  └─ wrap_results()              → MemoryResultList
```

### Ranking Algorithm

```
With search term:
  composite_rank = BM25(fts) * recency_weight * priority_weight

Without search term:
  composite_score = recency_weight * priority_weight

Where:
  recency_weight = 1 / (1 + days_since_access / 30)    [0.5 if never accessed]
  priority_weight = 1 + priority * 0.5                  [-1→0.5, 0→1.0, 1→1.5, 2→2.0]
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Turso HTTP API (not SQLite driver) | Works in sandboxed environments without native extensions |
| Two-table schema (config + memories) | Config is small/static (boot), memories grow unbounded |
| FTS5 with Porter stemmer | Morphological matching (running→run) without external dependencies |
| Write-through cache | Immediate local availability, eventual remote consistency |
| Soft deletes (deleted_at) | Refs integrity: superseded memories still resolve for chains |
| JSON arrays for tags/refs | Flexible schema within SQLite, parsed on read |
| Priority clamping [-1, 2] | Bounded range prevents runaway priority inflation |
| Background access tracking | Don't block recall() for analytics updates |

## Deprecated / Removed

| What | When | Notes |
|------|------|-------|
| Embeddings (OpenAI) | v4.0.0 | Removed dependency. FTS5+BM25 sufficient |
| entities column | v2.0.0 | Removed from schema |
| importance/salience | v2.0.0 | Replaced by priority integer |
| memory_class | v2.0.0 | Removed (was unused) |
| valid_to column | v2.0.0 | Soft delete via deleted_at instead |
| remember_bg() | v0.6.0 | Deprecated alias for remember(sync=False) |

## Credential Resolution Order

```
1. Environment: TURSO_TOKEN + TURSO_URL
2. configuring skill (Claude.ai)
3. Well-known files:
   - /mnt/project/turso.env
   - /mnt/project/muninn.env
   - ~/.muninn/.env
4. Legacy: /mnt/project/turso-token.txt (token only)
5. Default URL: https://assistant-memory-oaustegard.aws-us-east-1.turso.io
```

## Performance Characteristics

| Operation | Typical Latency | Notes |
|-----------|----------------|-------|
| boot() | ~150ms | Single HTTP batch + background cache warm |
| recall() cache hit | <5ms | Local FTS5 query |
| recall() cache miss | 150ms+ | Network round-trip to Turso |
| remember(sync=True) | 150ms+ | Blocking HTTP write |
| remember(sync=False) | <1ms | Returns immediately, background write |
| FTS5 MATCH | <1ms | Porter stemmer + BM25 ranking |
