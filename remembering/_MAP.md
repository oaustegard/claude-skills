# remembering/
*Files: 8 | Subdirectories: 1*

## Subdirectories

- [tests/](./tests/_MAP.md)

## Files

### __init__.py
> Imports: `requests, json, uuid, threading, os`...
- *No top-level symbols*

### boot.py
> Imports: `json, threading, datetime, ., .turso`...
- **profile** (f) `()`
- **ops** (f) `(include_reference: bool = False)`
- **boot** (f) `()`
- **journal** (f) `(topics: list = None, user_stated: str = None, my_intent: str = None)`
- **journal_recent** (f) `(n: int = 10)`
- **journal_prune** (f) `(keep: int = 40)`
- **therapy_scope** (f) `()`
- **therapy_session_count** (f) `()`
- **decisions_recent** (f) `(n: int = 10, conf: float = 0.7)`
- **group_by_type** (f) `(memories: list)`
- **group_by_tag** (f) `(memories: list)`
- **muninn_export** (f) `()`
- **handoff_pending** (f) `()`
- **handoff_complete** (f) `(handoff_id: str, completion_notes: str, version: str = None)`
- **muninn_import** (f) `(data: dict, *, merge: bool = False)`

### bootstrap.py
> Imports: `sys, os`
- **create_tables** (f) `()`
- **migrate_schema** (f) `()`
- **seed_config** (f) `()`
- **verify** (f) `()`
- **migrate_v2** (f) `(dry_run: bool = True)`
- **migrate_config_v2** (f) `(dry_run: bool = True)`

### cache.py
> Imports: `sqlite3, json, uuid, datetime, .`...
- **cache_stats** (f) `()`

### config.py
> Imports: `datetime, ., .turso, .cache`
- **config_get** (f) `(key: str)`
- **config_set** (f) `(key: str, value: str, category: str, *,
               char_limit: int = None, read_only: bool = False)`
- **config_delete** (f) `(key: str)`
- **config_set_boot_load** (f) `(key: str, boot_load: bool)`
- **config_list** (f) `(category: str = None)`

### memory.py
> Imports: `json, uuid, threading, time, datetime`...
- **remember** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
             refs: list = None, priority: int = 0, valid_from: str = None,
             sync: bool = True,
             # Deprecated parameters (ignored in v2.0.0, kept for backward compat)
             entities: list = None, importance: float = None, memory_class: str = None)`
- **remember_bg** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None,
                importance: float = None, memory_class: str = None, valid_from: str = None)`
- **flush** (f) `(timeout: float = 5.0)`
- **recall** (f) `(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any",
           use_cache: bool = True, strict: bool = False)`
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any")`
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any")`
- **forget** (f) `(memory_id: str)`
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)`
- **reprioritize** (f) `(memory_id: str, priority: int)`
- **strengthen** (f) `(memory_id: str, factor: float = 1.5)`
- **weaken** (f) `(memory_id: str, factor: float = 0.5)`

### state.py
> Imports: `threading, pathlib`
- *No top-level symbols*

### turso.py
> Imports: `requests, json, os, time, pathlib`...
- *No top-level symbols*

