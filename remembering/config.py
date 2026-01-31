"""
Config CRUD operations for remembering skill.

This module handles:
- Config get/set/delete operations
- Boot load flag management
- Config listing with category filtering

Imports from: state, turso, cache
"""

from datetime import datetime, UTC

from . import state
from .turso import _exec
from .cache import _cache_available


def config_get(key: str) -> str | None:
    """Get a config value by key."""
    result = _exec("SELECT value FROM config WHERE key = ?", [key])
    return result[0]["value"] if result else None


def config_set(key: str, value: str, category: str, *,
               char_limit: int = None, read_only: bool = False) -> None:
    """Set a config value with optional constraints.

    Args:
        key: Config key
        value: Config value
        category: Must be 'profile', 'ops', or 'journal'
        char_limit: Optional character limit for value (enforced on writes)
        read_only: Mark as read-only (advisory - not enforced by this function)

    Raises:
        ValueError: If category invalid or value exceeds char_limit
    """
    if category not in ("profile", "ops", "journal"):
        raise ValueError(f"Invalid category '{category}'. Must be 'profile', 'ops', or 'journal'")

    # Check existing entry for read_only flag
    # Note: Turso returns boolean fields as strings ('0' or '1'), so we need explicit checks
    existing = _exec("SELECT read_only FROM config WHERE key = ?", [key])
    if existing:
        is_readonly = existing[0].get("read_only")
        # Check for truthy values that indicate read-only (handle both int and string types)
        if is_readonly not in (None, 0, '0', False, 'false', 'False'):
            raise ValueError(f"Config key '{key}' is marked read-only and cannot be modified")

    # Enforce character limit if specified
    if char_limit and len(value) > char_limit:
        raise ValueError(
            f"Value exceeds char_limit ({len(value)} > {char_limit}). "
            f"Current value length: {len(value)}, limit: {char_limit}"
        )

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _exec(
        """INSERT OR REPLACE INTO config (key, value, category, updated_at, char_limit, read_only)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [key, value, category, now, char_limit, 1 if read_only else 0]
    )


def config_delete(key: str) -> bool:
    """Delete a config entry."""
    _exec("DELETE FROM config WHERE key = ?", [key])
    return True


def config_set_boot_load(key: str, boot_load: bool) -> bool:
    """Set whether a config entry loads at boot or is reference-only.

    Args:
        key: Config key to update
        boot_load: True to load at boot, False for reference-only

    Returns:
        True if successful

    Example:
        config_set_boot_load('github-api-endpoints', False)  # Make reference-only
        config_set_boot_load('storage-discipline', True)      # Load at boot
    """
    val = 1 if boot_load else 0

    # Update remote
    _exec("UPDATE config SET boot_load = ? WHERE key = ?", [val, key])

    # Update local cache if available
    if _cache_available():
        state._cache_conn.execute("UPDATE config_cache SET boot_load = ? WHERE key = ?", (val, key))
        state._cache_conn.commit()

    return True


def config_set_priority(key: str, priority: int) -> bool:
    """Set the priority of a config entry for ordering within categories.

    Higher priority entries appear first in boot output within their topic.

    Args:
        key: Config key to update
        priority: Priority level (higher = more important, default is 0)
                  Suggested scale: 0=normal, 1-9=elevated, 10+=critical

    Returns:
        True if successful

    Example:
        config_set_priority('storage-rules', 10)  # Critical - show first
        config_set_priority('fly-command', 0)     # Normal priority
    """
    # Update remote
    _exec("UPDATE config SET priority = ? WHERE key = ?", [priority, key])

    # Update local cache if available
    if _cache_available():
        state._cache_conn.execute("UPDATE config_cache SET priority = ? WHERE key = ?", (priority, key))
        state._cache_conn.commit()

    return True


def config_list(category: str = None) -> list:
    """List config entries, optionally filtered by category."""
    if category:
        return _exec("SELECT * FROM config WHERE category = ? ORDER BY key", [category])
    return _exec("SELECT * FROM config ORDER BY category, key")
