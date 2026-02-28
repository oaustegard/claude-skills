# Remembering — Architecture Reference

> Developer orientation document. Reduces repeated archaeology sessions.

## Schema Overview

### Remote Database (Turso SQLite via HTTP)

Two tables, no joins at query time:

```
config                              memories
├── key TEXT PK                     ├── id TEXT PK (UUID)
├── value TEXT                      ├── type TEXT
├── category TEXT (profile|ops|     │   (decision|world|anomaly|
│   journal)                        │    experience|interaction|procedure)
├── updated_at TEXT                 ├── t TEXT (ISO timestamp, creation time)
├── char_limit INTEGER              ├── summary TEXT (content)
├── read_only BOOLEAN               ├── confidence REAL (0.0-1.0)
├── boot_load INTEGER (0|1)         ├── tags TEXT (JSON array)
└── priority INTEGER                ├── refs TEXT (JSON array: memory IDs + typed objects)
                                    ├── priority INTEGER (-1 bg, 0 normal, 1 important, 2 critical)
Indexes:                            ├── session_id TEXT
  idx_config_category               ├── created_at TEXT
                                    ├── updated_at TEXT
                                    ├── deleted_at TEXT (soft delete)
                                    ├── valid_from TEXT
                                    ├── access_count INTEGER
                                    └── last_accessed TEXT

                                    Indexes:
                                      idx_memories_t (t DESC)
                                      idx_memories_priority (priority DESC, t DESC)
                                      idx_memories_session_id (session_id)

memory_fts (FTS5 virtual table)
├── id UNINDEXED
├── summary           (BM25 weight: 1.0)
└── tags              (BM25 weight: 1.0, raised from 0.5 in v5.1.0 #309)
tokenize='porter unicode61'

Triggers:
  memories_fts_ai: INSERT → FTS5 sync
  memories_fts_au: UPDATE → FTS5 re-index (if not soft-deleted)
  memories_fts_sd: soft-DELETE → FTS5 removal
```

## Module Map

```
remembering/
├── SKILL.md                 User-facing docs + frontmatter
├── _ARCH.md                 This file
│
└── scripts/
    ├── __init__.py          API export manifest
    ├── state.py             Module globals, constants, session ID
    │                        Zero imports from other modules (breaks cycles)
    ├── turso.py             Turso HTTP API: _exec(), _exec_batch(), _fts5_search(),
    │                        credential loading, retry logic (503/429/SSL)
    ├── memory.py            Core CRUD: remember, recall, forget, supersede,
    │                        get_chain, recall_batch, remember_batch,
    │                        recall_since, recall_between, group_by_type, group_by_tag,
    │                        curate (#295), decision_trace (#297), _resolve_memory_id (#244)
    ├── config.py            Config CRUD: get/set/delete/list
    ├── boot.py              Boot sequence, journal, therapy, handoff, session continuity
    ├── hints.py             Proactive memory surfacing via Turso FTS5 (recall_hints)
    ├── result.py            Type-safe MemoryResult/MemoryResultList wrappers
    ├── utilities.py         Runtime utility installation: materializes utility-code
    │                        memories to /home/claude/muninn_utils/ at boot
    └── defaults/
        ├── ops.json         Fallback ops config (used if Turso unreachable)
        └── profile.json     Fallback profile config
```

### Import Dependency Graph

```
state.py (no internal imports)
  ↑
turso.py (imports state)
  ↑
config.py (imports state, turso)
  ↑
memory.py (imports state, turso, config, result)
  ↑
boot.py (imports state, turso, memory, config, utilities)
hints.py (imports state, turso, memory)
result.py (no internal imports)
utilities.py (imports state, turso)
```

## Data Flow

### Boot Sequence

```
boot()
  ├─ turso._init()                 Load credentials, set headers
  ├─ _load_ops_topics()            Load topic mapping from config table
  ├─ _exec_batch([profile, ops])   Single HTTP request for both config sections
  ├─ detect_github_access()        Check gh CLI + tokens
  ├─ install_utilities()           Materialize utility-code memories to disk
  └─ _format_boot_output()         Markdown with organized sections
```

### Write Path (remember)

```
remember(what, type, ...)
  ├─ Validate type ∈ TYPES
  ├─ Generate UUID, timestamp
  ├─ if sync=True: _write_memory()        Blocking HTTP POST to Turso
  │  else: Thread → _write_memory()       Background write, returns immediately
  ├─ _fts5_sync (via trigger)             Turso triggers handle FTS5 index
  └─ Auto-append novel tags to config     recall-triggers config entry
```

### Read Path (recall)

```
recall(search, ...)
  ├─ Resolve tags_all/tags_any → tags + tag_mode
  ├─ _fts5_search()                FTS5 MATCH with Porter stemming + BM25 ranking
  │    └─ on failure/empty:        LIKE fallback via _query()
  ├─ if few results:               Query expansion via tags
  ├─ _update_access_tracking()     Background: increment counters in Turso
  └─ wrap_results()                → MemoryResultList
```

### Retry Logic

```
_retry_with_backoff(fn, ...)
  ├─ Transient errors: 503, 429, ssl.SSLError, ConnectionError
  ├─ Non-transient: 400, 401, 403, 404 → immediate raise
  ├─ Backoff: 1s → 2s → 4s (3 attempts default)
  └─ Exhaustion: raises last exception
```

