"""
Boot, journal, therapy, handoff, and export/import operations for remembering skill.

This module handles:
- Boot sequence (boot, profile, ops, _warm_cache)
- Journal operations (journal, journal_recent, journal_prune)
- Therapy helpers (therapy_scope, therapy_session_count, decisions_recent)
- Analysis helpers (group_by_type, group_by_tag)
- Handoff workflow (handoff_pending, handoff_complete)
- Export/Import (muninn_export, muninn_import)

Imports from: state, turso, cache, memory, config
"""

import json
import threading
from datetime import datetime, UTC

from . import state
from .turso import _exec, _exec_batch
from .cache import _init_local_cache, _cache_available, _cache_config, _cache_populate_index, _cache_populate_full
from .memory import recall, recall_since, remember, supersede
from .config import config_list, config_set, config_delete


def profile() -> list:
    """Load profile config for conversation start."""
    return config_list("profile")


def ops(include_reference: bool = False) -> list:
    """Load operational config for conversation start.

    Args:
        include_reference: If True, include reference-only entries.
                          If False (default), only return entries marked for boot loading.

    Returns:
        List of config dicts with ops entries
    """
    entries = config_list("ops")

    # Filter by boot_load unless include_reference=True
    # Note: Turso returns boot_load as string ('0' or '1')
    if not include_reference:
        entries = [e for e in entries if e.get('boot_load', 1) in (1, '1')]

    return entries


def _warm_cache():
    """Background cache population - fetches all memories from Turso.

    v2.0.0: Uses priority instead of importance.
    v2.0.1: Sets state._cache_warmed flag when complete to fix race condition.
    """
    try:
        results = _exec_batch([
            """SELECT * FROM memories
               WHERE deleted_at IS NULL
               ORDER BY t DESC LIMIT 500"""
        ])
        full_memories = results[0]

        if _cache_available():
            memory_index = []
            for m in full_memories:
                memory_index.append({
                    'id': m.get('id'),
                    'type': m.get('type'),
                    't': m.get('t'),
                    'tags': m.get('tags'),
                    'summary_preview': m.get('summary', '')[:100],
                    'confidence': m.get('confidence'),
                    'priority': m.get('priority', 0)
                })
            _cache_populate_index(memory_index)
            _cache_populate_full(full_memories)
            state._cache_warmed = True  # Mark as complete
    except Exception:
        pass  # Cache warming is best-effort


def boot() -> str:
    """Boot sequence: load profile + ops, start async cache population.

    Returns formatted string with complete profile and ops values.
    Spawns background thread to populate memory cache for fast recall().

    Filters reference-only ops from output to reduce token usage at boot.
    Reference material (API docs, container limits, etc.) can be queried via config_get().

    Organizes ops by topic for better cognitive navigation.

    Resilience: Retries transient errors (SSL, 503, 429) with exponential backoff.
    Falls back to cached config if remote fetch fails after retries.
    """
    # Initialize cache
    _init_local_cache()

    # Fetch profile + ops with retry logic for transient errors
    try:
        from .turso import _retry_with_backoff

        def _fetch_config():
            return _exec_batch([
                "SELECT * FROM config WHERE category = 'profile' ORDER BY key",
                "SELECT * FROM config WHERE category = 'ops' ORDER BY key",
            ])

        results = _retry_with_backoff(_fetch_config, max_retries=3, base_delay=1.0)
        profile_data = results[0]
        ops_data = results[1]

        # Cache config immediately (cache ALL config, even reference material)
        if _cache_available():
            _cache_config(profile_data + ops_data)

    except Exception as e:
        # Fallback to cached config if remote fetch fails
        print(f"Warning: Remote config fetch failed, using cached data: {e}")
        if _cache_available():
            # Read directly from cache, not remote
            profile_data = state._cache_conn.execute(
                "SELECT * FROM config_cache WHERE category = 'profile' ORDER BY key"
            ).fetchall()
            profile_data = [dict(row) for row in profile_data]

            ops_data = state._cache_conn.execute(
                "SELECT * FROM config_cache WHERE category = 'ops' ORDER BY key"
            ).fetchall()
            ops_data = [dict(row) for row in ops_data]
        else:
            # No cache available and remote failed - return error message
            return f"ERROR: Unable to load config (remote failed: {e}, no cache available)"

    # Start async cache warming
    threading.Thread(target=_warm_cache, daemon=True).start()

    # Filter ops by boot_load flag (progressive disclosure)
    # Reference-only entries (boot_load=0) excluded from boot output but accessible via config_get()
    # Note: Turso returns boot_load as string ('0' or '1')
    core_ops = [o for o in ops_data if o.get('boot_load', 1) in (1, '1')]
    reference_ops = [o for o in ops_data if o.get('boot_load', 1) in (0, '0')]

    # Organize ops by topic for cognitive efficiency
    OPS_TOPICS = {
        'Core Boot & Behavior': [
            'boot-behavior', 'boot-output-hygiene', 'dev-workflow'
        ],
        'Memory Operations': [
            'remembering-api', 'memory-types', 'memory-backup',
            'storage-rules', 'storage-initiative', 'think-then-store',
            'recall-before-speculation'
        ],
        'Communication & Voice': [
            'communication-patterns', 'question-style', 'language-precision',
            'anti-psychogenic-behavior', 'voice'
        ],
        'Handoff Workflow': [
            'handoff-pattern', 'handoff-discipline', 'self_improvement_handoffs'
        ],
        'Development & Technical': [
            'skill-workflow', 'python-path-setup', 'heredoc-for-multiline',
            'token-efficiency', 'token_conservation', 'error-handling',
            'batch-processing-drift', 'cache-testing-lesson'
        ],
        'Environment & Infrastructure': [
            'env-file-handling', 'muninn-env-loading', 'austegard-com-hosting'
        ],
        'Commands & Shortcuts': [
            'fly-command', 'rem-command'
        ],
        'Therapy & Self-Improvement': [
            'therapy'
        ]
    }

    # Build reverse lookup for quick topic assignment
    key_to_topic = {}
    for topic, keys in OPS_TOPICS.items():
        for key in keys:
            key_to_topic[key] = topic

    # Group ops by topic
    ops_by_topic = {}
    uncategorized = []

    for o in core_ops:
        key = o['key']
        topic = key_to_topic.get(key)
        if topic:
            if topic not in ops_by_topic:
                ops_by_topic[topic] = []
            ops_by_topic[topic].append(o)
        else:
            uncategorized.append(o)

    # Format output
    output = []
    if profile_data:
        output.append("=== PROFILE ===")
        for p in profile_data:
            output.append(f"{p['key']}:\n{p['value']}")

    if core_ops:
        output.append("\n=== OPS ===")

        # Output ops by topic in defined order
        for topic in OPS_TOPICS.keys():
            if topic in ops_by_topic:
                output.append(f"\n## {topic}")
                for o in ops_by_topic[topic]:
                    output.append(f"{o['key']}:\n{o['value']}")

        # Output uncategorized ops last (alphabetically)
        if uncategorized:
            output.append("\n## Other")
            for o in sorted(uncategorized, key=lambda x: x['key']):
                output.append(f"{o['key']}:\n{o['value']}")

        # Reference index: show what's available but not loaded
        if reference_ops:
            output.append("\n## Reference Entries (load via config_get)")
            ref_keys = sorted([o['key'] for o in reference_ops])
            output.append(", ".join(ref_keys))

    return '\n'.join(output)


