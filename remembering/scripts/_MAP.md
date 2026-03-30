# scripts/
*Files: 11 | Subdirectories: 2*

## Subdirectories

- [defaults/](./defaults/_MAP.md)
- [migrations/](./migrations/_MAP.md)

## Files

### __init__.py
> Imports: `requests, json, uuid, threading, os`...
- *No top-level symbols*

### boot.py
> Imports: `json, os, shutil, subprocess, datetime`...
- **classify_ops_key** (f) `(key: str)` :152
- **detect_github_access** (f) `()` :172
- **github_api** (f) `(endpoint: str, *, method: str = "GET", body: dict = None,
               accept: str = "application/vnd.github+json")` :249
- **group_ops_by_topic** (f) `(ops_entries: list)` :332
- **profile** (f) `()` :383
- **ops** (f) `(include_reference: bool = False)` :388
- **boot** (f) `(mode: str = None)` :463
- **journal** (f) `(topics: list = None, user_stated: str = None, my_intent: str = None)` :846
- **journal_recent** (f) `(n: int = 10)` :863
- **journal_prune** (f) `(keep: int = 40)` :879
- **therapy_scope** (f) `()` :894
- **therapy_session_count** (f) `()` :909
- **decisions_recent** (f) `(n: int = 10, conf: float = 0.7)` :918
- **therapy_reflect** (f) `(*, n_sample: int = 20, similarity_threshold: int = 3,
                     dry_run: bool = True)` :932
- **group_by_type** (f) `(memories: list)` :1062
- **group_by_tag** (f) `(memories: list)` :1078
- **muninn_export** (f) `()` :1098
- **session_save** (f) `(summary: str = None, context: dict = None)` :1116
- **session_resume** (f) `(session_id: str = None)` :1167
- **sessions** (f) `(n: int = 10, *, include_counts: bool = False)` :1239
- **handoff_pending** (f) `()` :1304
- **handoff_complete** (f) `(handoff_id: str, completion_notes: str, version: str = None)` :1319
- **muninn_import** (f) `(data: dict, *, merge: bool = False)` :1351

### bootstrap.py
> Imports: `sys, os, scripts`
- **create_tables** (f) `()` :18
- **migrate_schema** (f) `()` :80
- **seed_config** (f) `()` :159
- **verify** (f) `()` :205

### config.py
> Imports: `datetime, .turso`
- **config_get** (f) `(key: str)` :20
- **config_set** (f) `(key: str, value: str, category: str, *,
               char_limit: int = None, read_only: bool = False)` :27
- **config_delete** (f) `(key: str)` :68
- **config_set_boot_load** (f) `(key: str, boot_load: bool)` :74
- **config_set_priority** (f) `(key: str, priority: int)` :91
- **config_list** (f) `(category: str = None)` :109

### hints.py
> Imports: `re, json, typing, collections, .config`...
- **recall_hints** (f) `(context: str = None, *, terms: List[str] = None,
                 include_tags: bool = True, include_summaries: bool = True,
                 min_matches: int = 1)` :18

