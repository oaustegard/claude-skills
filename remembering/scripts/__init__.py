"""Remembering - Minimal persistent memory for Claude.

v5.0.0: Removed local SQLite cache. All operations go through Turso FTS5.
"""

import requests
import json
import uuid
import threading
import os
import time
from datetime import datetime, UTC

# Import module state and constants
from . import state
from .state import TYPES, get_session_id, set_session_id

# Import Turso HTTP layer
from .turso import (
    _init, _retry_with_backoff,
    _exec, _exec_batch, _parse_memory_row,
    _fts5_search  # v4.5.0: Server-side FTS5 search (#298)
)

# Import memory layer
from .memory import (
    _write_memory, remember, remember_bg, flush,
    recall, _update_access_tracking, _query,
    recall_since, recall_between,
    forget, supersede, reprioritize,
    strengthen, weaken,
    memory_histogram, prune_by_age, prune_by_priority,  # v3.2.0: retention helpers
    get_alternatives, consolidate,  # v4.2.0: decision alternatives (#254) and consolidation (#253)
    get_chain,  # v4.3.0: reference chain traversal (#283)
    recall_batch, remember_batch  # v4.5.0: batch APIs (#299)
)

# Import result types (v3.4.0: type-safe memory results, v3.7.0: normalization)
from .result import (
    MemoryResult, MemoryResultList,
    VALID_FIELDS, COMMON_MISTAKES,
    wrap_results, _normalize_memory
)

# Import hints layer (v3.4.0: proactive memory surfacing)
from .hints import recall_hints

# Import config layer
from .config import (
    config_get, config_set, config_delete,
    config_set_boot_load, config_set_priority,  # v3.6.0: priority management
    config_list
)

# Import boot layer
from .boot import (
    profile, ops, boot,
    detect_github_access,  # v3.5.0: GitHub access detection
    github_api,  # v3.8.0: Unified GitHub API interface (#240)
    journal, journal_recent, journal_prune,
    therapy_scope, therapy_session_count, therapy_reflect, decisions_recent,
    group_by_type, group_by_tag,
    handoff_pending, handoff_complete,
    muninn_export, muninn_import,
    session_save, session_resume, sessions  # v4.3.0: session continuity (#231)
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
    "config_get", "config_set", "config_delete", "config_list", "config_set_boot_load", "config_set_priority",  # config
    "profile", "ops", "boot", "journal", "journal_recent", "journal_prune",  # boot & journal
    "detect_github_access",  # v3.5.0: GitHub access detection
    "github_api",  # v3.8.0: Unified GitHub API interface (#240)
    "therapy_scope", "therapy_session_count", "therapy_reflect", "decisions_recent",  # therapy helpers
    "group_by_type", "group_by_tag",  # analysis helpers
    "handoff_pending", "handoff_complete",  # handoff workflow
    "muninn_export", "muninn_import",  # export/import
    "reprioritize",  # priority adjustment
    "strengthen", "weaken",  # memory consolidation (v3.3.0)
    "install_utilities", "UTIL_DIR",  # utilities
    "get_alternatives", "consolidate",  # v4.2.0: decision alternatives (#254) and consolidation (#253)
    "get_chain",  # v4.3.0: reference chain traversal (#283)
    "recall_batch", "remember_batch",  # v4.5.0: batch APIs (#299)
    "get_session_id", "set_session_id",  # session management (v3.2.0)
    "session_save", "session_resume", "sessions",  # v4.3.0: session continuity (#231)
    "memory_histogram", "prune_by_age", "prune_by_priority",  # retention helpers (v3.2.0)
    # v3.4.0: Type-safe results and proactive hints
    "MemoryResult", "MemoryResultList", "VALID_FIELDS", "recall_hints",
    "_exec",  # v3.9.0: Raw SQL execution for utilities
    "r", "q", "j", "TYPES"  # aliases & constants
]
