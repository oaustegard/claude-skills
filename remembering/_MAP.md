# remembering/
*Files: 14 | Subdirectories: 1*

## Subdirectories

- [tests/](./tests/_MAP.md)

## Files

### CHANGELOG.md
- Muninn Memory System - Changelog `h1` :1
- [3.2.1] - 2026-01-21 `h2` :5
- [3.2.0] - 2026-01-16 `h2` :9
- [3.2.0] - 2026-01-16 `h2` :15
- [3.1.0] - 2026-01-16 `h2` :44
- [3.0.0] - 2026-01-16 `h2` :50
- [3.0.0] - 2026-01-16 `h2` :68
- [2.2.1] - 2026-01-09 `h2` :90
- [2.1.1] - 2026-01-09 `h2` :110
- [2.1.0] - 2026-01-09 `h2` :120
- [2.0.2] - 2026-01-09 `h2` :126
- [2.0.1] - 2026-01-09 `h2` :132
- [1.0.1] - 2026-01-09 `h2` :143
- [2.0.0] - 2026-01-09 `h2` :153
- [0.14.1] - 2026-01-06 `h2` :159
- [0.14.1] - 2026-01-06 `h2` :165
- [0.14.0] - 2026-01-04 `h2` :172
- [0.13.1] - 2026-01-02 `h2` :178
- [0.13.0] - 2025-12-30 `h2` :195
- [0.12.2] - 2025-12-30 `h2` :207
- [0.12.1] - 2025-12-30 `h2` :211
- [0.12.0] - 2025-12-30 `h2` :244
- [0.11.0] - 2025-12-30 `h2` :283
- [0.10.1] - 2025-12-29 `h2` :315
- [0.10.0] - 2025-12-28 `h2` :354
- [0.9.1] - 2025-12-28 `h2` :407
- [0.9.0] - 2025-12-28 `h2` :426
- [0.8.0] - 2025-12-27 `h2` :475
- [0.7.1] - 2025-12-27 `h2` :509
- [0.7.0] - 2025-12-27 `h2` :536
- [0.6.1] - 2025-12-27 `h2` :581
- [0.6.0] - 2025-12-27 `h2` :605
- [0.4.0] - 2025-12-27 `h2` :641
- [0.3.1] - 2025-12-26 `h2` :660
- [0.3.0] - 2025-12-26 `h2` :667
- [0.1.0] - 2025-12-26 `h2` :676
- Summary `h2` :687

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
- Lessons for Claude Code Agents `h2` :277
- What's New in v3.2.0 `h2` :335
- Known Limitations `h2` :352

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
- Edge Cases `h2` :618
- Implementation Notes `h2` :638

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
- **migrate_schema** (f) `()` :64
- **seed_config** (f) `()` :150
- **verify** (f) `()` :196
- **migrate_v2** (f) `(dry_run: bool = True)` :212
- **migrate_config_v2** (f) `(dry_run: bool = True)` :383

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
           use_cache: bool = True, strict: bool = False, session_id: str = None,
           auto_strengthen: bool = False)` :218
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any", session_id: str = None)` :480
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None)` :541
- **forget** (f) `(memory_id: str)` :605
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)` :623
- **reprioritize** (f) `(memory_id: str, priority: int)` :691
- **memory_histogram** (f) `()` :732
- **prune_by_age** (f) `(older_than_days: int, priority_floor: int = 0, dry_run: bool = True)` :788
- **prune_by_priority** (f) `(max_priority: int = -1, dry_run: bool = True)` :834
- **strengthen** (f) `(memory_id: str, boost: int = 1)` :873
- **weaken** (f) `(memory_id: str, drop: int = 1)` :913

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

