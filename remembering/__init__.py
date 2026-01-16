"""Remembering - Minimal persistent memory for Claude."""

import requests
import json
import uuid
import threading
import os
import time
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

# Import module state and constants
from . import state
from .state import TYPES, get_session_id, set_session_id

# Import Turso HTTP layer
from .turso import (
    _load_env_file, _init, _retry_with_backoff,
    _exec, _exec_batch, _parse_memory_row
)

# Import cache layer
from .cache import (
    _init_local_cache, _cache_available, _cache_clear,
    _cache_populate_index, _cache_populate_full, _cache_config,
    _cache_query_index, _escape_fts5_query, _cache_row_to_dict,
    _cache_memory, _fetch_full_content, cache_stats,
    _log_recall_query,
    recall_stats, top_queries  # v3.2.0: observability
)

# Import memory layer
from .memory import (
    _write_memory, remember, remember_bg, flush,
    recall, _update_access_tracking, _query,
    recall_since, recall_between,
    forget, supersede, reprioritize,
    strengthen, weaken,
    memory_histogram, prune_by_age, prune_by_priority  # v3.2.0: retention helpers
)

# Import config layer
from .config import (
    config_get, config_set, config_delete,
    config_set_boot_load, config_list
)

# Import boot layer
from .boot import (
    profile, ops, _warm_cache, boot,
    journal, journal_recent, journal_prune,
    therapy_scope, therapy_session_count, decisions_recent,
    group_by_type, group_by_tag,
    handoff_pending, handoff_complete,
    muninn_export, muninn_import
)

# Import utilities layer
from .utilities import install_utilities, UTIL_DIR

# Short aliases
r = remember
q = recall
j = journal

__all__ = [
    "remember", "recall", "forget", "supersede", "remember_bg", "flush",  # memories
    "recall_since", "recall_between",  # date-filtered queries
    "config_get", "config_set", "config_delete", "config_list", "config_set_boot_load",  # config
    "profile", "ops", "boot", "journal", "journal_recent", "journal_prune",  # boot & journal
    "therapy_scope", "therapy_session_count", "decisions_recent",  # therapy helpers
    "group_by_type", "group_by_tag",  # analysis helpers
    "handoff_pending", "handoff_complete",  # handoff workflow
    "muninn_export", "muninn_import",  # export/import
    "cache_stats",  # cache diagnostics
    "reprioritize",  # priority adjustment
    "strengthen", "weaken",  # deprecated (v2.0.0) - no-op, kept for compat
    "install_utilities", "UTIL_DIR",  # utilities
    "get_session_id", "set_session_id",  # session management (v3.2.0)
    "recall_stats", "top_queries",  # retrieval observability (v3.2.0)
    "memory_histogram", "prune_by_age", "prune_by_priority",  # retention helpers (v3.2.0)
    "r", "q", "j", "TYPES"  # aliases & constants
]
