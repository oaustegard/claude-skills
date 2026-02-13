# scripts/
*Files: 11 | Subdirectories: 1*

## Subdirectories

- [defaults/](./defaults/_MAP.md)

## Files

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
             alternatives: list = None,
             # Deprecated parameters (ignored in v2.0.0, kept for backward compat)
             entities: list = None, importance: float = None, memory_class: str = None)` :70
- **remember_bg** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None,
                importance: float = None, memory_class: str = None, valid_from: str = None)` :187
- **flush** (f) `(timeout: float = 5.0)` :204
- **recall** (f) `(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any",
           use_cache: bool = True, strict: bool = False, session_id: str = None,
           auto_strengthen: bool = False, raw: bool = False,
           expansion_threshold: int = 3,
           limit: int = None, fetch_all: bool = False)` :236
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any",
                 session_id: str = None, raw: bool = False)` :537
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None, raw: bool = False)` :604
- **forget** (f) `(memory_id: str)` :673
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)` :691
- **reprioritize** (f) `(memory_id: str, priority: int)` :759
- **memory_histogram** (f) `()` :800
- **prune_by_age** (f) `(older_than_days: int, priority_floor: int = 0, dry_run: bool = True)` :856
- **prune_by_priority** (f) `(max_priority: int = -1, dry_run: bool = True)` :902
- **strengthen** (f) `(memory_id: str, boost: int = 1)` :941
- **weaken** (f) `(memory_id: str, drop: int = 1)` :981
- **get_alternatives** (f) `(memory_id: str)` :1015
- **consolidate** (f) `(*, tags: list = None, min_cluster: int = 3, dry_run: bool = True,
                session_id: str = None)` :1056

### result.py
> Imports: `typing`
- **MemoryResult** (C) :80
  - **__init__** (m) `(self, data: dict)` :99
  - **__getattr__** (m) `(self, name: str)` :103
  - **__setattr__** (m) `(self, name: str, value: Any)` :121
  - **__getitem__** (m) `(self, key: str)` :128
  - **__contains__** (m) `(self, key: str)` :143
  - **__iter__** (m) `(self)` :147
  - **__len__** (m) `(self)` :151
  - **__repr__** (m) `(self)` :155
  - **__str__** (m) `(self)` :162
  - **_error_message** (m) `(self, field: str, error_type: str)` :166
  - **get** (m) `(self, key: str, default: Any = None)` :180
  - **keys** (m) `(self)` :199
  - **values** (m) `(self)` :203
  - **items** (m) `(self)` :207
  - **to_dict** (m) `(self)` :211
  - **copy** (m) `(self)` :220
- **MemoryResultList** (C) :225
  - **__repr__** (m) `(self)` :232
  - **to_dicts** (m) `(self)` :237
- **wrap_results** (f) `(results: List[dict])` :276

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

