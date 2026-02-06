# remembering/
*Files: 16 | Subdirectories: 2*

## Subdirectories

- [defaults/](./defaults/_MAP.md)
- [tests/](./tests/_MAP.md)

## Files

### CHANGELOG.md
- Muninn Memory System - Changelog `h1` :1
- [3.7.0] - 2026-02-05 `h2` :5
- [3.6.0] - 2026-01-31 `h2` :11
- [3.6.0] - 2026-01-31 `h2` :17
- [3.5.0] - 2026-01-27 `h2` :32
- [3.4.0] - 2026-01-25 `h2` :39
- [3.4.0] - 2026-01-25 `h2` :50
- [3.3.3] - 2026-01-22 `h2` :64
- [3.3.2] - 2026-01-22 `h2` :70
- [3.3.2] - 2026-01-22 `h2` :81
- [3.3.1] - 2026-01-22 `h2` :95
- [3.3.0] - 2026-01-21 `h2` :101
- [3.2.1] - 2026-01-21 `h2` :111
- [3.2.0] - 2026-01-16 `h2` :115
- [3.2.0] - 2026-01-16 `h2` :121
- [3.1.0] - 2026-01-16 `h2` :150
- [3.0.0] - 2026-01-16 `h2` :156
- [3.0.0] - 2026-01-16 `h2` :174
- [2.2.1] - 2026-01-09 `h2` :196
- [2.1.1] - 2026-01-09 `h2` :216
- [2.1.0] - 2026-01-09 `h2` :226
- [2.0.2] - 2026-01-09 `h2` :232
- [2.0.1] - 2026-01-09 `h2` :238
- [1.0.1] - 2026-01-09 `h2` :249
- [2.0.0] - 2026-01-09 `h2` :259
- [0.14.1] - 2026-01-06 `h2` :265
- [0.14.1] - 2026-01-06 `h2` :271
- [0.14.0] - 2026-01-04 `h2` :278
- [0.13.1] - 2026-01-02 `h2` :284
- [0.13.0] - 2025-12-30 `h2` :301
- [0.12.2] - 2025-12-30 `h2` :313
- [0.12.1] - 2025-12-30 `h2` :317
- [0.12.0] - 2025-12-30 `h2` :350
- [0.11.0] - 2025-12-30 `h2` :389
- [0.10.1] - 2025-12-29 `h2` :421
- [0.10.0] - 2025-12-28 `h2` :460
- [0.9.1] - 2025-12-28 `h2` :513
- [0.9.0] - 2025-12-28 `h2` :532
- [0.8.0] - 2025-12-27 `h2` :581
- [0.7.1] - 2025-12-27 `h2` :615
- [0.7.0] - 2025-12-27 `h2` :642
- [0.6.1] - 2025-12-27 `h2` :687
- [0.6.0] - 2025-12-27 `h2` :711
- [0.4.0] - 2025-12-27 `h2` :747
- [0.3.1] - 2025-12-26 `h2` :766
- [0.3.0] - 2025-12-26 `h2` :773
- [0.1.0] - 2025-12-26 `h2` :782
- Summary `h2` :793

### CLAUDE.md
- Muninn Memory System - Claude Code Context `h1` :1
- ⚠️ CRITICAL REQUIREMENT: VERSION BUMPING ⚠️ `h2` :7
- Boot `h2` :33
- Meta: Using Muninn During Development `h2` :50
- Quick Reference `h2` :75
- Environment Variables `h2` :81
- Architecture `h2` :104
- Core API `h2` :145
- Memory Types `h2` :227
- HTTP API Format `h2` :236
- Testing `h2` :258
- File Structure `h2` :277
- Development Notes `h2` :290
- Lessons for Claude Code Agents `h2` :302
- What's New in v3.6.0 `h2` :360
- What's New in v3.5.0 `h2` :381
- What's New in v3.2.0 `h2` :408
- What's New in v3.7.0 `h2` :425
- What's New in v3.8.0 `h2` :442
- Known Limitations `h2` :467

### README.md
- remembering `h1` :1

