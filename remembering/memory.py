"""
Memory CRUD and query operations for remembering skill.

This module handles:
- Memory creation (remember, remember_bg)
- Memory querying (recall, recall_since, recall_between)
- Memory updates (supersede, reprioritize)
- Memory deletion (forget)
- Access tracking

Imports from: state, turso, cache, config
"""

import json
import uuid
import threading
import time
from datetime import datetime, UTC

from . import state
from .state import TYPES
from .turso import _exec
from .cache import (
    _cache_available, _cache_memory, _cache_query_index,
    _fetch_full_content, _cache_populate_full, _log_recall_query
)
# Import config_get and config_set for recall-triggers management
from .config import config_get, config_set


def _write_memory(mem_id: str, what: str, type: str, now: str, conf: float,
                  tags: list, refs: list, priority: int, valid_from: str) -> None:
    """Internal helper: write memory to Turso (blocking).

    v2.0.0: Simplified schema - removed entities, importance, salience, memory_class,
            session_id, embedding. Added priority field.
    """
    _exec(
        """INSERT INTO memories (id, type, t, summary, confidence, tags, refs, priority,
           created_at, updated_at, valid_from, access_count, last_accessed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)""",
        [mem_id, type, now, what, conf,
         json.dumps(tags or []), json.dumps(refs or []),
         priority, now, now, valid_from]
    )


def remember(what: str, type: str, *, tags: list = None, conf: float = None,
             refs: list = None, priority: int = 0, valid_from: str = None,
             sync: bool = True,
             # Deprecated parameters (ignored in v2.0.0, kept for backward compat)
             entities: list = None, importance: float = None, memory_class: str = None) -> str:
    """Store a memory. Type is required. Returns memory ID.

    Args:
        what: Memory content/summary
        type: Memory type (decision, world, anomaly, experience)
        tags: Optional list of tags
        conf: Optional confidence score (0.0-1.0)
        refs: Optional list of referenced memory IDs
        priority: Priority level (-1=background, 0=normal, 1=important, 2=critical)
        valid_from: Optional timestamp when fact became true (defaults to creation time)
        sync: If True (default), block until write completes. If False, write in background.
               Use sync=True for critical memories (handoffs, decisions). Use sync=False for
               fast writes where eventual consistency is acceptable.

    Deprecated args (v2.0.0 - ignored but accepted for backward compat):
        entities, importance, memory_class

    Returns:
        Memory ID (UUID)

    v0.6.0: Added sync parameter for background writes. Use flush() to wait for all pending writes.
    v0.13.0: Removed embedding generation (OpenAI dependency removed).
    v2.0.0: Simplified schema. Added priority. Removed entities, importance, memory_class.
    """
    if type not in TYPES:
        raise ValueError(f"Invalid type '{type}'. Must be one of: {', '.join(sorted(TYPES))}")

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mem_id = str(uuid.uuid4())

    if type == "decision" and conf is None:
        conf = 0.8

    if valid_from is None:
        valid_from = now

    # Clamp priority to valid range
    priority = max(-1, min(2, priority))

    # Write to local cache immediately (if available) - v0.7.0
    if _cache_available():
        _cache_memory(mem_id, what, type, now, conf, tags, priority,
                     refs=refs, valid_from=valid_from)

    if sync:
        # Blocking write to Turso
        _write_memory(mem_id, what, type, now, conf, tags, refs, priority, valid_from)
    else:
        # Background write to Turso
        def _bg_write():
            try:
                _write_memory(mem_id, what, type, now, conf, tags, refs, priority, valid_from)
            finally:
                # Remove from pending list when done
                with state._pending_writes_lock:
                    if thread in state._pending_writes:
                        state._pending_writes.remove(thread)

        thread = threading.Thread(target=_bg_write, daemon=True)
        with state._pending_writes_lock:
            state._pending_writes.append(thread)
        thread.start()

    # v0.13.0: Auto-append novel tags to recall-triggers config
    # This helps build up a vocabulary of searchable terms over time
    if tags:
        try:
            # Get current recall-triggers list
            current_triggers = config_get("recall-triggers")
            if current_triggers:
                try:
                    trigger_list = json.loads(current_triggers) if isinstance(current_triggers, str) else current_triggers
                except json.JSONDecodeError:
                    trigger_list = []
            else:
                trigger_list = []

            # Add novel tags
            trigger_set = set(trigger_list)
            new_tags = [t for t in tags if t not in trigger_set]
            if new_tags:
                trigger_set.update(new_tags)
                config_set("recall-triggers", json.dumps(sorted(trigger_set)), "ops")
        except Exception:
            # Don't fail remember() if trigger update fails
            pass

    return mem_id


