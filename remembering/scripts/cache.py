"""
Local SQLite cache layer for remembering skill.

This module handles:
- Cache initialization and schema creation (_init_local_cache)
- Cache availability checks (_cache_available)
- Cache population (index, full content, config)
- FTS5 full-text search queries
- Cache write-through operations
- Query logging for instrumentation

Imports from: state, turso
"""

import sqlite3
import json
import uuid
from datetime import datetime, UTC

from . import state
from .turso import _exec


def _init_local_cache() -> bool:
    """Initialize local SQLite cache. Returns True if successful."""
    if state._cache_conn is not None:
        return True  # Already initialized

    if not state._cache_enabled:
        return False

    try:
        state._CACHE_DIR.mkdir(parents=True, exist_ok=True)
        state._cache_conn = sqlite3.connect(str(state._CACHE_DB), check_same_thread=False)
        state._cache_conn.row_factory = sqlite3.Row

        # Create schema
        # v2.0.0: Simplified schema - removed importance, salience, entities, memory_class, valid_to
        #         Added priority field
        state._cache_conn.executescript("""
            -- Index: populated at boot, headlines only
            CREATE TABLE IF NOT EXISTS memory_index (
                id TEXT PRIMARY KEY,
                type TEXT,
                t TEXT,
                tags TEXT,              -- JSON array
                summary_preview TEXT,   -- First 100 chars
                confidence REAL,
                priority INTEGER DEFAULT 0,  -- v2.0.0: -1=bg, 0=normal, 1=important, 2=critical
                session_id TEXT,        -- v3.8.0: session scoping for cache queries (#237)
                last_accessed TEXT,
                access_count INTEGER,
                has_full INTEGER DEFAULT 0
            );

            -- Full content: lazy-loaded on demand
            CREATE TABLE IF NOT EXISTS memory_full (
                id TEXT PRIMARY KEY,
                summary TEXT,
                refs TEXT,
                valid_from TEXT,
                access_count INTEGER,
                last_accessed TEXT
            );

            -- FTS5 virtual table for fast ranked text search (v0.9.0)
            -- v0.13.0: Added Porter stemmer for morphological variants (beads→bead, running→run)
            -- Standalone table (not contentless) for simpler sync
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                id UNINDEXED,
                summary,
                tags,
                tokenize='porter unicode61'
            );

            -- Config: full mirror (small)
            CREATE TABLE IF NOT EXISTS config_cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                category TEXT,
                boot_load INTEGER DEFAULT 1  -- 1=load at boot, 0=reference only
            );

            -- Track cache freshness
            CREATE TABLE IF NOT EXISTS cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            -- Query logging for retrieval instrumentation (v0.12.0)
            CREATE TABLE IF NOT EXISTS recall_logs (
                id TEXT PRIMARY KEY,
                t TEXT NOT NULL,
                query TEXT,
                filters TEXT,             -- JSON: {type, tags, conf, tag_mode}
                n_requested INTEGER,
                n_returned INTEGER,
                exec_time_ms REAL,
                used_cache BOOLEAN,
                used_semantic_fallback BOOLEAN
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_memory_index_type ON memory_index(type);
            CREATE INDEX IF NOT EXISTS idx_memory_index_t ON memory_index(t);
            CREATE INDEX IF NOT EXISTS idx_config_cache_category ON config_cache(category);
        """)
        state._cache_conn.commit()

        # v0.13.0: Migrate FTS5 to Porter stemmer if needed
        # v2.0.1: Silent migration - no output to avoid polluting boot()
        try:
            meta_check = state._cache_conn.execute(
                "SELECT value FROM cache_meta WHERE key = 'fts5_porter_migrated'"
            ).fetchone()

            if not meta_check:
                # Migration needed - rebuild FTS5 with Porter stemmer
                state._cache_conn.execute("DROP TABLE IF EXISTS memory_fts")
                state._cache_conn.execute("""
                    CREATE VIRTUAL TABLE memory_fts USING fts5(
                        id UNINDEXED,
                        summary,
                        tags,
                        tokenize='porter unicode61'
                    )
                """)
                state._cache_conn.execute(
                    "INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)",
                    ("fts5_porter_migrated", "true")
                )
                state._cache_conn.commit()
        except Exception:
            pass  # Silent - migration will retry on next boot

        # v2.1.0: Add boot_load column to config_cache if needed
        try:
            cursor = state._cache_conn.cursor()
            cursor.execute("PRAGMA table_info(config_cache)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'boot_load' not in columns:
                cursor.execute("ALTER TABLE config_cache ADD COLUMN boot_load INTEGER DEFAULT 1")
                state._cache_conn.commit()
        except Exception:
            pass  # Silent - migration will retry on next boot

        # v3.8.0: Add session_id column to memory_index if needed (#237)
        try:
            cursor = state._cache_conn.cursor()
            cursor.execute("PRAGMA table_info(memory_index)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'session_id' not in columns:
                cursor.execute("ALTER TABLE memory_index ADD COLUMN session_id TEXT")
                state._cache_conn.commit()
        except Exception:
            pass  # Silent - migration will retry on next boot

        # Store initialization timestamp
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        state._cache_conn.execute(
            "INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)",
            ("initialized_at", now)
        )
        state._cache_conn.commit()
        return True
    except Exception:
        # v2.0.1: Silent failure - cache is optional, don't pollute boot() output
        state._cache_conn = None
        return False


def _cache_available() -> bool:
    """Check if local cache is initialized and healthy."""
    return state._cache_conn is not None and state._cache_enabled


def _log_recall_query(query: str, filters: dict, n_requested: int, n_returned: int,
                      exec_time_ms: float, used_cache: bool, used_semantic_fallback: bool) -> None:
    """Log recall query for retrieval instrumentation (Phase 0).

    Args:
        query: Search query text (or None)
        filters: Dict of filters {type, tags, conf, tag_mode}
        n_requested: Number of results requested
        n_returned: Number of results actually returned
        exec_time_ms: Execution time in milliseconds
        used_cache: Whether cache was used
        used_semantic_fallback: Whether semantic fallback was triggered
    """
    if not _cache_available():
        return  # Logging requires cache

    try:
        log_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        filters_json = json.dumps(filters)

        state._cache_conn.execute("""
            INSERT INTO recall_logs
            (id, t, query, filters, n_requested, n_returned, exec_time_ms, used_cache, used_semantic_fallback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (log_id, now, query, filters_json, n_requested, n_returned, exec_time_ms,
              used_cache, used_semantic_fallback))
        state._cache_conn.commit()
    except Exception:
        pass  # Don't fail recall() if logging fails


def _cache_clear():
    """Clear all cached data (for testing/refresh)."""
    if not _cache_available():
        return
    try:
        state._cache_conn.executescript("""
            DELETE FROM memory_index;
            DELETE FROM memory_full;
            DELETE FROM config_cache;
            DELETE FROM cache_meta;
        """)
        state._cache_conn.commit()
    except Exception as e:
        print(f"Warning: Cache clear failed: {e}")


def _cache_populate_index(memories: list):
    """Populate memory_index from boot data (headlines only).

    v2.0.0: Uses priority instead of importance/salience.
    """
    if not _cache_available() or not memories:
        return

    try:
        for m in memories:
            tags = m.get('tags')
            if isinstance(tags, list):
                tags = json.dumps(tags)

            state._cache_conn.execute("""
                INSERT OR REPLACE INTO memory_index
                (id, type, t, tags, summary_preview, confidence, priority, session_id, last_accessed, access_count, has_full)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                m.get('id'),
                m.get('type'),
                m.get('t'),
                tags,
                m.get('summary_preview', m.get('summary', '')[:100]),
                m.get('confidence'),
                m.get('priority', 0),
                m.get('session_id'),
                m.get('last_accessed'),
                m.get('access_count', 0)
            ))
        state._cache_conn.commit()
    except Exception:
        pass  # Silent - cache is optional, don't pollute output


def _cache_populate_full(memories: list):
    """Populate memory_full and FTS5 with complete content (lazy-load target).

    v2.0.0: Simplified schema - removed entities, memory_class, valid_to, salience.
    """
    if not _cache_available() or not memories:
        return

    try:
        for m in memories:
            mem_id = m.get('id')
            summary = m.get('summary', '')
            tags = m.get('tags')
            if isinstance(tags, list):
                tags_str = ' '.join(tags)  # Space-separated for FTS5
            elif isinstance(tags, str):
                try:
                    tags_str = ' '.join(json.loads(tags))
                except json.JSONDecodeError:
                    tags_str = tags
            else:
                tags_str = ''

            # Update index to mark as having full content
            state._cache_conn.execute(
                "UPDATE memory_index SET has_full = 1 WHERE id = ?",
                (mem_id,)
            )

            # Store full content
            refs = m.get('refs')
            if isinstance(refs, list):
                refs = json.dumps(refs)

            state._cache_conn.execute("""
                INSERT OR REPLACE INTO memory_full
                (id, summary, refs, valid_from, access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                mem_id,
                summary,
                refs,
                m.get('valid_from'),
                m.get('access_count'),
                m.get('last_accessed')
            ))

            # Populate FTS5 for fast text search (v0.9.0)
            # FTS5 doesn't support INSERT OR REPLACE - use DELETE + INSERT
            state._cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (mem_id,))
            state._cache_conn.execute(
                "INSERT INTO memory_fts (id, summary, tags) VALUES (?, ?, ?)",
                (mem_id, summary, tags_str)
            )
        state._cache_conn.commit()
    except Exception:
        pass  # Silent - cache is optional, don't pollute output


def _cache_config(config_entries: list):
    """Cache config entries."""
    if not _cache_available() or not config_entries:
        return

    try:
        for c in config_entries:
            state._cache_conn.execute("""
                INSERT OR REPLACE INTO config_cache (key, value, category, boot_load)
                VALUES (?, ?, ?, ?)
            """, (c.get('key'), c.get('value'), c.get('category'), c.get('boot_load', 1)))
        state._cache_conn.commit()
    except Exception:
        pass  # Silent - cache is optional, don't pollute output


def _cache_query_index(search: str = None, type: str = None,
                       tags: list = None, n: int = 10,
                       conf: float = None, tag_mode: str = "any",
                       strict: bool = False, session_id: str = None,
                       since: str = None, until: str = None) -> list:
    """Query memory_index using FTS5 for text search (v0.9.0).

    When search is provided, uses FTS5 MATCH for ranked full-text search
    instead of LIKE. Results are ordered by BM25 relevance.

    Args:
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        strict: If True, skip ranking and order by timestamp DESC (v0.12.1)
        session_id: Filter by session identifier (v3.8.0, #237)
        since: Filter memories created at or after this ISO timestamp (v4.3.0, #281)
        until: Filter memories created at or before this ISO timestamp (v4.3.0, #281)

    Returns list of dicts with cache data. If has_full=0,
    full content needs to be fetched from Turso.
    """
    if not _cache_available():
        return []

    try:
        # v0.12.1: Strict mode - plain SQL with timestamp ordering (no ranking)
        if strict:
            conditions = []
            params = []

            if type:
                conditions.append("i.type = ?")
                params.append(type)
            if conf is not None:
                conditions.append("i.confidence >= ?")
                params.append(conf)
            if tags:
                # Match tags according to tag_mode
                tag_conds = []
                for t in tags:
                    tag_conds.append("i.tags LIKE ?")
                    params.append(f'%"{t}"%')
                join_op = ' AND ' if tag_mode == "all" else ' OR '
                conditions.append(f"({join_op.join(tag_conds)})")
            if session_id is not None:
                conditions.append("i.session_id = ?")
                params.append(session_id)
            if since is not None:
                conditions.append("i.t >= ?")
                params.append(since)
            if until is not None:
                conditions.append("i.t <= ?")
                params.append(until)

            where = " AND ".join(conditions) if conditions else "1=1"

            # Plain timestamp ordering - newest first
            cursor = state._cache_conn.execute(f"""
                SELECT i.*, f.summary, f.refs, f.valid_from, f.access_count, f.last_accessed
                FROM memory_index i
                LEFT JOIN memory_full f ON i.id = f.id
                WHERE {where}
                ORDER BY i.t DESC
                LIMIT ?
            """, params + [n])

            rows = cursor.fetchall()
            return [_cache_row_to_dict(row) for row in rows]

        if search:
            # Use FTS5 for ranked text search (v0.9.0)
            # Escape FTS5 special characters and add prefix matching
            fts_query = _escape_fts5_query(search)

            conditions = ["1=1"]
            params = [fts_query]

            if type:
                conditions.append("i.type = ?")
                params.append(type)
            if conf is not None:
                conditions.append("i.confidence >= ?")
                params.append(conf)
            if tags:
                # Match tags according to tag_mode
                tag_conds = []
                for t in tags:
                    tag_conds.append("i.tags LIKE ?")
                    params.append(f'%"{t}"%')
                join_op = ' AND ' if tag_mode == "all" else ' OR '
                conditions.append(f"({join_op.join(tag_conds)})")
            if session_id is not None:
                conditions.append("i.session_id = ?")
                params.append(session_id)
            if since is not None:
                conditions.append("i.t >= ?")
                params.append(since)
            if until is not None:
                conditions.append("i.t <= ?")
                params.append(until)

            where = " AND ".join(conditions)

            # v2.0.0: Composite ranking = BM25 * recency_weight * priority_weight
            # - recency_weight: 1 / (1 + days_since_access / 30)
            # - priority_weight: 1 + priority * 0.5 (so priority=-1 gives 0.5, priority=2 gives 2.0)
            cursor = state._cache_conn.execute(f"""
                SELECT i.*, f.summary, f.refs, f.valid_from, f.access_count, f.last_accessed,
                       bm25(memory_fts) as bm25_score,
                       bm25(memory_fts) *
                       (CASE
                           WHEN i.last_accessed IS NOT NULL
                           THEN 1.0 / (1.0 + (julianday('now') - julianday(i.last_accessed)) / 30.0)
                           ELSE 0.5
                       END) *
                       (1.0 + COALESCE(i.priority, 0) * 0.5) as composite_rank
                FROM memory_fts fts
                JOIN memory_index i ON fts.id = i.id
                LEFT JOIN memory_full f ON i.id = f.id
                WHERE memory_fts MATCH ?
                  AND {where}
                ORDER BY composite_rank
                LIMIT ?
            """, params + [n])
        else:
            # No search term - use simple index query
            conditions = []
            params = []

            if type:
                conditions.append("i.type = ?")
                params.append(type)
            if conf is not None:
                conditions.append("i.confidence >= ?")
                params.append(conf)
            if tags:
                # Match tags according to tag_mode
                tag_conds = []
                for t in tags:
                    tag_conds.append("i.tags LIKE ?")
                    params.append(f'%"{t}"%')
                join_op = ' AND ' if tag_mode == "all" else ' OR '
                conditions.append(f"({join_op.join(tag_conds)})")
            if session_id is not None:
                conditions.append("i.session_id = ?")
                params.append(session_id)
            if since is not None:
                conditions.append("i.t >= ?")
                params.append(since)
            if until is not None:
                conditions.append("i.t <= ?")
                params.append(until)

            where = " AND ".join(conditions) if conditions else "1=1"

            # v2.0.0: When no search, order by composite score using recency and priority
            # composite_score = recency_weight * priority_weight
            cursor = state._cache_conn.execute(f"""
                SELECT i.*, f.summary, f.refs, f.valid_from, f.access_count, f.last_accessed,
                       (CASE
                           WHEN i.last_accessed IS NOT NULL
                           THEN 1.0 / (1.0 + (julianday('now') - julianday(i.last_accessed)) / 30.0)
                           ELSE 1.0 / (1.0 + (julianday('now') - julianday(i.t)) / 30.0)
                       END) *
                       (1.0 + COALESCE(i.priority, 0) * 0.5) as composite_score
                FROM memory_index i
                LEFT JOIN memory_full f ON i.id = f.id
                WHERE {where}
                ORDER BY composite_score DESC
                LIMIT ?
            """, params + [n])

        rows = cursor.fetchall()
        return [_cache_row_to_dict(row) for row in rows]
    except Exception as e:
        print(f"Warning: Cache query failed: {e}")
        return []


def _escape_fts5_query(query: str) -> str:
    """Escape special FTS5 characters and format for search.

    FTS5 special chars: " * ( ) : ^
    We escape them and add prefix matching (*) for better UX.
    """
    # Remove FTS5 special characters that could break the query
    special_chars = '"*():^'
    escaped = query
    for char in special_chars:
        escaped = escaped.replace(char, ' ')

    # Split into words, filter empty, and add prefix matching
    words = [w.strip() for w in escaped.split() if w.strip()]
    if not words:
        return '""'  # Empty query - match nothing

    # Use OR between words with prefix matching for partial matches
    return ' OR '.join(f'"{w}"*' for w in words)


def _cache_row_to_dict(row: sqlite3.Row) -> dict:
    """Convert SQLite row to dict, parsing JSON fields."""
    d = dict(row)

    # Parse JSON fields
    for field in ('tags', 'entities', 'refs'):
        if field in d and d[field] is not None:
            if isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except json.JSONDecodeError:
                    d[field] = []

    return d


def _cache_memory(mem_id: str, what: str, type: str, now: str,
                  conf: float, tags: list, priority: int, **kwargs):
    """Cache a new memory (write-through), including FTS5 index.

    v2.0.0: Replaced importance/salience with priority field.
    v3.8.0: Added session_id caching (#237).
    """
    if not _cache_available():
        return

    try:
        tags_list = tags or []
        tags_json = json.dumps(tags_list)
        tags_str = ' '.join(tags_list)  # Space-separated for FTS5
        session_id = kwargs.get('session_id')

        # Insert into index
        state._cache_conn.execute("""
            INSERT OR REPLACE INTO memory_index
            (id, type, t, tags, summary_preview, confidence, priority, session_id, last_accessed, access_count, has_full)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (mem_id, type, now, tags_json, what[:100], conf, priority, session_id, None, 0))

        # Insert full content
        refs = kwargs.get('refs')
        if isinstance(refs, list):
            refs = json.dumps(refs)

        state._cache_conn.execute("""
            INSERT OR REPLACE INTO memory_full
            (id, summary, refs, valid_from, access_count)
            VALUES (?, ?, ?, ?, 0)
        """, (
            mem_id, what, refs,
            kwargs.get('valid_from', now)
        ))

        # Insert into FTS5 for fast text search (v0.9.0)
        # FTS5 doesn't support INSERT OR REPLACE - use DELETE + INSERT
        state._cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (mem_id,))
        state._cache_conn.execute(
            "INSERT INTO memory_fts (id, summary, tags) VALUES (?, ?, ?)",
            (mem_id, what, tags_str)
        )

        state._cache_conn.commit()
    except Exception as e:
        print(f"Warning: Cache write failed: {e}")


def _fetch_full_content(ids: list) -> list:
    """Fetch full content from Turso for cache misses."""
    if not ids:
        return []

    placeholders = ", ".join("?" * len(ids))
    return _exec(f"""
        SELECT * FROM memories
        WHERE id IN ({placeholders}) AND deleted_at IS NULL
    """, ids)


def cache_stats() -> dict:
    """Get cache statistics for debugging."""
    if not _cache_available():
        return {"enabled": False, "available": False}

    try:
        index_count = state._cache_conn.execute(
            "SELECT COUNT(*) FROM memory_index"
        ).fetchone()[0]
        full_count = state._cache_conn.execute(
            "SELECT COUNT(*) FROM memory_full"
        ).fetchone()[0]
        config_count = state._cache_conn.execute(
            "SELECT COUNT(*) FROM config_cache"
        ).fetchone()[0]
        initialized = state._cache_conn.execute(
            "SELECT value FROM cache_meta WHERE key = 'initialized_at'"
        ).fetchone()

        return {
            "enabled": state._cache_enabled,
            "available": True,
            "index_count": index_count,
            "full_count": full_count,
            "config_count": config_count,
            "hit_rate": f"{full_count}/{index_count}" if index_count else "0/0",
            "initialized_at": initialized[0] if initialized else None
        }
    except Exception as e:
        return {"enabled": state._cache_enabled, "available": False, "error": str(e)}


# v3.2.0: Retrieval observability helpers
def recall_stats(limit: int = 100) -> dict:
    """Get retrieval statistics from query logs.

    Returns aggregated statistics about recall queries including:
    - Total queries logged
    - Average execution time
    - Cache hit rate
    - Most common filters

    Args:
        limit: Maximum number of recent queries to analyze (default 100)

    Returns:
        Dict with aggregated statistics

    Example:
        >>> stats = recall_stats()
        >>> print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
        >>> print(f"Avg query time: {stats['avg_exec_time_ms']:.1f}ms")
    """
    if not _cache_available():
        return {"error": "Cache not available"}

    try:
        # Get recent queries
        logs = state._cache_conn.execute(f"""
            SELECT * FROM recall_logs
            ORDER BY t DESC
            LIMIT ?
        """, (limit,)).fetchall()

        if not logs:
            return {
                "total_queries": 0,
                "cache_hit_rate": 0.0,
                "avg_exec_time_ms": 0.0,
                "queries_analyzed": 0
            }

        total = len(logs)
        cache_hits = sum(1 for log in logs if log['used_cache'])
        exec_times = [log['exec_time_ms'] for log in logs if log['exec_time_ms']]

        return {
            "total_queries": total,
            "cache_hit_rate": cache_hits / total if total > 0 else 0.0,
            "avg_exec_time_ms": sum(exec_times) / len(exec_times) if exec_times else 0.0,
            "min_exec_time_ms": min(exec_times) if exec_times else 0.0,
            "max_exec_time_ms": max(exec_times) if exec_times else 0.0,
            "queries_analyzed": total
        }
    except Exception as e:
        return {"error": str(e)}


def top_queries(n: int = 10) -> list:
    """Get most common search queries from logs.

    Args:
        n: Number of top queries to return (default 10)

    Returns:
        List of dicts with query text and frequency

    Example:
        >>> for query_info in top_queries(5):
        ...     print(f"{query_info['query']}: {query_info['count']} times")
    """
    if not _cache_available():
        return []

    try:
        results = state._cache_conn.execute("""
            SELECT query, COUNT(*) as count
            FROM recall_logs
            WHERE query IS NOT NULL AND query != ''
            GROUP BY query
            ORDER BY count DESC
            LIMIT ?
        """, (n,)).fetchall()

        return [{"query": row['query'], "count": row['count']} for row in results]
    except Exception as e:
        return [{"error": str(e)}]


# Auto-init cache on module import if DB exists (v0.9.2 fix for cross-process cache)
# Fixes: remember() and recall() work across bash_tool calls
if state._CACHE_DB.exists() and state._cache_conn is None:
    try:
        _init_local_cache()
    except Exception:
        pass  # Fall back to network-only mode