### SKILL.md
- Remembering - Advanced Operations `h1` :12
- Two-Table Architecture `h2` :16
- Boot Sequence `h2` :25
- Journal System `h2` :99
- Config Table `h2` :129
- Memory Type System `h2` :245
- Priority System (v2.0.0) `h2` :262
- Background Writes (Agentic Pattern) `h2` :324
- Memory Versioning (Patch/Snapshot) `h2` :364
- Complex Queries `h2` :380
- Date-Filtered Queries `h2` :400
- Therapy Helpers `h2` :429
- Analysis Helpers `h2` :464
- FTS5 Search with Porter Stemmer (v0.13.0) `h2` :498
- Soft Delete `h2` :527
- Memory Quality Guidelines `h2` :539
- Handoff Convention `h2` :549
- Session Scoping (v3.2.0) `h2` :634
- Retrieval Observability (v3.2.0) `h2` :655
- Retention Management (v3.2.0) `h2` :672
- Export/Import for Portability `h2` :697
- Type-Safe Results (v3.4.0) `h2` :728
- Proactive Memory Hints (v3.4.0) `h2` :786
- Edge Cases `h2` :841
- Unified GitHub API (v3.8.0) `h2` :861
- Implementation Notes `h2` :876

### __init__.py
> Imports: `requests, json, uuid, threading, os`...
- *No top-level symbols*

### boot.py
> Imports: `json, os, shutil, subprocess, threading`...
- **classify_ops_key** (f) `(key: str)` :132
- **detect_github_access** (f) `()` :152
- **github_api** (f) `(endpoint: str, *, method: str = "GET", body: dict = None,
               accept: str = "application/vnd.github+json")` :229
- **group_ops_by_topic** (f) `(ops_entries: list)` :312
- **profile** (f) `()` :363
- **ops** (f) `(include_reference: bool = False)` :368
- **boot** (f) `()` :468
- **journal** (f) `(topics: list = None, user_stated: str = None, my_intent: str = None)` :662
- **journal_recent** (f) `(n: int = 10)` :679
- **journal_prune** (f) `(keep: int = 40)` :695
- **therapy_scope** (f) `()` :709
- **therapy_session_count** (f) `()` :724
- **decisions_recent** (f) `(n: int = 10, conf: float = 0.7)` :733
- **group_by_type** (f) `(memories: list)` :748
- **group_by_tag** (f) `(memories: list)` :764
- **muninn_export** (f) `()` :784
- **handoff_pending** (f) `()` :798
- **handoff_complete** (f) `(handoff_id: str, completion_notes: str, version: str = None)` :813
- **muninn_import** (f) `(data: dict, *, merge: bool = False)` :845

### bootstrap.py
> Imports: `sys, os`
- **create_tables** (f) `()` :22
- **migrate_schema** (f) `()` :70
- **seed_config** (f) `()` :132
- **verify** (f) `()` :178

### cache.py
> Imports: `sqlite3, json, uuid, datetime, .`...
- **cache_stats** (f) `()` :591
- **recall_stats** (f) `(limit: int = 100)` :624
- **top_queries** (f) `(n: int = 10)` :679

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
- **config_set_priority** (f) `(key: str, priority: int)` :99
- **config_list** (f) `(category: str = None)` :127

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
           auto_strengthen: bool = False, raw: bool = False,
           expansion_threshold: int = 3,
           limit: int = None)` :219
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any",
                 session_id: str = None, raw: bool = False)` :499
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None, raw: bool = False)` :566
- **forget** (f) `(memory_id: str)` :635
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)` :653
- **reprioritize** (f) `(memory_id: str, priority: int)` :721
- **memory_histogram** (f) `()` :762
- **prune_by_age** (f) `(older_than_days: int, priority_floor: int = 0, dry_run: bool = True)` :818
- **prune_by_priority** (f) `(max_priority: int = -1, dry_run: bool = True)` :864
- **strengthen** (f) `(memory_id: str, boost: int = 1)` :903
- **weaken** (f) `(memory_id: str, drop: int = 1)` :943

### result.py
> Imports: `typing`
- **MemoryResult** (C) :77
  - **__init__** (m) `(self, data: dict)` :96
  - **__getattr__** (m) `(self, name: str)` :100
  - **__setattr__** (m) `(self, name: str, value: Any)` :118
  - **__getitem__** (m) `(self, key: str)` :125
  - **__contains__** (m) `(self, key: str)` :140
  - **__iter__** (m) `(self)` :144
  - **__len__** (m) `(self)` :148
  - **__repr__** (m) `(self)` :152
  - **__str__** (m) `(self)` :159
  - **_error_message** (m) `(self, field: str, error_type: str)` :163
  - **get** (m) `(self, key: str, default: Any = None)` :177
  - **keys** (m) `(self)` :196
  - **values** (m) `(self)` :200
  - **items** (m) `(self)` :204
  - **to_dict** (m) `(self)` :208
  - **copy** (m) `(self)` :217
- **MemoryResultList** (C) :222
  - **__repr__** (m) `(self)` :229
  - **to_dicts** (m) `(self)` :234
- **wrap_results** (f) `(results: List[dict])` :255

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