def remember_bg(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None,
                importance: float = None, memory_class: str = None, valid_from: str = None) -> str:
    """Deprecated: Use remember(..., sync=False) instead.

    Fire-and-forget memory storage. Type required. Returns immediately, writes in background.

    Args:
        Same as remember(), including v0.4.0 parameters (importance, memory_class, valid_from).

    Returns:
        Memory ID (UUID)
    """
    return remember(what, type, tags=tags, conf=conf, entities=entities, refs=refs,
                    importance=importance, memory_class=memory_class, valid_from=valid_from, sync=False)


def flush(timeout: float = 5.0) -> dict:
    """Block until all pending background writes complete.

    Call this before conversation end to ensure all memories are persisted.

    Args:
        timeout: Maximum seconds to wait per thread (default 5.0)

    Returns:
        Dict with 'completed' count and 'timed_out' count

    Example:
        remember("note 1", "world", sync=False)
        remember("note 2", "world", sync=False)
        flush()  # Wait for both writes to complete
    """
    with state._pending_writes_lock:
        threads = list(state._pending_writes)  # Copy list

    completed = 0
    timed_out = 0

    for thread in threads:
        thread.join(timeout=timeout)
        if thread.is_alive():
            timed_out += 1
        else:
            completed += 1

    return {"completed": completed, "timed_out": timed_out}


def recall(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any",
           use_cache: bool = True, strict: bool = False) -> list:
    """Query memories with flexible filters.

    v0.7.0: Uses local cache with progressive disclosure when available.
    v0.9.0: Uses FTS5 for ranked text search instead of LIKE.
    v0.12.0: Logs queries for retrieval instrumentation.
    v0.12.1: Adds strict mode for timestamp-only ordering (no ranking).

    Args:
        search: Text to search for in memory summaries (FTS5 ranked search)
        n: Max number of results
        tags: Filter by tags
        type: Filter by memory type
        conf: Minimum confidence threshold
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        use_cache: If True (default), check local cache first (much faster)
        strict: If True, skip FTS5/ranking and order by timestamp DESC (v0.12.1)
    """
    # Track timing for logging (v0.12.0)
    start_time = time.time()

    if isinstance(search, int):
        return _query(limit=search)

    # Try cache first (progressive disclosure)
    # v2.0.1: Only trust empty cache results if warming completed, otherwise fall back to Turso
    if use_cache and _cache_available():
        results = _cache_query_index(search=search, type=type, tags=tags, n=n, conf=conf, tag_mode=tag_mode, strict=strict)

        # v2.0.1: If cache returns no results and warming isn't complete, fall back to Turso
        # This fixes race condition where recall() called immediately after boot() returns 0 results
        if not results and not state._cache_warmed:
            results = _query(search=search, tags=tags, type=type, conf=conf, limit=n, tag_mode=tag_mode)
            exec_time = (time.time() - start_time) * 1000
            _log_recall_query(
                query=search,
                filters={'type': type, 'tags': tags, 'conf': conf, 'tag_mode': tag_mode},
                n_requested=n,
                n_returned=len(results),
                exec_time_ms=exec_time,
                used_cache=False,
                used_semantic_fallback=False
            )
            return results

        # v0.13.0: Query expansion fallback - if FTS5 returns few results and search was provided,
        # extract tags from partial results and search for those tags to find related memories
        # Skip in strict mode
        if search and not strict and len(results) < 3:
            # Extract unique tags from partial results
            expansion_tags = set()
            for r in results:
                result_tags = r.get('tags', [])
                if isinstance(result_tags, list):
                    expansion_tags.update(result_tags)

            # Search for memories with those tags (exclude already found)
            if expansion_tags:
                seen_ids = {r['id'] for r in results}
                for tag in expansion_tags:
                    # Search for this tag as a term (handles concept relationships)
                    tag_results = _cache_query_index(search=tag, type=type, tags=tags, n=n-len(results), conf=conf, tag_mode=tag_mode, strict=strict)
                    for tr in tag_results:
                        if tr['id'] not in seen_ids:
                            results.append(tr)
                            seen_ids.add(tr['id'])
                            if len(results) >= n:
                                break
                    if len(results) >= n:
                        break

        if results:
            # Check if we need to fetch full content for any results
            need_full = [r['id'] for r in results if not r.get('has_full')]

            if need_full:
                # Lazy-load full content from Turso
                full_content = _fetch_full_content(need_full)

                # Update cache with full content
                _cache_populate_full(full_content)

                # Merge full content into results
                full_by_id = {m['id']: m for m in full_content}
                for r in results:
                    if r['id'] in full_by_id:
                        full = full_by_id[r['id']]
                        # v2.0.0: Removed entities, memory_class, valid_to from schema
                        r.update({
                            'summary': full.get('summary'),
                            'refs': full.get('refs'),
                            'valid_from': full.get('valid_from'),
                            'access_count': full.get('access_count'),
                            'last_accessed': full.get('last_accessed'),
                            'has_full': 1
                        })

            # Track access in Turso (background, don't block)
            def _bg_track():
                _update_access_tracking([r['id'] for r in results])
            threading.Thread(target=_bg_track, daemon=True).start()

            # Log query (v0.12.0)
            exec_time = (time.time() - start_time) * 1000  # Convert to ms
            _log_recall_query(
                query=search,
                filters={'type': type, 'tags': tags, 'conf': conf, 'tag_mode': tag_mode},
                n_requested=n,
                n_returned=len(results),
                exec_time_ms=exec_time,
                used_cache=True,
                used_semantic_fallback=False
            )

            return results

    # Fallback to direct Turso query
    results = _query(search=search, tags=tags, type=type, conf=conf, limit=n, tag_mode=tag_mode)

    # Log query (v0.12.0)
    exec_time = (time.time() - start_time) * 1000  # Convert to ms
    _log_recall_query(
        query=search,
        filters={'type': type, 'tags': tags, 'conf': conf, 'tag_mode': tag_mode},
        n_requested=n,
        n_returned=len(results),
        exec_time_ms=exec_time,
        used_cache=False,
        used_semantic_fallback=False
    )

    return results


