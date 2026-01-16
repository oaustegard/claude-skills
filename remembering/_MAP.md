# remembering/
*Files: 15 | Subdirectories: 1*

## Subdirectories

- [tests/](./tests/_MAP.md)

## Files

### CHANGELOG.md
- Muninn Memory System - Changelog `h1` :1
- [3.2.0] - 2026-01-16 `h2` :5
- [3.1.0] - 2026-01-16 `h2` :34
- [3.0.0] - 2026-01-16 `h2` :40
- [3.0.0] - 2026-01-16 `h2` :58
- [2.2.1] - 2026-01-09 `h2` :80
- [2.1.1] - 2026-01-09 `h2` :100
- [2.1.0] - 2026-01-09 `h2` :110
- [2.0.2] - 2026-01-09 `h2` :116
- [2.0.1] - 2026-01-09 `h2` :122
- [1.0.1] - 2026-01-09 `h2` :133
- [2.0.0] - 2026-01-09 `h2` :143
- [0.14.1] - 2026-01-06 `h2` :149
- [0.14.1] - 2026-01-06 `h2` :155
- [0.14.0] - 2026-01-04 `h2` :162
- [0.13.1] - 2026-01-02 `h2` :168
- [0.13.0] - 2025-12-30 `h2` :185
- [0.12.2] - 2025-12-30 `h2` :197
- [0.12.1] - 2025-12-30 `h2` :201
- [0.12.0] - 2025-12-30 `h2` :234
- [0.11.0] - 2025-12-30 `h2` :273
- [0.10.1] - 2025-12-29 `h2` :305
- [0.10.0] - 2025-12-28 `h2` :344
- [0.9.1] - 2025-12-28 `h2` :397
- [0.9.0] - 2025-12-28 `h2` :416
- [0.8.0] - 2025-12-27 `h2` :465
- [0.7.1] - 2025-12-27 `h2` :499
- [0.7.0] - 2025-12-27 `h2` :526
- [0.6.1] - 2025-12-27 `h2` :571
- [0.6.0] - 2025-12-27 `h2` :595
- [0.4.0] - 2025-12-27 `h2` :631
- [0.3.1] - 2025-12-26 `h2` :650
- [0.3.0] - 2025-12-26 `h2` :657
- [0.1.0] - 2025-12-26 `h2` :666
- Summary `h2` :677

### CLAUDE.md
- Muninn Memory System - Claude Code Context `h1` :1
- Boot `h2` :5
- Meta: Using Muninn During Development `h2` :22
- Quick Reference `h2` :47
- Environment Variables `h2` :53
- Architecture `h2` :76
- Core API `h2` :117
- Memory Types `h2` :195
- HTTP API Format `h2` :204
- Testing `h2` :226
- File Structure `h2` :245
- Development Notes `h2` :258
- Lessons for Claude Code Agents `h2` :272
- What's New in v3.2.0 `h2` :330
- Known Limitations `h2` :347

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
- Background Writes (Agentic Pattern) `h2` :186
- Memory Versioning (Patch/Snapshot) `h2` :226
- Complex Queries `h2` :240
- Date-Filtered Queries `h2` :260
- Therapy Helpers `h2` :289
- Analysis Helpers `h2` :324
- FTS5 Search with Porter Stemmer (v0.13.0) `h2` :358
- Soft Delete `h2` :382
- Memory Quality Guidelines `h2` :394
- Handoff Convention `h2` :404
- Session Scoping (v3.2.0) `h2` :489
- Retrieval Observability (v3.2.0) `h2` :510
- Retention Management (v3.2.0) `h2` :527
- Export/Import for Portability `h2` :552
- Edge Cases `h2` :583
- Implementation Notes `h2` :603

### WORK_SESSION_PLAN.md
- Remembering skill augmentation plan (Claude Code session) `h1` :1
- Quick review (current behavior) `h2` :5
- Augmentation ideas (plan only) `h2` :10

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
- **migrate_schema** (f) `()` :65
- **seed_config** (f) `()` :169
- **verify** (f) `()` :215
- **migrate_v2** (f) `(dry_run: bool = True)` :231
- **migrate_config_v2** (f) `(dry_run: bool = True)` :408

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

### memory.py
> Imports: `json, uuid, threading, time, atexit`...
- **remember** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
             refs: list = None, priority: int = 0, valid_from: str = None,
             sync: bool = True, session_id: str = None,
             # Deprecated parameters (ignored in v2.0.0, kept for backward compat)
             entities: list = None, importance: float = None, memory_class: str = None)` :69
- **remember_bg** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None,
                importance: float = None, memory_class: str = None, valid_from: str = None)` :169
- **flush** (f) `(timeout: float = 5.0)` :186
- **recall** (f) `(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any",
           use_cache: bool = True, strict: bool = False, session_id: str = None)` :218
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any", session_id: str = None)` :463
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None)` :524
- **forget** (f) `(memory_id: str)` :588
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)` :606
- **reprioritize** (f) `(memory_id: str, priority: int)` :637
- **memory_histogram** (f) `()` :678
- **prune_by_age** (f) `(older_than_days: int, priority_floor: int = 0, dry_run: bool = True)` :734
- **prune_by_priority** (f) `(max_priority: int = -1, dry_run: bool = True)` :780
- **strengthen** (f) `(memory_id: str, factor: float = 1.5)` :819
- **weaken** (f) `(memory_id: str, factor: float = 0.5)` :824

### state.py
> Imports: `threading, os, pathlib`
- **get_session_id** (f) `()` :40
- **set_session_id** (f) `(session_id: str)` :56

### turso.py
> Imports: `requests, json, os, time, pathlib`...
- *No top-level symbols*

### utilities.py
> Imports: `os, sys`
- **install_utilities** (f) `()` :8

