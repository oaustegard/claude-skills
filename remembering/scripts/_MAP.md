# scripts/
*Files: 10 | Subdirectories: 1*

## Subdirectories

- [defaults/](./defaults/_MAP.md)

## Files

### __init__.py
> Imports: `requests, json, uuid, threading, os`...
- *No top-level symbols*

### boot.py
> Imports: `json, os, shutil, subprocess, datetime`...
- **classify_ops_key** (f) `(key: str)` :133
- **detect_github_access** (f) `()` :153
- **github_api** (f) `(endpoint: str, *, method: str = "GET", body: dict = None,
               accept: str = "application/vnd.github+json")` :230
- **group_ops_by_topic** (f) `(ops_entries: list)` :313
- **profile** (f) `()` :364
- **ops** (f) `(include_reference: bool = False)` :369
- **boot** (f) `()` :435
- **journal** (f) `(topics: list = None, user_stated: str = None, my_intent: str = None)` :591
- **journal_recent** (f) `(n: int = 10)` :608
- **journal_prune** (f) `(keep: int = 40)` :624
- **therapy_scope** (f) `()` :638
- **therapy_session_count** (f) `()` :653
- **decisions_recent** (f) `(n: int = 10, conf: float = 0.7)` :662
- **therapy_reflect** (f) `(*, n_sample: int = 20, similarity_threshold: int = 3,
                     dry_run: bool = True)` :675
- **group_by_type** (f) `(memories: list)` :805
- **group_by_tag** (f) `(memories: list)` :821
- **muninn_export** (f) `()` :841
- **session_save** (f) `(summary: str = None, context: dict = None)` :858
- **session_resume** (f) `(session_id: str = None)` :908
- **sessions** (f) `(n: int = 10, *, include_counts: bool = False)` :980
- **handoff_pending** (f) `()` :1045
- **handoff_complete** (f) `(handoff_id: str, completion_notes: str, version: str = None)` :1060
- **muninn_import** (f) `(data: dict, *, merge: bool = False)` :1092

### bootstrap.py
> Imports: `sys, os, scripts`
- **create_tables** (f) `()` :17
- **migrate_schema** (f) `()` :65
- **seed_config** (f) `()` :127
- **verify** (f) `()` :173

### config.py
> Imports: `datetime, .turso`
- **config_get** (f) `(key: str)` :19
- **config_set** (f) `(key: str, value: str, category: str, *,
               char_limit: int = None, read_only: bool = False)` :25
- **config_delete** (f) `(key: str)` :66
- **config_set_boot_load** (f) `(key: str, boot_load: bool)` :72
- **config_set_priority** (f) `(key: str, priority: int)` :89
- **config_list** (f) `(category: str = None)` :107

### hints.py
> Imports: `re, json, typing, collections, .config`...
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
             entities: list = None, importance: float = None, memory_class: str = None)` :68
- **remember_bg** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None,
                importance: float = None, memory_class: str = None, valid_from: str = None)` :184
- **flush** (f) `(timeout: float = 5.0)` :201
- **recall** (f) `(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any",
           strict: bool = False, session_id: str = None,
           auto_strengthen: bool = False, raw: bool = False,
           expansion_threshold: int = 3,
           limit: int = None, fetch_all: bool = False,
           since: str = None, until: str = None,
           tags_all: list = None, tags_any: list = None,
           # Deprecated parameters (kept for backward compat)
           use_cache: bool = True)` :233
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any",
                 session_id: str = None, raw: bool = False)` :490
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None, raw: bool = False)` :557
- **forget** (f) `(memory_id: str)` :626
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)` :636
- **reprioritize** (f) `(memory_id: str, priority: int)` :685
- **memory_histogram** (f) `()` :707
- **prune_by_age** (f) `(older_than_days: int, priority_floor: int = 0, dry_run: bool = True)` :763
- **prune_by_priority** (f) `(max_priority: int = -1, dry_run: bool = True)` :809
- **strengthen** (f) `(memory_id: str, boost: int = 1)` :848
- **weaken** (f) `(memory_id: str, drop: int = 1)` :888
- **recall_batch** (f) `(queries: list, *, n: int = 10, type: str = None,
                 tags: list = None, tag_mode: str = "any",
                 conf: float = None, session_id: str = None,
                 raw: bool = False)` :922
- **remember_batch** (f) `(items: list, *, sync: bool = True)` :1050
- **get_alternatives** (f) `(memory_id: str)` :1192
- **get_chain** (f) `(memory_id: str, depth: int = 3)` :1231
- **consolidate** (f) `(*, tags: list = None, min_cluster: int = 3, dry_run: bool = True,
                session_id: str = None)` :1301

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
> Imports: `threading, os`
- **get_session_id** (f) `()` :35
- **set_session_id** (f) `(session_id: str)` :51

### turso.py
> Imports: `importlib, importlib.util, json, os, time`...
- *No top-level symbols*

### utilities.py
> Imports: `os, sys`
- **install_utilities** (f) `()` :8