def _update_access_tracking(memory_ids: list):
    """Update access_count and last_accessed for memories (v0.4.0, updated v0.10.0 for cache sync)."""
    if not memory_ids:
        return
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Update Turso database
    placeholders = ", ".join("?" * len(memory_ids))
    _exec(f"""
        UPDATE memories
        SET access_count = COALESCE(access_count, 0) + 1,
            last_accessed = ?
        WHERE id IN ({placeholders})
    """, [now] + memory_ids)

    # Update cache if available (v0.10.0)
    if _cache_available():
        try:
            for mem_id in memory_ids:
                # Update memory_index
                state._cache_conn.execute("""
                    UPDATE memory_index
                    SET access_count = COALESCE(access_count, 0) + 1,
                        last_accessed = ?
                    WHERE id = ?
                """, (now, mem_id))

                # Update memory_full
                state._cache_conn.execute("""
                    UPDATE memory_full
                    SET access_count = COALESCE(access_count, 0) + 1,
                        last_accessed = ?
                    WHERE id = ?
                """, (now, mem_id))

            state._cache_conn.commit()
        except Exception as e:
            print(f"Warning: Cache access tracking failed: {e}")


def _query(search: str = None, tags: list = None, type: str = None,
           conf: float = None, limit: int = 10, tag_mode: str = "any") -> list:
    """Internal query implementation.

    Args:
        tag_mode: "any" (default) matches any tag, "all" requires all tags

    v0.4.0: Tracks access_count and last_accessed for retrieved memories.
    """
    # Exclude soft-deleted memories and superseded memories (those referenced in refs)
    conditions = [
        "deleted_at IS NULL",
        # Exclude memories that are superseded (appear in any other memory's refs field)
        "id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]

    if search:
        conditions.append(f"summary LIKE '%{search}%'")
    if tags:
        if tag_mode == "all":
            # Require all tags to be present
            tag_conds = " AND ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        else:  # "any"
            # Match any of the tags
            tag_conds = " OR ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        conditions.append(f"({tag_conds})")
    if type:
        conditions.append(f"type = '{type}'")
    if conf is not None:
        conditions.append(f"confidence >= {conf}")

    where = " AND ".join(conditions)
    order = "confidence DESC" if conf else "t DESC"

    results = _exec(f"SELECT * FROM memories WHERE {where} ORDER BY {order} LIMIT {limit}")

    # Track access for returned memories
    if results:
        _update_access_tracking([m["id"] for m in results])

    return results


def recall_since(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any") -> list:
    """Query memories created after a given timestamp.

    Args:
        after: ISO timestamp (e.g., '2025-12-26T00:00:00Z')
        search: Text to search for in memory summaries
        n: Max number of results
        type: Filter by memory type
        tags: Filter by tags
        tag_mode: "any" (default) matches any tag, "all" requires all tags
    """
    conditions = [
        "deleted_at IS NULL",
        f"t > '{after}'",
        "id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]
    if search:
        conditions.append(f"summary LIKE '%{search}%'")
    if type:
        conditions.append(f"type = '{type}'")
    if tags:
        if tag_mode == "all":
            tag_conds = " AND ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        else:  # "any"
            tag_conds = " OR ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        conditions.append(f"({tag_conds})")
    where = " AND ".join(conditions)
    results = _exec(f"SELECT * FROM memories WHERE {where} ORDER BY t DESC LIMIT {n}")

    # Track access for returned memories
    if results:
        _update_access_tracking([m["id"] for m in results])

    return results


def recall_between(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any") -> list:
    """Query memories within a time range.

    Args:
        after: Start timestamp (exclusive)
        before: End timestamp (exclusive)
        search: Text to search for in memory summaries
        n: Max number of results
        type: Filter by memory type
        tags: Filter by tags
        tag_mode: "any" (default) matches any tag, "all" requires all tags
    """
    conditions = [
        "deleted_at IS NULL",
        f"t > '{after}'",
        f"t < '{before}'",
        "id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]
    if search:
        conditions.append(f"summary LIKE '%{search}%'")
    if type:
        conditions.append(f"type = '{type}'")
    if tags:
        if tag_mode == "all":
            tag_conds = " AND ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        else:  # "any"
            tag_conds = " OR ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        conditions.append(f"({tag_conds})")
    where = " AND ".join(conditions)
    results = _exec(f"SELECT * FROM memories WHERE {where} ORDER BY t DESC LIMIT {n}")

    # Track access for returned memories
    if results:
        _update_access_tracking([m["id"] for m in results])

    return results


def forget(memory_id: str) -> bool:
    """Soft-delete a memory."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _exec("UPDATE memories SET deleted_at = ? WHERE id = ?", [now, memory_id])

    # Invalidate cache (v0.13.0 bugfix)
    if _cache_available():
        try:
            state._cache_conn.execute("DELETE FROM memory_index WHERE id = ?", (memory_id,))
            state._cache_conn.execute("DELETE FROM memory_full WHERE id = ?", (memory_id,))
            state._cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (memory_id,))
            state._cache_conn.commit()
        except Exception as e:
            print(f"Warning: Failed to invalidate cache for {memory_id}: {e}")

    return True


def supersede(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None) -> str:
    """Create a patch that supersedes an existing memory. Type required. Returns new memory ID.

    v0.4.0: Sets valid_to on original memory and valid_from on new memory for bitemporal tracking.
    v0.13.0: Invalidates cache for superseded memory.
    v2.0.0: Soft-deletes original memory (valid_to column removed from schema).
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Soft-delete original memory to mark when it stopped being true
    # v2.0.0: valid_to column removed, using deleted_at for supersession tracking
    _exec("UPDATE memories SET deleted_at = ? WHERE id = ?", [now, original_id])

    # Invalidate cache for superseded memory (v0.13.0 bugfix)
    # Superseded memories should not appear in recall() results
    if _cache_available():
        try:
            state._cache_conn.execute("DELETE FROM memory_index WHERE id = ?", (original_id,))
            state._cache_conn.execute("DELETE FROM memory_full WHERE id = ?", (original_id,))
            state._cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (original_id,))
            state._cache_conn.commit()
        except Exception as e:
            print(f"Warning: Failed to invalidate cache for superseded memory {original_id}: {e}")

    # Create new memory with valid_from set to now
    return remember(summary, type, tags=tags, conf=conf, refs=[original_id], valid_from=now)


# --- Priority adjustment functions (v2.0.0) ---

def reprioritize(memory_id: str, priority: int) -> None:
    """Adjust priority for a memory.

    Priority levels:
        -1: Background (low-value, can age out first)
         0: Normal (default)
         1: Important (boost in ranking)
         2: Critical (always surface, never auto-age)

    Args:
        memory_id: Memory UUID
        priority: New priority level (-1 to 2)

    Example:
        reprioritize("abc-123", priority=2)  # Mark as critical
        reprioritize("xyz-789", priority=-1)  # Demote to background
    """
    priority = max(-1, min(2, priority))

    # Update Turso database
    _exec("""
        UPDATE memories
        SET priority = ?
        WHERE id = ?
    """, [priority, memory_id])

    # Update cache if available
    if _cache_available():
        try:
            state._cache_conn.execute("""
                UPDATE memory_index
                SET priority = ?
                WHERE id = ?
            """, (priority, memory_id))
            state._cache_conn.commit()
        except Exception as e:
            print(f"Warning: Cache priority update failed: {e}")


# Deprecated functions (v2.0.0) - kept for backward compatibility
def strengthen(memory_id: str, factor: float = 1.5) -> None:
    """DEPRECATED: Use reprioritize() instead. This is a no-op in v2.0.0."""
    pass


def weaken(memory_id: str, factor: float = 0.5) -> None:
    """DEPRECATED: Use reprioritize() instead. This is a no-op in v2.0.0."""
    pass
