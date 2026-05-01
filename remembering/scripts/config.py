"""
Config CRUD operations for remembering skill.

This module handles:
- Config get/set/delete operations
- Boot load flag management
- Config listing with category filtering

Imports from: turso

v5.0.0: Removed local cache dependency. All reads/writes go to Turso directly.
"""

from datetime import datetime, UTC

from .turso import _exec


# @lat: [[memory#Config System]]
def config_get(key: str) -> str | None:
    """Get a config value by key."""
    result = _exec("SELECT value FROM config WHERE key = ?", [key])
    return result[0]["value"] if result else None


# @lat: [[memory#Config System]]
def config_set(key: str, value: str, category: str, *,
               char_limit: int = None, read_only: bool = False,
               boot_load: bool = None) -> None:
    """Set a config value with optional constraints.

    Args:
        key: Config key
        value: Config value
        category: Must be 'profile', 'ops', or 'journal'
        char_limit: Optional character limit for value (enforced on writes)
        read_only: Mark as read-only (advisory - not enforced by this function)
        boot_load: Whether the entry loads at boot. If None (default), existing
            entries preserve their current boot_load and new entries default to
            True. Pass True/False to set explicitly.

    Raises:
        ValueError: If category invalid or value exceeds char_limit
    """
    if category not in ("profile", "ops", "journal"):
        raise ValueError(f"Invalid category '{category}'. Must be 'profile', 'ops', or 'journal'")

    # Check existing entry for read_only flag and current boot_load.
    # Note: Turso returns boolean fields as strings ('0' or '1'), so we need explicit checks
    existing = _exec("SELECT read_only, boot_load FROM config WHERE key = ?", [key])
    if existing:
        is_readonly = existing[0].get("read_only")
        # Check for truthy values that indicate read-only (handle both int and string types)
        if is_readonly not in (None, 0, '0', False, 'false', 'False'):
            raise ValueError(f"Config key '{key}' is marked read-only and cannot be modified")
        # Preserve existing boot_load on update unless caller explicitly specified one.
        # Without this, INSERT OR REPLACE would silently reset boot_load to the column
        # default (1), re-promoting reference-only entries to boot-loaded on every update.
        # This is critical for auto-maintained keys like 'recall-triggers' that are written
        # on every remember() call.
        if boot_load is None:
            existing_bl = existing[0].get("boot_load")
            boot_load_val = 0 if existing_bl in (0, '0', False, 'false', 'False') else 1
        else:
            boot_load_val = 1 if boot_load else 0
    else:
        # New entry: default to boot_load=1 (matches schema default), or use explicit value.
        boot_load_val = 1 if (boot_load is None or boot_load) else 0

    # Enforce character limit if specified
    if char_limit and len(value) > char_limit:
        raise ValueError(
            f"Value exceeds char_limit ({len(value)} > {char_limit}). "
            f"Current value length: {len(value)}, limit: {char_limit}"
        )

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _exec(
        """INSERT OR REPLACE INTO config (key, value, category, updated_at, char_limit, read_only, boot_load)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [key, value, category, now, char_limit, 1 if read_only else 0, boot_load_val]
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

    v5.0.0: Turso-only. Removed local cache update.
    """
    val = 1 if boot_load else 0
    _exec("UPDATE config SET boot_load = ? WHERE key = ?", [val, key])
    return True


def config_set_priority(key: str, priority: int) -> bool:
    """Set the priority of a config entry for ordering within categories.

    Higher priority entries appear first in boot output within their topic.

    Args:
        key: Config key to update
        priority: Priority level (higher = more important, default is 0)

    Returns:
        True if successful

    v5.0.0: Turso-only. Removed local cache update.
    """
    _exec("UPDATE config SET priority = ? WHERE key = ?", [priority, key])
    return True


def config_list(category: str = None) -> list:
    """List config entries, optionally filtered by category."""
    if category:
        return _exec("SELECT * FROM config WHERE category = ? ORDER BY key", [category])
    return _exec("SELECT * FROM config ORDER BY category, key")
