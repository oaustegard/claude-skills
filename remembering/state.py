"""
Shared module state and constants for remembering skill.

This module contains:
- Module globals (database connection, credentials, pending writes)
- Constants (valid types, cache paths)
- Zero imports from other remembering modules (prevents circular dependencies)
"""

import threading
import os
from pathlib import Path

# Default Turso database URL
_DEFAULT_URL = "https://assistant-memory-oaustegard.aws-us-east-1.turso.io"

# Module globals - initialized by turso._init()
_URL = None
_TOKEN = None
_HEADERS = None

# Valid memory types (profile now lives in config table)
TYPES = {"decision", "world", "anomaly", "experience", "interaction"}

# Track pending background writes for flush()
_pending_writes = []
_pending_writes_lock = threading.Lock()

# Local SQLite cache configuration
_CACHE_DIR = Path.home() / ".muninn"
_CACHE_DB = _CACHE_DIR / "cache.db"
_cache_conn = None
_cache_enabled = True  # Can be disabled for testing
_cache_warmed = False  # Track if background warming completed

# Session tracking (v3.2.0)
_session_id = None  # Lazy-initialized from env or default


def get_session_id() -> str:
    """Get current session ID from environment variable or default.

    Priority:
    1. MUNINN_SESSION_ID environment variable
    2. Fallback to 'default-session'

    Returns:
        Session ID string
    """
    global _session_id
    if _session_id is None:
        _session_id = os.environ.get('MUNINN_SESSION_ID', 'default-session')
    return _session_id


def set_session_id(session_id: str) -> None:
    """Manually set session ID for current process.

    Args:
        session_id: Session identifier string
    """
    global _session_id
    _session_id = session_id
