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
import atexit
from datetime import datetime, UTC

from . import state
from .state import TYPES, get_session_id
from .turso import _exec, _exec_batch
from .cache import (
    _cache_available, _cache_memory, _cache_query_index,
    _fetch_full_content, _cache_populate_full, _log_recall_query
)
# Import config_get and config_set for recall-triggers management
from .config import config_get, config_set
from .result import wrap_results, MemoryResult, MemoryResultList

# v3.2.0: Register automatic flush on exit to prevent data loss from background writes
@atexit.register
def _auto_flush_on_exit():
    """Automatically flush pending background writes on process exit.

    This prevents data loss when background writes are pending and the process terminates.
    Registered with atexit to ensure it runs even on abnormal exits.
    """
    with state._pending_writes_lock:
        pending_count = len(state._pending_writes)

    if pending_count > 0:
        # Only print if there are actually pending writes
        result = flush(timeout=10.0)
        completed = result.get('completed', 0)
        timed_out = result.get('timed_out', 0)
        if completed > 0 or timed_out > 0:
            print(f"Muninn: Auto-flushed {completed} background writes on exit ({timed_out} timed out)")



def _write_memory(mem_id: str, what: str, type: str, now: str, conf: float,
                  tags: list, refs: list, priority: int, valid_from: str, session_id: str) -> None:
    """Internal helper: write memory to Turso (blocking).

    v2.0.0: Simplified schema - removed entities, importance, salience, memory_class, embedding. Added priority field.
    v3.2.0: Re-enabled session_id tracking.
    """
    _exec(
        """INSERT INTO memories (id, type, t, summary, confidence, tags, refs, priority,
           session_id, created_at, updated_at, valid_from, access_count, last_accessed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)""",
        [mem_id, type, now, what, conf,
         json.dumps(tags or []), json.dumps(refs or []),
         priority, session_id, now, now, valid_from]
    )


