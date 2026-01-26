# remembering/
*Files: 16 | Subdirectories: 1*

## Subdirectories

- [tests/](./tests/_MAP.md)

## Files

### CHANGELOG.md
- Muninn Memory System - Changelog `h1` :1
- [3.4.0] - 2026-01-25 `h2` :5
- [3.4.0] - 2026-01-25 `h2` :16
- [3.3.3] - 2026-01-22 `h2` :30
- [3.3.2] - 2026-01-22 `h2` :36
- [3.3.2] - 2026-01-22 `h2` :47
- [3.3.1] - 2026-01-22 `h2` :61
- [3.3.0] - 2026-01-21 `h2` :67
- [3.2.1] - 2026-01-21 `h2` :77
- [3.2.0] - 2026-01-16 `h2` :81
- [3.2.0] - 2026-01-16 `h2` :87
- [3.1.0] - 2026-01-16 `h2` :116
- [3.0.0] - 2026-01-16 `h2` :122
- [3.0.0] - 2026-01-16 `h2` :140
- [2.2.1] - 2026-01-09 `h2` :162
- [2.1.1] - 2026-01-09 `h2` :182
- [2.1.0] - 2026-01-09 `h2` :192
- [2.0.2] - 2026-01-09 `h2` :198
- [2.0.1] - 2026-01-09 `h2` :204
- [1.0.1] - 2026-01-09 `h2` :215
- [2.0.0] - 2026-01-09 `h2` :225
- [0.14.1] - 2026-01-06 `h2` :231
- [0.14.1] - 2026-01-06 `h2` :237
- [0.14.0] - 2026-01-04 `h2` :244
- [0.13.1] - 2026-01-02 `h2` :250
- [0.13.0] - 2025-12-30 `h2` :267
- [0.12.2] - 2025-12-30 `h2` :279
- [0.12.1] - 2025-12-30 `h2` :283
- [0.12.0] - 2025-12-30 `h2` :316
- [0.11.0] - 2025-12-30 `h2` :355
- [0.10.1] - 2025-12-29 `h2` :387
- [0.10.0] - 2025-12-28 `h2` :426
- [0.9.1] - 2025-12-28 `h2` :479
- [0.9.0] - 2025-12-28 `h2` :498
- [0.8.0] - 2025-12-27 `h2` :547
- [0.7.1] - 2025-12-27 `h2` :581
- [0.7.0] - 2025-12-27 `h2` :608
- [0.6.1] - 2025-12-27 `h2` :653
- [0.6.0] - 2025-12-27 `h2` :677
- [0.4.0] - 2025-12-27 `h2` :713
- [0.3.1] - 2025-12-26 `h2` :732
- [0.3.0] - 2025-12-26 `h2` :739
- [0.1.0] - 2025-12-26 `h2` :748
- Summary `h2` :759

### CLAUDE.md
- Muninn Memory System - Claude Code Context `h1` :1
- ⚠️ CRITICAL REQUIREMENT: VERSION BUMPING ⚠️ `h2` :7
- Boot `h2` :33
- Meta: Using Muninn During Development `h2` :50
- Quick Reference `h2` :75
- Environment Variables `h2` :81
- Architecture `h2` :104
- Core API `h2` :145
- Memory Types `h2` :225
- HTTP API Format `h2` :234
- Testing `h2` :256
- File Structure `h2` :275
- Development Notes `h2` :288
- Lessons for Claude Code Agents `h2` :300
- What's New in v3.2.0 `h2` :358
- Known Limitations `h2` :375

### README.md
- remembering `h1` :1

### SKILL.md
- Remembering - Advanced Operations `h1` :12
- Two-Table Architecture `h2` :16
- Boot Sequence `h2` :25
- Journal System `h2` :44
- Config Table `h2` :74
- Memory Type System `h2` :140
- Priority System (v2.0.0) `h2` :157
- Background Writes (Agentic Pattern) `h2` :219
- Memory Versioning (Patch/Snapshot) `h2` :259
- Complex Queries `h2` :275
- Date-Filtered Queries `h2` :295
- Therapy Helpers `h2` :324
- Analysis Helpers `h2` :359
- FTS5 Search with Porter Stemmer (v0.13.0) `h2` :393
- Soft Delete `h2` :417
- Memory Quality Guidelines `h2` :429
- Handoff Convention `h2` :439
- Session Scoping (v3.2.0) `h2` :524
- Retrieval Observability (v3.2.0) `h2` :545
- Retention Management (v3.2.0) `h2` :562
- Export/Import for Portability `h2` :587
- Type-Safe Results (v3.4.0) `h2` :618
- Proactive Memory Hints (v3.4.0) `h2` :660
- Edge Cases `h2` :715
- Implementation Notes `h2` :735

### __init__.py
> Imports: `requests, json, uuid, threading, os`...
- *No top-level symbols*