### memory.py
> Imports: `json, uuid, threading, time, atexit`...
- **remember** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
             refs: list = None, priority: int = 0, valid_from: str = None,
             sync: bool = True, session_id: str = None,
             alternatives: list = None,
             # Deprecated parameters (ignored in v2.0.0, kept for backward compat)
             entities: list = None, importance: float = None, memory_class: str = None)` :112
- **remember_bg** (f) `(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None,
                importance: float = None, memory_class: str = None, valid_from: str = None)` :238
- **flush** (f) `(timeout: float = 5.0)` :256
- **recall** (f) `(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any",
           strict: bool = False, session_id: str = None,
           auto_strengthen: bool = False, raw: bool = False,
           expansion_threshold: int = 3,
           limit: int = None, fetch_all: bool = False,
           since: str = None, until: str = None,
           tags_all: list = None, tags_any: list = None,
           episodic: bool = False,
           # Deprecated parameters (kept for backward compat)
           use_cache: bool = True)` :289
- **recall_since** (f) `(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any",
                 session_id: str = None, raw: bool = False)` :641
- **recall_between** (f) `(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None, raw: bool = False)` :713
- **forget** (f) `(memory_id: str)` :788
- **supersede** (f) `(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None)` :840
- **reprioritize** (f) `(memory_id: str, priority: int)` :893
- **memory_histogram** (f) `()` :917
- **prune_by_age** (f) `(older_than_days: int, priority_floor: int = 0, dry_run: bool = True)` :973
- **prune_by_priority** (f) `(max_priority: int = -1, dry_run: bool = True)` :1019
- **strengthen** (f) `(memory_id: str, boost: int = 1)` :1059
- **weaken** (f) `(memory_id: str, drop: int = 1)` :1103
- **recall_batch** (f) `(queries: list, *, n: int = 10, type: str = None,
                 tags: list = None, tag_mode: str = "any",
                 conf: float = None, session_id: str = None,
                 raw: bool = False)` :1141
- **remember_batch** (f) `(items: list, *, sync: bool = True)` :1271
- **get_alternatives** (f) `(memory_id: str)` :1413
- **get_chain** (f) `(memory_id: str, depth: int = 3)` :1452
- **consolidate** (f) `(*, tags: list = None, min_cluster: int = 3, dry_run: bool = True,
                session_id: str = None)` :1523
- **curate** (f) `(*, dry_run: bool = True, consolidation_threshold: int = 3,
           stale_days: int = 90, low_priority_cap: int = -1,
           max_actions: int = 20)` :1669
- **decision_trace** (f) `(choice: str, context: str, rationale: str, *,
                   alternatives: list = None, tradeoffs: str = None,
                   contraindications: str = None, tags: list = None,
                   refs: list = None, conf: float = 0.9,
                   priority: int = 1)` :1795

### result.py
> Imports: `datetime, typing, zoneinfo`
- **MemoryResult** (C) :83
  - **__init__** (m) `(self, data: dict)` :102
  - **__getattr__** (m) `(self, name: str)` :106
  - **__setattr__** (m) `(self, name: str, value: Any)` :124
  - **__getitem__** (m) `(self, key: str)` :131
  - **__contains__** (m) `(self, key: str)` :146
  - **__iter__** (m) `(self)` :150
  - **__len__** (m) `(self)` :154
  - **__repr__** (m) `(self)` :158
  - **__str__** (m) `(self)` :165
  - **_error_message** (m) `(self, field: str, error_type: str)` :169
  - **get** (m) `(self, key: str, default: Any = None)` :183
  - **keys** (m) `(self)` :202
  - **values** (m) `(self)` :206
  - **items** (m) `(self)` :210
  - **to_dict** (m) `(self)` :214
  - **copy** (m) `(self)` :223
- **MemoryResultList** (C) :228
  - **__repr__** (m) `(self)` :235
  - **to_dicts** (m) `(self)` :240
- **normalize_to_utc** (f) `(ts: str)` :326
- **wrap_results** (f) `(results: List[dict])` :349

### state.py
> Imports: `threading, os`
- **get_session_id** (f) `()` :35
- **set_session_id** (f) `(session_id: str)` :51

### task.py
> Imports: `json, sys, time, contextlib, datetime`
- **Task** (C) :89
  - **__init__** (m) `(self, name: str, steps=None, task_type: str = None,
                 require_store: bool = True, persist: bool = True)` :102
  - **done** (m) `(self, step: str)` :128
  - **pending** (m) `(self)` :137
  - **status** (m) `(self)` :141
  - **incomplete_prefix** (m) `(self, content: str)` :155
  - **complete** (m) `(self)` :164
- **task** (f) `(name: str, steps=None, task_type: str = None,
         require_store: bool = True, persist: bool = True)` :208
- **task_resume** (f) `(name: str)` :231
- **incomplete_tasks** (f) `()` :253

### turso.py
> Imports: `importlib, importlib.util, json, os, time`...
- *No top-level symbols*

### utilities.py
> Imports: `os, sys`
- **install_utilities** (f) `()` :9