def remember(what: str, type: str, *, tags: list = None, conf: float = None,
             refs: list = None, priority: int = 0, valid_from: str = None,
             sync: bool = True, session_id: str = None,
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
        session_id: Optional session identifier. Defaults to MUNINN_SESSION_ID env var or 'default-session'.

    Deprecated args (v2.0.0 - ignored but accepted for backward compat):
        entities, importance, memory_class

    Returns:
        Memory ID (UUID)

    v0.6.0: Added sync parameter for background writes. Use flush() to wait for all pending writes.
    v0.13.0: Removed embedding generation (OpenAI dependency removed).
    v2.0.0: Simplified schema. Added priority. Removed entities, importance, memory_class.
    v3.2.0: Added session_id parameter for session scoping.
    """
    if type not in TYPES:
        raise ValueError(f"Invalid type '{type}'. Must be one of: {', '.join(sorted(TYPES))}")

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mem_id = str(uuid.uuid4())

    if type == "decision" and conf is None:
        conf = 0.8

    if valid_from is None:
        valid_from = now

    if session_id is None:
        session_id = get_session_id()

    # Clamp priority to valid range
    priority = max(-1, min(2, priority))

    # Write to local cache immediately (if available) - v0.7.0
    if _cache_available():
        _cache_memory(mem_id, what, type, now, conf, tags, priority,
                     refs=refs, valid_from=valid_from, session_id=session_id)

    if sync:
        # Blocking write to Turso
        _write_memory(mem_id, what, type, now, conf, tags, refs, priority, valid_from, session_id)
    else:
        # Background write to Turso
        def _bg_write():
            try:
                _write_memory(mem_id, what, type, now, conf, tags, refs, priority, valid_from, session_id)
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
           use_cache: bool = True, strict: bool = False, session_id: str = None,
           auto_strengthen: bool = False, raw: bool = False,
           expansion_threshold: int = 3,
           limit: int = None, fetch_all: bool = False) -> MemoryResultList:
    """Query memories with flexible filters.

    v0.7.0: Uses local cache with progressive disclosure when available.
    v0.9.0: Uses FTS5 for ranked text search instead of LIKE.
    v0.12.0: Logs queries for retrieval instrumentation.
    v0.12.1: Adds strict mode for timestamp-only ordering (no ranking).
    v3.2.0: Added session_id filter for session scoping.
    v3.3.0: Added auto_strengthen for biological memory consolidation pattern.
    v3.4.0: Returns MemoryResult objects that validate field access.
    v3.7.0: Added expansion_threshold parameter. Added limit as alias for n.
    v4.1.0: Added fetch_all parameter for comprehensive memory retrieval.

    Args:
        search: Text to search for in memory summaries (FTS5 ranked search).
            Note: Wildcards like '*' are treated as literal text, not patterns.
            Use fetch_all=True for comprehensive retrieval instead.
        n: Max number of results
        tags: Filter by tags
        type: Filter by memory type
        conf: Minimum confidence threshold
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        use_cache: If True (default), check local cache first (much faster)
        strict: If True, skip FTS5/ranking and order by timestamp DESC (v0.12.1)
        session_id: Filter by session identifier (optional)
        auto_strengthen: If True, automatically strengthen top 3 results (v3.3.0)
        raw: If True, return plain dicts instead of MemoryResult objects (v3.4.0)
        expansion_threshold: Minimum results before triggering query expansion (default 3).
            Set to 0 to disable expansion entirely. (v3.7.0)
        limit: Deprecated alias for n. If provided, overrides n. (v3.7.0)
        fetch_all: If True, retrieve all memories without search filtering (v4.1.0).
            This is the explicit way to get comprehensive memory retrieval.
            When True, the search parameter is ignored.

    Returns:
        MemoryResultList of MemoryResult objects (or list of dicts if raw=True).
        MemoryResult objects validate field access and transparently resolve
        common aliases like 'content' -> 'summary'.
    """
    # v3.7.0: Accept limit= as deprecated alias for n=
    if limit is not None:
        n = limit

    # v4.1.0: Validate wildcard patterns and guide users to fetch_all
    if search and not fetch_all:
        wildcard_patterns = ['*', '%', '?']
        if any(pattern in search and search.strip() in wildcard_patterns for pattern in wildcard_patterns):
            raise ValueError(
                f"Wildcard pattern '{search}' is not supported. "
                "Use fetch_all=True for comprehensive memory retrieval instead. "
                f"Example: recall(fetch_all=True, n={n})"
            )

    # v4.1.0: Handle fetch_all mode - retrieve all memories without search filtering
    if fetch_all:
        search = None

    # Track timing for logging (v0.12.0)
    start_time = time.time()

    if isinstance(search, int):
        results = _query(limit=search)
        return results if raw else wrap_results(results)

    # Try cache first (progressive disclosure)
    # v2.0.1: Only trust empty cache results if warming completed, otherwise fall back to Turso
    # v3.8.0: Session-filtered queries now use cache (#237) instead of bypassing it
    if use_cache and _cache_available():
        results = _cache_query_index(search=search, type=type, tags=tags, n=n, conf=conf, tag_mode=tag_mode, strict=strict, session_id=session_id)

        # v2.0.1: If cache returns no results and warming isn't complete, fall back to Turso
        # This fixes race condition where recall() called immediately after boot() returns 0 results
        if not results and not state._cache_warmed:
            results = _query(search=search, tags=tags, type=type, conf=conf, limit=n, tag_mode=tag_mode, session_id=session_id)
            exec_time = (time.time() - start_time) * 1000
            _log_recall_query(
                query=search,
                filters={'type': type, 'tags': tags, 'conf': conf, 'tag_mode': tag_mode, 'session_id': session_id},
                n_requested=n,
                n_returned=len(results),
                exec_time_ms=exec_time,
                used_cache=False,
                used_semantic_fallback=False
            )
            return results if raw else wrap_results(results)

        # v0.13.0: Query expansion fallback - if FTS5 returns few results and search was provided,
        # extract tags from partial results and search for those tags to find related memories
        # Skip in strict mode. v3.7.0: threshold is configurable via expansion_threshold parameter.
        if search and not strict and expansion_threshold > 0 and len(results) < expansion_threshold:
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

            # Auto-strengthen returned memories if requested (v3.3.0)
            # Biological parallel: memories that participate in cognition consolidate
            if auto_strengthen and results:
                for r in results[:3]:  # Only top 3 to avoid over-strengthening
                    if r.get('priority', 0) < 2:
                        strengthen(r['id'], boost=1)

            # Log query (v0.12.0)
            exec_time = (time.time() - start_time) * 1000  # Convert to ms
            _log_recall_query(
                query=search,
                filters={'type': type, 'tags': tags, 'conf': conf, 'tag_mode': tag_mode, 'session_id': session_id},
                n_requested=n,
                n_returned=len(results),
                exec_time_ms=exec_time,
                used_cache=True,
                used_semantic_fallback=False
            )

            return results if raw else wrap_results(results)

    # Fallback to direct Turso query
    results = _query(search=search, tags=tags, type=type, conf=conf, limit=n, tag_mode=tag_mode, session_id=session_id)

    # Auto-strengthen returned memories if requested (v3.3.0)
    # Biological parallel: memories that participate in cognition consolidate
    if auto_strengthen and results:
        for r in results[:3]:  # Only top 3 to avoid over-strengthening
            if r.get('priority', 0) < 2:
                strengthen(r['id'], boost=1)

    # Log query (v0.12.0)
    exec_time = (time.time() - start_time) * 1000  # Convert to ms
    _log_recall_query(
        query=search,
        filters={'type': type, 'tags': tags, 'conf': conf, 'tag_mode': tag_mode, 'session_id': session_id},
        n_requested=n,
        n_returned=len(results),
        exec_time_ms=exec_time,
        used_cache=False,
        used_semantic_fallback=False
    )

    return results if raw else wrap_results(results)


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
           conf: float = None, limit: int = 10, tag_mode: str = "any", session_id: str = None) -> list:
    """Internal query implementation with parameterized queries.

    Args:
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        session_id: Optional session filter (v3.2.0)

    v0.4.0: Tracks access_count and last_accessed for retrieved memories.
    v3.2.0: Added session_id filter. Converted to parameterized queries for SQL injection protection.
    """
    # Build parameterized WHERE clause
    conditions = [
        "deleted_at IS NULL",
        # Exclude memories that are superseded (appear in any other memory's refs field)
        "id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]
    params = []

    if search:
        conditions.append("summary LIKE ?")
        params.append(f"%{search}%")

    if tags:
        if tag_mode == "all":
            # Require all tags to be present
            tag_conds = []
            for t in tags:
                tag_conds.append("tags LIKE ?")
                params.append(f'%"{t}"%')
            conditions.append(f"({' AND '.join(tag_conds)})")
        else:  # "any"
            # Match any of the tags
            tag_conds = []
            for t in tags:
                tag_conds.append("tags LIKE ?")
                params.append(f'%"{t}"%')
            conditions.append(f"({' OR '.join(tag_conds)})")

    if type:
        conditions.append("type = ?")
        params.append(type)

    if conf is not None:
        conditions.append("confidence >= ?")
        params.append(conf)

    if session_id is not None:
        conditions.append("session_id = ?")
        params.append(session_id)

    where = " AND ".join(conditions)
    order = "confidence DESC" if conf else "t DESC"

    # Add limit as parameter
    query = f"SELECT * FROM memories WHERE {where} ORDER BY {order} LIMIT ?"
    params.append(limit)

    results = _exec(query, params)

    # Track access for returned memories
    if results:
        _update_access_tracking([m["id"] for m in results])

    return results


def recall_since(after: str, *, search: str = None, n: int = 50,
                 type: str = None, tags: list = None, tag_mode: str = "any",
                 session_id: str = None, raw: bool = False) -> MemoryResultList:
    """Query memories created after a given timestamp with parameterized queries.

    Args:
        after: ISO timestamp (e.g., '2025-12-26T00:00:00Z')
        search: Text to search for in memory summaries
        n: Max number of results
        type: Filter by memory type
        tags: Filter by tags
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        session_id: Filter by session identifier (optional, v3.2.0)
        raw: If True, return plain dicts instead of MemoryResult objects (v3.4.0)

    Returns:
        MemoryResultList of MemoryResult objects (or list of dicts if raw=True).

    v3.2.0: Converted to parameterized queries for SQL injection protection.
    v3.4.0: Returns MemoryResult objects that validate field access.
    """
    conditions = [
        "deleted_at IS NULL",
        "t > ?",
        "id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]
    params = [after]

    if search:
        conditions.append("summary LIKE ?")
        params.append(f"%{search}%")

    if type:
        conditions.append("type = ?")
        params.append(type)

    if tags:
        if tag_mode == "all":
            tag_conds = []
            for t in tags:
                tag_conds.append("tags LIKE ?")
                params.append(f'%"{t}"%')
            conditions.append(f"({' AND '.join(tag_conds)})")
        else:  # "any"
            tag_conds = []
            for t in tags:
                tag_conds.append("tags LIKE ?")
                params.append(f'%"{t}"%')
            conditions.append(f"({' OR '.join(tag_conds)})")

    if session_id is not None:
        conditions.append("session_id = ?")
        params.append(session_id)

    where = " AND ".join(conditions)
    query = f"SELECT * FROM memories WHERE {where} ORDER BY t DESC LIMIT ?"
    params.append(n)

    results = _exec(query, params)

    # Track access for returned memories
    if results:
        _update_access_tracking([m["id"] for m in results])

    return results if raw else wrap_results(results)


def recall_between(after: str, before: str, *, search: str = None,
                   n: int = 100, type: str = None, tags: list = None,
                   tag_mode: str = "any", session_id: str = None, raw: bool = False) -> MemoryResultList:
    """Query memories within a time range with parameterized queries.

    Args:
        after: Start timestamp (exclusive)
        before: End timestamp (exclusive)
        search: Text to search for in memory summaries
        n: Max number of results
        type: Filter by memory type
        tags: Filter by tags
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        session_id: Filter by session identifier (optional, v3.2.0)
        raw: If True, return plain dicts instead of MemoryResult objects (v3.4.0)

    Returns:
        MemoryResultList of MemoryResult objects (or list of dicts if raw=True).

    v3.2.0: Converted to parameterized queries for SQL injection protection.
    v3.4.0: Returns MemoryResult objects that validate field access.
    """
    conditions = [
        "deleted_at IS NULL",
        "t > ?",
        "t < ?",
        "id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]
    params = [after, before]

    if search:
        conditions.append("summary LIKE ?")
        params.append(f"%{search}%")

    if type:
        conditions.append("type = ?")
        params.append(type)

    if tags:
        if tag_mode == "all":
            tag_conds = []
            for t in tags:
                tag_conds.append("tags LIKE ?")
                params.append(f'%"{t}"%')
            conditions.append(f"({' AND '.join(tag_conds)})")
        else:  # "any"
            tag_conds = []
            for t in tags:
                tag_conds.append("tags LIKE ?")
                params.append(f'%"{t}"%')
            conditions.append(f"({' OR '.join(tag_conds)})")

    if session_id is not None:
        conditions.append("session_id = ?")
        params.append(session_id)

    where = " AND ".join(conditions)
    query = f"SELECT * FROM memories WHERE {where} ORDER BY t DESC LIMIT ?"
    params.append(n)

    results = _exec(query, params)

    # Track access for returned memories
    if results:
        _update_access_tracking([m["id"] for m in results])

    return results if raw else wrap_results(results)


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
    v3.3.0: Uses _exec_batch for single HTTP request (2x efficiency improvement).
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    new_id = str(uuid.uuid4())
    session_id = get_session_id()

    # Batch both operations in single HTTP request (v3.3.0)
    _exec_batch([
        # Soft-delete original
        ("UPDATE memories SET deleted_at = ? WHERE id = ?", [now, original_id]),
        # Insert new memory
        ("""INSERT INTO memories (id, type, t, summary, confidence, tags, refs, priority,
               session_id, created_at, updated_at, valid_from, access_count, last_accessed)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, NULL)""",
         [new_id, type, now, summary, conf or 0.8,
          json.dumps(tags or []), json.dumps([original_id]),
          session_id, now, now, now])
    ])

    # Cache invalidation (unchanged)
    if _cache_available():
        try:
            state._cache_conn.execute("DELETE FROM memory_index WHERE id = ?", (original_id,))
            state._cache_conn.execute("DELETE FROM memory_full WHERE id = ?", (original_id,))
            state._cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (original_id,))
            state._cache_conn.commit()
        except Exception as e:
            print(f"Warning: Failed to invalidate cache for superseded memory {original_id}: {e}")

    # Cache new memory
    _cache_memory(new_id, summary, type, now, conf or 0.8, tags, priority=0,
                 refs=[original_id], valid_from=now)

    # Update recall-triggers (moved from remember() to avoid duplication)
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
            # Don't fail supersede() if trigger update fails
            pass

    return new_id


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


# --- Retrieval observability and retention helpers (v3.2.0) ---

def memory_histogram() -> dict:
    """Get distribution of memories by type, priority, and age.

    Returns:
        Dict with memory count breakdowns

    Example:
        >>> hist = memory_histogram()
        >>> print(f"Total memories: {hist['total']}")
        >>> print(f"By type: {hist['by_type']}")
        >>> print(f"By priority: {hist['by_priority']}")
    """
    # Get all active memories
    results = _exec("""
        SELECT type, priority, created_at
        FROM memories
        WHERE deleted_at IS NULL
          AND id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)
    """)

    if not results:
        return {
            "total": 0,
            "by_type": {},
            "by_priority": {},
            "by_age_days": {}
        }

    from collections import Counter
    now = datetime.now(UTC)

    by_type = Counter(m['type'] for m in results)
    by_priority = Counter(m.get('priority', 0) for m in results)

    # Age buckets: 0-7 days, 8-30 days, 31-90 days, 90+ days
    age_buckets = {"0-7d": 0, "8-30d": 0, "31-90d": 0, "90d+": 0}
    for m in results:
        created = datetime.fromisoformat(m['created_at'].replace('Z', '+00:00'))
        age_days = (now - created).days
        if age_days <= 7:
            age_buckets["0-7d"] += 1
        elif age_days <= 30:
            age_buckets["8-30d"] += 1
        elif age_days <= 90:
            age_buckets["31-90d"] += 1
        else:
            age_buckets["90d+"] += 1

    return {
        "total": len(results),
        "by_type": dict(by_type),
        "by_priority": dict(by_priority),
        "by_age_days": age_buckets
    }


def prune_by_age(older_than_days: int, priority_floor: int = 0, dry_run: bool = True) -> dict:
    """Soft-delete old memories with priority at or below a threshold.

    Args:
        older_than_days: Delete memories older than this many days
        priority_floor: Only delete memories with priority <= this (default 0)
        dry_run: If True (default), return what would be deleted without deleting

    Returns:
        Dict with count and list of memory IDs that were (or would be) deleted

    Example:
        >>> # See what would be deleted
        >>> result = prune_by_age(older_than_days=90, priority_floor=0)
        >>> print(f"Would delete {result['count']} memories")
        >>> # Actually delete
        >>> result = prune_by_age(older_than_days=90, priority_floor=0, dry_run=False)
    """
    cutoff = datetime.now(UTC) - __import__('datetime').timedelta(days=older_than_days)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")

    # Find candidates
    results = _exec("""
        SELECT id, summary, type, priority, created_at
        FROM memories
        WHERE deleted_at IS NULL
          AND created_at < ?
          AND priority <= ?
          AND id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)
    """, [cutoff_iso, priority_floor])

    ids = [m['id'] for m in results]

    if not dry_run and ids:
        # Actually delete
        for memory_id in ids:
            forget(memory_id)

    return {
        "count": len(ids),
        "ids": ids,
        "dry_run": dry_run,
        "criteria": f"older_than={older_than_days}d, priority<={priority_floor}"
    }


def prune_by_priority(max_priority: int = -1, dry_run: bool = True) -> dict:
    """Soft-delete memories with priority at or below a threshold.

    Args:
        max_priority: Delete memories with priority <= this (default -1, background only)
        dry_run: If True (default), return what would be deleted without deleting

    Returns:
        Dict with count and list of memory IDs that were (or would be) deleted

    Example:
        >>> # Delete all background priority memories
        >>> result = prune_by_priority(max_priority=-1, dry_run=False)
    """
    # Find candidates
    results = _exec("""
        SELECT id, summary, type, priority
        FROM memories
        WHERE deleted_at IS NULL
          AND priority <= ?
          AND id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)
    """, [max_priority])

    ids = [m['id'] for m in results]

    if not dry_run and ids:
        # Actually delete
        for memory_id in ids:
            forget(memory_id)

    return {
        "count": len(ids),
        "ids": ids,
        "dry_run": dry_run,
        "criteria": f"priority<={max_priority}"
    }


# Priority adjustment with biological memory consolidation pattern (v3.3.0)
def strengthen(memory_id: str, boost: int = 1) -> dict:
    """Strengthen a memory by incrementing its priority.

    Based on biological memory consolidation: memories that participate
    in active cognition should consolidate more strongly.

    Args:
        memory_id: UUID of memory to strengthen
        boost: Priority increment (default 1, max result is 2)

    Returns:
        dict with memory_id, old_priority, new_priority, changed
    """
    # Get current state
    result = _exec(
        "SELECT priority, access_count FROM memories WHERE id = ? AND deleted_at IS NULL",
        [memory_id]
    )

    if not result:
        return {"error": f"Memory {memory_id} not found"}

    old_priority = int(result[0]['priority'] or 0)
    access_count = int(result[0]['access_count'] or 0)

    # Cap at priority=2
    new_priority = min(2, old_priority + boost)

    if new_priority != old_priority:
        reprioritize(memory_id, new_priority)

    return {
        "memory_id": memory_id,
        "old_priority": old_priority,
        "new_priority": new_priority,
        "access_count": access_count,
        "changed": new_priority != old_priority
    }


def weaken(memory_id: str, drop: int = 1) -> dict:
    """Weaken a memory by decrementing its priority.

    Args:
        memory_id: UUID of memory to weaken
        drop: Priority decrement (default 1, min result is -1)

    Returns:
        dict with memory_id, old_priority, new_priority, changed
    """
    result = _exec(
        "SELECT priority FROM memories WHERE id = ? AND deleted_at IS NULL",
        [memory_id]
    )

    if not result:
        return {"error": f"Memory {memory_id} not found"}

    old_priority = int(result[0]['priority'] or 0)
    new_priority = max(-1, old_priority - drop)

    if new_priority != old_priority:
        reprioritize(memory_id, new_priority)

    return {
        "memory_id": memory_id,
        "old_priority": old_priority,
        "new_priority": new_priority,
        "changed": new_priority != old_priority
    }