def journal(topics: list = None, user_stated: str = None, my_intent: str = None) -> str:
    """Record a journal entry. Returns the entry key."""
    now = datetime.now(UTC)
    # Use microsecond precision to prevent key collisions from rapid successive calls
    key = f"j-{now.strftime('%Y%m%d-%H%M%S%f')}"
    entry = {
        "t": now.isoformat().replace("+00:00", "Z"),
        "topics": topics or [],
        "user_stated": user_stated,
        "my_intent": my_intent
    }
    # Remove None values for cleaner storage
    entry = {k: v for k, v in entry.items() if v is not None}
    config_set(key, json.dumps(entry), "journal")
    return key


def journal_recent(n: int = 10) -> list:
    """Get recent journal entries for boot context. Returns list of parsed entries."""
    entries = config_list("journal")
    # Sort by key (timestamp-based) descending, take last n
    entries.sort(key=lambda x: x["key"], reverse=True)
    result = []
    for e in entries[:n]:
        try:
            parsed = json.loads(e["value"])
            parsed["_key"] = e["key"]
            result.append(parsed)
        except json.JSONDecodeError:
            continue
    return result


def journal_prune(keep: int = 40) -> int:
    """Prune old journal entries, keeping the most recent `keep` entries. Returns count deleted."""
    entries = config_list("journal")
    if len(entries) <= keep:
        return 0
    entries.sort(key=lambda x: x["key"], reverse=True)
    to_delete = entries[keep:]
    for e in to_delete:
        config_delete(e["key"])
    return len(to_delete)


# --- Therapy session helpers ---

def therapy_scope() -> tuple[str | None, list]:
    """Get cutoff timestamp and unprocessed memories for therapy session.

    Returns:
        Tuple of (cutoff_timestamp, memories_list)
        - cutoff_timestamp: Latest therapy session timestamp, or None if no sessions exist
        - memories_list: Memories since last therapy session (or all if no sessions)
    """
    # v0.12.1: Use strict=True to get newest session by timestamp, not by relevance ranking
    sessions = recall(type="experience", tags=["therapy"], n=1, strict=True)
    cutoff = sessions[0]['t'] if sessions else None
    memories = recall_since(cutoff, n=100) if cutoff else recall(n=100)
    return cutoff, memories


def therapy_session_count() -> int:
    """Count existing therapy sessions.

    Returns:
        Number of therapy session memories found
    """
    return len(recall(search="Therapy Session", type="experience", tags=["therapy"], n=100))


