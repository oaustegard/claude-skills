"""
Shared module state and constants for remembering skill.

This module contains:
- Module globals (database connection, credentials, pending writes)
- Constants (valid types, cache paths)
- Zero imports from other remembering modules (prevents circular dependencies)
"""

import threading
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