### boot.py
> Imports: `json, threading, datetime, ., .turso`...
- **classify_ops_key** (f) `(key: str)` :71
- **group_ops_by_topic** (f) `(ops_entries: list)` :90
- **profile** (f) `()` :117
- **ops** (f) `(include_reference: bool = False)` :122
- **boot** (f) `()` :175
- **journal** (f) `(topics: list = None, user_stated: str = None, my_intent: str = None)` :323
- **journal_recent** (f) `(n: int = 10)` :340
- **journal_prune** (f) `(keep: int = 40)` :356
- **therapy_scope** (f) `()` :370
- **therapy_session_count** (f) `()` :385
- **decisions_recent** (f) `(n: int = 10, conf: float = 0.7)` :394
- **group_by_type** (f) `(memories: list)` :409
- **group_by_tag** (f) `(memories: list)` :425
- **muninn_export** (f) `()` :445
- **handoff_pending** (f) `()` :459
- **handoff_complete** (f) `(handoff_id: str, completion_notes: str, version: str = None)` :474
- **muninn_import** (f) `(data: dict, *, merge: bool = False)` :506

### bootstrap.py
> Imports: `sys, os`
- **create_tables** (f) `()` :22
- **migrate_schema** (f) `()` :69
- **seed_config** (f) `()` :124
- **verify** (f) `()` :170

### cache.py
> Imports: `sqlite3, json, uuid, datetime, .`...
- **cache_stats** (f) `()` :566
- **recall_stats** (f) `(limit: int = 100)` :599
- **top_queries** (f) `(n: int = 10)` :654

### claude-ai-project-instructions.md
- Muninn `h1` :1
- Boot `h2` :5

### config.py
> Imports: `datetime, ., .turso, .cache`
- **config_get** (f) `(key: str)` :19
- **config_set** (f) `(key: str, value: str, category: str, *,
               char_limit: int = None, read_only: bool = False)` :25
- **config_delete** (f) `(key: str)` :66
- **config_set_boot_load** (f) `(key: str, boot_load: bool)` :72
- **config_list** (f) `(category: str = None)` :99

### hints.py
> Imports: `re, json, typing, collections, .`...
- **recall_hints** (f) `(context: str = None, *, terms: List[str] = None,
                 include_tags: bool = True, include_summaries: bool = True,
                 min_matches: int = 1)` :17

### memory.py
> Imports: `json, uuid, threading, time, atexit`...
- **remember** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
             refs: list = None, priority: int = 0, valid_from: str = None,
             sync: bool = True, session_id: str = None,
             # Deprecated parameters (ignored in v2.0.0, kept for backward compat)
             entities: list = None, importance: float = None, memory_class: str = None)` :70
- **remember_bg** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None,
                importance: float = None, memory_class: str = None, valid_from: str = None)` :170
- **flush** (f) `(timeout: float = 5.0)` :187
- **recall** (f) `(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any",
           use_cache: bool = True, strict: bool = False, session_id: str = None,
           auto_strengthen: bool = False, raw: bool = False)` :219
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any",
                 session_id: str = None, raw: bool = False)` :489
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None, raw: bool = False)` :556
- **forget** (f) `(memory_id: str)` :625
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)` :643
- **reprioritize** (f) `(memory_id: str, priority: int)` :711
- **memory_histogram** (f) `()` :752
- **prune_by_age** (f) `(older_than_days: int, priority_floor: int = 0, dry_run: bool = True)` :808
- **prune_by_priority** (f) `(max_priority: int = -1, dry_run: bool = True)` :854
- **strengthen** (f) `(memory_id: str, boost: int = 1)` :893
- **weaken** (f) `(memory_id: str, drop: int = 1)` :933

### result.py
> Imports: `typing`
- **MemoryResult** (C) :71
  - **__init__** (m) `(self, data: dict)` :90
  - **__getattr__** (m) `(self, name: str)` :94
  - **__setattr__** (m) `(self, name: str, value: Any)` :104
  - **__getitem__** (m) `(self, key: str)` :111
  - **__contains__** (m) `(self, key: str)` :118
  - **__iter__** (m) `(self)` :122
  - **__len__** (m) `(self)` :126
  - **__repr__** (m) `(self)` :130
  - **__str__** (m) `(self)` :137
  - **_error_message** (m) `(self, field: str, error_type: str)` :141
  - **get** (m) `(self, key: str, default: Any = None)` :155
  - **keys** (m) `(self)` :169
  - **values** (m) `(self)` :173
  - **items** (m) `(self)` :177
  - **to_dict** (m) `(self)` :181
  - **copy** (m) `(self)` :190
- **MemoryResultList** (C) :195
  - **__repr__** (m) `(self)` :202
  - **to_dicts** (m) `(self)` :207
- **wrap_results** (f) `(results: List[dict])` :212

### state.py
> Imports: `threading, os, pathlib`
- **get_session_id** (f) `()` :41
- **set_session_id** (f) `(session_id: str)` :57

### turso.py
> Imports: `importlib, importlib.util, json, os, time`...
- *No top-level symbols*

### utilities.py
> Imports: `os, sys`
- **install_utilities** (f) `()` :8