def decisions_recent(n: int = 10, conf: float = 0.7) -> list:
    """Return recent decisions above confidence threshold for boot loading.

    Args:
        n: Maximum number of decisions to return (default 10)
        conf: Minimum confidence threshold (default 0.7)

    Returns:
        List of decision memories sorted by timestamp (newest first)
    """
    return recall(type="decision", conf=conf, n=n)


# --- Analysis helpers ---

def group_by_type(memories: list) -> dict:
    """Group memories by type.

    Args:
        memories: List of memory dicts from recall()

    Returns:
        Dict mapping type -> list of memories: {type: [memories]}
    """
    by_type = {}
    for m in memories:
        t = m.get('type', 'unknown')
        by_type.setdefault(t, []).append(m)
    return by_type


def group_by_tag(memories: list) -> dict:
    """Group memories by tags.

    Args:
        memories: List of memory dicts from recall()

    Returns:
        Dict mapping tag -> list of memories: {tag: [memories]}
        Note: A memory with multiple tags will appear under each tag
    """
    by_tag = {}
    for m in memories:
        tags = json.loads(m.get('tags', '[]')) if isinstance(m.get('tags'), str) else m.get('tags', [])
        for tag in tags:
            by_tag.setdefault(tag, []).append(m)
    return by_tag


# --- Export/Import for portability ---

def muninn_export() -> dict:
    """Export all Muninn state as portable JSON.

    Returns:
        Dict with version, timestamp, config, and memories
    """
    return {
        "version": "1.0",
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "config": config_list(),
        "memories": _exec("SELECT * FROM memories WHERE deleted_at IS NULL")
    }


def handoff_pending() -> list:
    """Get pending handoff instructions (not yet completed).

    Returns handoffs tagged with BOTH 'handoff' AND 'pending', excluding superseded ones.
    Use handoff_complete() to mark a handoff as done.

    Returns:
        List of pending handoff memories, most recent first
    """
    return recall(tags=["handoff", "pending"], tag_mode="all", n=50)


def handoff_complete(handoff_id: str, completion_notes: str, version: str = None) -> str:
    """Mark a handoff as completed by superseding it with completion record.

    The original handoff will be excluded from future handoff_pending() queries.
    Completion record is tagged with version for historical tracking.

    Args:
        handoff_id: ID of the handoff to mark complete
        completion_notes: Summary of what was done
        version: Optional version number (e.g., "0.5.0")

    Returns:
        ID of the completion record

    Example:
        handoff_id = handoff_pending()[0]['id']
        handoff_complete(handoff_id, "Implemented boot() function", "0.5.0")
    """
    # Read VERSION file if version not provided
    if version is None:
        try:
            from pathlib import Path
            version_file = Path(__file__).parent / "VERSION"
            version = version_file.read_text().strip()
        except Exception:
            version = "unknown"

    # Supersede the handoff with completion record
    completion_tags = ["handoff-completed", f"v{version}"]
    return supersede(handoff_id, completion_notes, "world", tags=completion_tags)


def muninn_import(data: dict, *, merge: bool = False) -> dict:
    """Import Muninn state from exported JSON.

    Args:
        data: Dict from muninn_export()
        merge: If True, add to existing data. If False, replace all (destructive!)

    Returns:
        Stats dict with counts of imported items

    Raises:
        ValueError: If data format invalid
    """
    if not isinstance(data, dict) or "version" not in data:
        raise ValueError("Invalid import data: missing version field")

    stats = {"config_count": 0, "memory_count": 0, "errors": []}

    if not merge:
        # Destructive: clear all existing data
        _exec("DELETE FROM config")
        _exec("DELETE FROM memories")

    # Import config entries
    for c in data.get("config", []):
        try:
            config_set(
                c["key"],
                c["value"],
                c["category"],
                char_limit=c.get("char_limit"),
                read_only=bool(c.get("read_only", False))
            )
            stats["config_count"] += 1
        except Exception as e:
            stats["errors"].append(f"Config {c.get('key')}: {e}")

    # Import memories (regenerate IDs to avoid conflicts in merge mode)
    for m in data.get("memories", []):
        try:
            # Parse JSON fields
            tags = json.loads(m.get("tags", "[]")) if isinstance(m.get("tags"), str) else m.get("tags", [])
            entities = json.loads(m.get("entities", "[]")) if isinstance(m.get("entities"), str) else m.get("entities", [])
            refs = json.loads(m.get("refs", "[]")) if isinstance(m.get("refs"), str) else m.get("refs", [])

            # v0.13.0: Embeddings no longer supported
            remember(
                m["summary"],
                m["type"],
                tags=tags,
                conf=m.get("confidence"),
                entities=entities,
                refs=refs
            )
            stats["memory_count"] += 1
        except Exception as e:
            stats["errors"].append(f"Memory {m.get('id', 'unknown')}: {e}")

    return stats