### Ranking Algorithm

```
With search term (FTS5):
  composite_score = BM25(fts) × priority_weight × recency_decay

With search term + episodic=True (v5.1.0, #296):
  composite_score = BM25(fts) × priority_weight × recency_decay × access_boost

Without search term:
  composite_score = recency_weight × priority_weight

Where:
  recency_decay  = 1 / (1 + age_in_days × 0.01)
  priority_weight = 1 + priority × 0.3               [-1→0.7, 0→1.0, 1→1.3, 2→1.6]
  access_boost   = 1 + ln(1 + access_count) × 0.2    [0→1.0, 1→1.14, 10→1.48]
  BM25 weights   = id:0, summary:1.0, tags:1.0       (tags raised from 0.5 in v5.1.0 #309)
```

## Runtime Utilities (muninn_utils)

At boot, `install_utilities()` materializes memories tagged `utility-code` from Turso
into `/home/claude/muninn_utils/`. These are not part of the skill ZIP — they live in
the database and are written to disk at runtime.

Current utilities (as of v5.0.0):

| Utility | Purpose |
|---------|---------|
| `therapy.py` | Structured memory consolidation and quality improvement sessions |
| `connection_finder.py` | Finds semantically related orphan memories for ref-building |
| `serendipity.py` | Surfaces unconnected memory pairs that might be related |
| `bulk_forget.py` | Delete multiple memories at once with logging |
| `batch_supersede.py` | Supersede multiple memories with same content |
| `add_ref.py` | Add reference between two memories without full supersede |
| `deliver.py` | Fuse memory storage + file output into single call |
| `task.py` | Structural forcing function for multi-step work |
| `validate_fields.py` | Validate recall field access before use |
| `memory_graph.py` | Generate interactive D3 force graph of memory topology |
| `strengthen_memory.py` | Boost priority/confidence for important memories |
| `github_pages.py` | Publish files to oaustegard.github.io via PR |
| `whtwnd.py` | Post/update/delete blog entries on WhiteWind (AT Protocol) |
| `wisp_deploy.py` | Deploy single-file static sites to wisp.place |
| `margin.py` | Read/write web annotations via margin.at |
| `tangled.py` | Social interactions with tangled.org (AT Protocol) |
| `backup_zip.py` | Date-stamped zip of a directory to /mnt/user-data/outputs |
| `test_remembering.py` | Comprehensive test suite (80 tests), run as muninn_utils module |

Utilities import from `remembering.scripts` with the skill directory on `sys.path`.
To update a utility, change the memory content in Turso (not a file in this repo).

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Turso HTTP API (not SQLite driver) | Works in sandboxed environments without native extensions |
| Turso as sole storage | Eliminated local SQLite sync complexity (~737 lines). Cache latency savings (~145ms) are negligible vs tool call overhead (~3-4s) |
| Two-table schema (config + memories) | Config is small/static (boot), memories grow unbounded |
| FTS5 with Porter stemmer | Morphological matching (running→run) without external dependencies |
| Server-side FTS5 triggers | FTS5 index kept consistent by DB triggers, not application code |
| Soft deletes (deleted_at) | Refs integrity: superseded memories still resolve for chains |
| JSON arrays for tags/refs | Flexible schema within SQLite, parsed on read |
| Priority clamping [-1, 2] | Bounded range prevents runaway priority inflation |
| Background access tracking | Don't block recall() for analytics updates |
| Retry with backoff | Handles transient Turso 503/429/SSL errors without caller involvement |
| Utilities stored as memories | No install step; utilities boot with the skill, versioned in DB |

## Performance Characteristics

| Operation | Typical Latency | Notes |
|-----------|----------------|-------|
| boot() | ~150ms | Single HTTP batch request, no background warming |
| recall() | ~150ms | Network round-trip to Turso FTS5 |
| remember(sync=True) | ~150ms | Blocking HTTP write |
| remember(sync=False) | <1ms | Returns immediately, background write |
| FTS5 MATCH | <5ms server-side | Porter stemmer + BM25 ranking, executed in Turso |
| recall_batch() | ~150ms | Single HTTP batch for multiple queries |

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

## Deprecated / Removed

| What | When | Notes |
|------|------|-------|
| Local SQLite cache (~/.muninn/cache.db) | v5.0.0 (#300, #301) | Eliminated in favor of Turso FTS5. Net -570 lines |
| cache.py | v5.0.0 | Deleted (737 lines). Was memory_index, memory_full, memory_fts, recall_logs, cache_meta tables |
| cache_stats, recall_stats, top_queries | v5.0.0 | Exported functions removed with cache module |
| use_cache parameter in recall() | v5.0.0 | Deprecated. Accepted but ignored |
| Background cache warming thread | v5.0.0 | Removed from boot sequence |
| Embeddings (OpenAI) | v4.0.0 | Removed dependency. FTS5+BM25 sufficient |
| entities column | v2.0.0 | Removed from schema |
| importance/salience | v2.0.0 | Replaced by priority integer |
| memory_class | v2.0.0 | Removed (was unused) |
| valid_to column | v2.0.0 | Soft delete via deleted_at instead |
| remember_bg() | v0.6.0 | Deprecated alias for remember(sync=False) |
