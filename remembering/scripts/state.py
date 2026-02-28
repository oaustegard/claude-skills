"""
Shared module state and constants for remembering skill.

This module contains:
- Module globals (database credentials, pending writes)
- Constants (valid types)
- Zero imports from other remembering modules (prevents circular dependencies)

v5.0.0: Removed local cache globals. All storage is Turso-only.
"""

import threading
import os

# Default Turso database URL (hostname without protocol)
_DEFAULT_URL_HOST = "assistant-memory-oaustegard.aws-us-east-1.turso.io"
_DEFAULT_URL = f"https://{_DEFAULT_URL_HOST}"

# Module globals - initialized by turso._init()
_URL = None
_TOKEN = None
_HEADERS = None

# Valid memory types (profile now lives in config table)
TYPES = {"decision", "world", "anomaly", "experience", "interaction", "procedure", "analysis"}

# Track pending background writes for flush()
_pending_writes = []
_pending_writes_lock = threading.Lock()

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
