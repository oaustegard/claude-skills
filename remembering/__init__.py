"""Remembering - Minimal persistent memory for Claude."""

import requests
import json
import uuid
import threading
import os
import time
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

_URL = "https://assistant-memory-oaustegard.aws-us-east-1.turso.io"
_TOKEN = None
_HEADERS = None

# Valid memory types (profile now lives in config table)
TYPES = {"decision", "world", "anomaly", "experience"}

# Track pending background writes for flush()
_pending_writes = []
_pending_writes_lock = threading.Lock()

# =========================================================================
# Local SQLite Cache (v0.7.0) - Progressive Disclosure
# =========================================================================
# Cache stores:
# - memory_index: Headlines only (id, type, t, tags, summary_preview, confidence)
# - memory_full: Full content, lazy-loaded on demand
# - config_cache: Full config (small, always populated)
#
# Benefits:
# - Boot: Single Turso round-trip populates index
# - Recall: Local queries <5ms vs 150ms network
# - Progressive: Full content fetched only when needed
# =========================================================================

_CACHE_DIR = Path.home() / ".muninn"
_CACHE_DB = _CACHE_DIR / "cache.db"
_cache_conn = None
_cache_enabled = True  # Can be disabled for testing


def _init_local_cache() -> bool:
    """Initialize local SQLite cache. Returns True if successful."""
    global _cache_conn
    if _cache_conn is not None:
        return True  # Already initialized

    if not _cache_enabled:
        return False

    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_conn = sqlite3.connect(str(_CACHE_DB), check_same_thread=False)
        _cache_conn.row_factory = sqlite3.Row

        # Create schema
        _cache_conn.executescript("""
            -- Index: populated at boot, headlines only
            CREATE TABLE IF NOT EXISTS memory_index (
                id TEXT PRIMARY KEY,
                type TEXT,
                t TEXT,
                tags TEXT,              -- JSON array
                summary_preview TEXT,   -- First 100 chars
                confidence REAL,
                importance REAL,
                salience REAL,          -- v0.9.2: for composite ranking
                last_accessed TEXT,     -- v0.9.2: for recency weight
                access_count INTEGER,   -- v0.9.2: for access weight
                has_full INTEGER DEFAULT 0
            );

            -- Full content: lazy-loaded on demand
            CREATE TABLE IF NOT EXISTS memory_full (
                id TEXT PRIMARY KEY,
                summary TEXT,
                entities TEXT,
                refs TEXT,
                memory_class TEXT,
                valid_from TEXT,
                valid_to TEXT,
                access_count INTEGER,
                last_accessed TEXT,
                salience REAL
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
                category TEXT
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
        _cache_conn.commit()

        # v0.13.0: Migrate FTS5 to Porter stemmer if needed
        # Check if FTS5 table needs rebuilding (check for porter tokenizer)
        try:
            # Try to get the FTS5 table info - if it exists with wrong tokenizer, rebuild
            meta_check = _cache_conn.execute(
                "SELECT value FROM cache_meta WHERE key = 'fts5_porter_migrated'"
            ).fetchone()

            if not meta_check:
                # Migration needed - rebuild FTS5 with Porter stemmer
                print("Migrating FTS5 to Porter stemmer...")
                _cache_conn.execute("DROP TABLE IF EXISTS memory_fts")
                _cache_conn.execute("""
                    CREATE VIRTUAL TABLE memory_fts USING fts5(
                        id UNINDEXED,
                        summary,
                        tags,
                        tokenize='porter unicode61'
                    )
                """)
                # Mark migration complete
                _cache_conn.execute(
                    "INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)",
                    ("fts5_porter_migrated", "true")
                )
                _cache_conn.commit()
                print("FTS5 migration complete. Cache will repopulate on next boot.")
        except Exception as e:
            print(f"Warning: FTS5 migration check failed: {e}")

        # Store initialization timestamp
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        _cache_conn.execute(
            "INSERT OR REPLACE INTO cache_meta (key, value) VALUES (?, ?)",
            ("initialized_at", now)
        )
        _cache_conn.commit()
        return True
    except Exception as e:
        print(f"Warning: Cache initialization failed: {e}")
        _cache_conn = None
        return False


def _cache_available() -> bool:
    """Check if local cache is initialized and healthy."""
    return _cache_conn is not None and _cache_enabled


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

        _cache_conn.execute("""
            INSERT INTO recall_logs
            (id, t, query, filters, n_requested, n_returned, exec_time_ms, used_cache, used_semantic_fallback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (log_id, now, query, filters_json, n_requested, n_returned, exec_time_ms,
              used_cache, used_semantic_fallback))
        _cache_conn.commit()
    except Exception:
        pass  # Don't fail recall() if logging fails


# Auto-init cache on module import if DB exists (v0.9.2 fix for cross-process cache)
# Fixes: remember() and recall() work across bash_tool calls
if _CACHE_DB.exists() and _cache_conn is None:
    try:
        _init_local_cache()
    except Exception:
        pass  # Fall back to network-only mode


def _cache_clear():
    """Clear all cached data (for testing/refresh)."""
    if not _cache_available():
        return
    try:
        _cache_conn.executescript("""
            DELETE FROM memory_index;
            DELETE FROM memory_full;
            DELETE FROM config_cache;
            DELETE FROM cache_meta;
        """)
        _cache_conn.commit()
    except Exception as e:
        print(f"Warning: Cache clear failed: {e}")


def _cache_populate_index(memories: list):
    """Populate memory_index from boot data (headlines only)."""
    if not _cache_available() or not memories:
        return

    try:
        for m in memories:
            tags = m.get('tags')
            if isinstance(tags, list):
                tags = json.dumps(tags)

            _cache_conn.execute("""
                INSERT OR REPLACE INTO memory_index
                (id, type, t, tags, summary_preview, confidence, importance, salience, last_accessed, access_count, has_full)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                m.get('id'),
                m.get('type'),
                m.get('t'),
                tags,
                m.get('summary_preview', m.get('summary', '')[:100]),
                m.get('confidence'),
                m.get('importance'),
                m.get('salience', 1.0),
                m.get('last_accessed'),
                m.get('access_count', 0)
            ))
        _cache_conn.commit()
    except Exception as e:
        print(f"Warning: Cache index population failed: {e}")


def _cache_populate_full(memories: list):
    """Populate memory_full and FTS5 with complete content (lazy-load target)."""
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
            _cache_conn.execute(
                "UPDATE memory_index SET has_full = 1 WHERE id = ?",
                (mem_id,)
            )

            # Store full content
            entities = m.get('entities')
            if isinstance(entities, list):
                entities = json.dumps(entities)
            refs = m.get('refs')
            if isinstance(refs, list):
                refs = json.dumps(refs)

            _cache_conn.execute("""
                INSERT OR REPLACE INTO memory_full
                (id, summary, entities, refs, memory_class, valid_from, valid_to, access_count, last_accessed, salience)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id,
                summary,
                entities,
                refs,
                m.get('memory_class'),
                m.get('valid_from'),
                m.get('valid_to'),
                m.get('access_count'),
                m.get('last_accessed'),
                m.get('salience', 1.0)
            ))

            # Populate FTS5 for fast text search (v0.9.0)
            # FTS5 doesn't support INSERT OR REPLACE - use DELETE + INSERT
            _cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (mem_id,))
            _cache_conn.execute(
                "INSERT INTO memory_fts (id, summary, tags) VALUES (?, ?, ?)",
                (mem_id, summary, tags_str)
            )
        _cache_conn.commit()
    except Exception as e:
        print(f"Warning: Cache full population failed: {e}")


def _cache_config(config_entries: list):
    """Cache config entries."""
    if not _cache_available() or not config_entries:
        return

    try:
        for c in config_entries:
            _cache_conn.execute("""
                INSERT OR REPLACE INTO config_cache (key, value, category)
                VALUES (?, ?, ?)
            """, (c.get('key'), c.get('value'), c.get('category')))
        _cache_conn.commit()
    except Exception as e:
        print(f"Warning: Config caching failed: {e}")


def _cache_query_index(search: str = None, type: str = None,
                       tags: list = None, n: int = 10,
                       conf: float = None, tag_mode: str = "any",
                       strict: bool = False) -> list:
    """Query memory_index using FTS5 for text search (v0.9.0).

    When search is provided, uses FTS5 MATCH for ranked full-text search
    instead of LIKE. Results are ordered by BM25 relevance.

    Args:
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        strict: If True, skip ranking and order by timestamp DESC (v0.12.1)

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

            where = " AND ".join(conditions) if conditions else "1=1"

            # Plain timestamp ordering - newest first
            cursor = _cache_conn.execute(f"""
                SELECT i.*, f.summary, f.entities, f.refs, f.memory_class,
                       f.valid_from, f.valid_to, f.access_count, f.last_accessed
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

            where = " AND ".join(conditions)

            # v0.10.0: Composite ranking = BM25 * recency_weight * access_weight * salience
            # - recency_weight: 1 / (1 + days_since_access / 30)
            # - access_weight: log(access_count + 1)  [natural log]
            # - salience: therapy-adjustable multiplier
            cursor = _cache_conn.execute(f"""
                SELECT i.*, f.summary, f.entities, f.refs, f.memory_class,
                       f.valid_from, f.valid_to, f.access_count, f.last_accessed,
                       bm25(memory_fts) as bm25_score,
                       bm25(memory_fts) *
                       COALESCE(i.salience, 1.0) *
                       (CASE
                           WHEN i.last_accessed IS NOT NULL
                           THEN 1.0 / (1.0 + (julianday('now') - julianday(i.last_accessed)) / 30.0)
                           ELSE 0.5
                       END) *
                       (1.0 + ln(1.0 + COALESCE(i.access_count, 0))) as composite_rank
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

            where = " AND ".join(conditions) if conditions else "1=1"

            # v0.10.0: When no search, order by composite score using recency from 't'
            # composite_score = salience * recency_weight * access_weight
            cursor = _cache_conn.execute(f"""
                SELECT i.*, f.summary, f.entities, f.refs, f.memory_class,
                       f.valid_from, f.valid_to, f.access_count, f.last_accessed,
                       COALESCE(i.salience, 1.0) *
                       (CASE
                           WHEN i.last_accessed IS NOT NULL
                           THEN 1.0 / (1.0 + (julianday('now') - julianday(i.last_accessed)) / 30.0)
                           ELSE 1.0 / (1.0 + (julianday('now') - julianday(i.t)) / 30.0)
                       END) *
                       (1.0 + ln(1.0 + COALESCE(i.access_count, 0))) as composite_score
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
                  conf: float, tags: list, importance: float, **kwargs):
    """Cache a new memory (write-through), including FTS5 index."""
    if not _cache_available():
        return

    try:
        tags_list = tags or []
        tags_json = json.dumps(tags_list)
        tags_str = ' '.join(tags_list)  # Space-separated for FTS5

        # Insert into index
        _cache_conn.execute("""
            INSERT OR REPLACE INTO memory_index
            (id, type, t, tags, summary_preview, confidence, importance, salience, last_accessed, access_count, has_full)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (mem_id, type, now, tags_json, what[:100], conf, importance, 1.0, None, 0))

        # Insert full content
        entities = kwargs.get('entities')
        refs = kwargs.get('refs')
        if isinstance(entities, list):
            entities = json.dumps(entities)
        if isinstance(refs, list):
            refs = json.dumps(refs)

        _cache_conn.execute("""
            INSERT OR REPLACE INTO memory_full
            (id, summary, entities, refs, memory_class, valid_from, access_count, salience)
            VALUES (?, ?, ?, ?, ?, ?, 0, 1.0)
        """, (
            mem_id, what, entities, refs,
            kwargs.get('memory_class', 'episodic'),
            kwargs.get('valid_from', now)
        ))

        # Insert into FTS5 for fast text search (v0.9.0)
        # FTS5 doesn't support INSERT OR REPLACE - use DELETE + INSERT
        _cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (mem_id,))
        _cache_conn.execute(
            "INSERT INTO memory_fts (id, summary, tags) VALUES (?, ?, ?)",
            (mem_id, what, tags_str)
        )

        _cache_conn.commit()
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
        index_count = _cache_conn.execute(
            "SELECT COUNT(*) FROM memory_index"
        ).fetchone()[0]
        full_count = _cache_conn.execute(
            "SELECT COUNT(*) FROM memory_full"
        ).fetchone()[0]
        config_count = _cache_conn.execute(
            "SELECT COUNT(*) FROM config_cache"
        ).fetchone()[0]
        initialized = _cache_conn.execute(
            "SELECT value FROM cache_meta WHERE key = 'initialized_at'"
        ).fetchone()

        return {
            "enabled": _cache_enabled,
            "available": True,
            "index_count": index_count,
            "full_count": full_count,
            "config_count": config_count,
            "hit_rate": f"{full_count}/{index_count}" if index_count else "0/0",
            "initialized_at": initialized[0] if initialized else None
        }
    except Exception as e:
        return {"enabled": _cache_enabled, "available": False, "error": str(e)}

def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Ignores comments and blank lines."""
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                env[key.strip()] = value.strip()
    return env


def _init():
    """Lazy-load credentials from environment, .env file, or legacy project file."""
    global _TOKEN, _HEADERS
    if _TOKEN is None:
        # 1. Prefer environment variable (for Claude Code)
        _TOKEN = os.environ.get("TURSO_TOKEN")

        # 2. Fall back to .env file in project knowledge
        if not _TOKEN:
            env_file = _load_env_file(Path("/mnt/project/muninn.env"))
            _TOKEN = env_file.get("TURSO_TOKEN")

        # 3. Legacy fallback to separate token file
        if not _TOKEN:
            token_path = Path("/mnt/project/turso-token.txt")
            if token_path.exists():
                _TOKEN = token_path.read_text().strip()

        if not _TOKEN:
            raise RuntimeError("No TURSO_TOKEN in environment, /mnt/project/muninn.env, or /mnt/project/turso-token.txt")

        # Clean token: remove whitespace that may be present
        _TOKEN = _TOKEN.strip().replace(" ", "")
        _HEADERS = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}

def _retry_with_backoff(fn, max_retries=3, base_delay=1.0):
    """Retry a function with exponential backoff on 503/429 errors.

    Args:
        fn: Callable that may raise exceptions
        max_retries: Maximum number of retry attempts (default 3)
        base_delay: Initial delay in seconds (default 1.0)

    Returns:
        Result of fn() if successful

    Raises:
        Last exception if all retries exhausted
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt == max_retries - 1:
                # Last attempt failed, re-raise
                raise
            # Check if it's a retriable error (503 Service Unavailable, 429 Too Many Requests)
            error_str = str(e)
            if '503' in error_str or '429' in error_str or 'Service Unavailable' in error_str:
                delay = base_delay * (2 ** attempt)
                print(f"Warning: API request failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                # Non-retriable error, fail immediately
                raise

def _parse_memory_row(row: dict) -> dict:
    """Parse JSON fields in a memory row (tags, entities, refs).

    Args:
        row: Raw row dict from database

    Returns:
        Row dict with parsed JSON fields
    """
    # Parse tags field
    if 'tags' in row and row['tags'] is not None:
        if isinstance(row['tags'], str):
            try:
                row['tags'] = json.loads(row['tags'])
            except json.JSONDecodeError:
                row['tags'] = []

    # Parse entities field
    if 'entities' in row and row['entities'] is not None:
        if isinstance(row['entities'], str):
            try:
                row['entities'] = json.loads(row['entities'])
            except json.JSONDecodeError:
                row['entities'] = []

    # Parse refs field
    if 'refs' in row and row['refs'] is not None:
        if isinstance(row['refs'], str):
            try:
                row['refs'] = json.loads(row['refs'])
            except json.JSONDecodeError:
                row['refs'] = []

    return row

def _exec_batch(statements: list) -> list:
    """Execute multiple SQL statements in a single pipeline request.

    Args:
        statements: List of SQL strings or (sql, args) tuples

    Returns:
        List of result lists (one per statement)

    Example:
        results = _exec_batch([
            "SELECT * FROM config WHERE category = 'profile'",
            ("SELECT * FROM memories WHERE type = ?", ["decision"])
        ])
        profile_data = results[0]
        decisions = results[1]
    """
    _init()
    requests_list = []

    for stmt in statements:
        if isinstance(stmt, tuple):
            sql, args = stmt
        else:
            sql, args = stmt, []

        request = {"type": "execute", "stmt": {"sql": sql}}
        if args:
            request["stmt"]["args"] = [
                {"type": "text", "value": str(v)} if v is not None else {"type": "null"}
                for v in args
            ]
        requests_list.append(request)

    # Add close request
    requests_list.append({"type": "close"})

    resp = requests.post(
        f"{_URL}/v2/pipeline",
        headers=_HEADERS,
        json={"requests": requests_list}
    ).json()

    # Parse results (exclude the close response)
    results = []
    for r in resp.get("results", [])[:-1]:  # Exclude close result
        if r["type"] != "ok":
            error_msg = r.get("error", {}).get("message", "Unknown error")
            error_code = r.get("error", {}).get("code", "UNKNOWN")
            raise RuntimeError(f"Database error [{error_code}]: {error_msg}")

        res = r["response"]["result"]
        cols = [c["name"] for c in res["cols"]]
        rows = [
            {cols[i]: (row[i].get("value") if row[i].get("type") != "null" else None)
             for i in range(len(cols))}
            for row in res["rows"]
        ]

        # Parse JSON fields if this is a memory query
        if rows and 'tags' in rows[0]:
            rows = [_parse_memory_row(row) for row in rows]

        results.append(rows)

    return results

def _exec(sql, args=None, parse_json: bool = True):
    """Execute SQL, return list of dicts.

    Args:
        sql: SQL query
        args: Query arguments
        parse_json: If True, parse JSON fields (tags, entities, refs) in memory rows
    """
    _init()
    stmt = {"sql": sql}
    if args:
        stmt["args"] = [
            {"type": "text", "value": str(v)} if v is not None else {"type": "null"}
            for v in args
        ]
    resp = requests.post(
        f"{_URL}/v2/pipeline",
        headers=_HEADERS,
        json={"requests": [{"type": "execute", "stmt": stmt}]}
    ).json()

    r = resp["results"][0]
    if r["type"] != "ok":
        error_msg = r.get("error", {}).get("message", "Unknown error")
        error_code = r.get("error", {}).get("code", "UNKNOWN")
        raise RuntimeError(f"Database error [{error_code}]: {error_msg}")

    res = r["response"]["result"]
    cols = [c["name"] for c in res["cols"]]
    rows = [
        {cols[i]: (row[i].get("value") if row[i].get("type") != "null" else None) for i in range(len(cols))}
        for row in res["rows"]
    ]

    # Parse JSON fields if this is a memory query
    if parse_json and rows and 'tags' in rows[0]:
        rows = [_parse_memory_row(row) for row in rows]

    return rows

def _write_memory(mem_id: str, what: str, type: str, now: str, conf: float,
                  tags: list, entities: list, refs: list,
                  importance: float, memory_class: str, valid_from: str) -> None:
    """Internal helper: write memory to Turso (blocking)."""
    # Insert without embedding (embeddings removed in v0.13.0)
    _exec(
        """INSERT INTO memories (id, type, t, summary, confidence, tags, entities, refs,
           session_id, created_at, updated_at, embedding, importance, memory_class, valid_from, access_count, salience)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, 0, 1.0)""",
        [mem_id, type, now, what, conf,
         json.dumps(tags or []), json.dumps(entities or []), json.dumps(refs or []),
         "session", now, now, importance, memory_class, valid_from]
    )

def remember(what: str, type: str, *, tags: list = None, conf: float = None,
             entities: list = None, refs: list = None,
             importance: float = None, memory_class: str = None, valid_from: str = None,
             sync: bool = True) -> str:
    """Store a memory. Type is required. Returns memory ID.

    Args:
        what: Memory content/summary
        type: Memory type (decision, world, anomaly, experience)
        tags: Optional list of tags
        conf: Optional confidence score (0.0-1.0)
        entities: Optional list of entities
        refs: Optional list of referenced memory IDs
        importance: Optional importance score (0.0-1.0, default 0.5)
        memory_class: Optional classification ('episodic' or 'semantic', default 'episodic')
        valid_from: Optional timestamp when fact became true (defaults to creation time)
        sync: If True (default), block until write completes. If False, write in background.
               Use sync=True for critical memories (handoffs, decisions). Use sync=False for
               fast writes where eventual consistency is acceptable.

    Returns:
        Memory ID (UUID)

    v0.6.0: Added sync parameter for background writes. Use flush() to wait for all pending writes.
    v0.13.0: Removed embedding generation (OpenAI dependency removed).
    """
    if type not in TYPES:
        raise ValueError(f"Invalid type '{type}'. Must be one of: {', '.join(sorted(TYPES))}")

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mem_id = str(uuid.uuid4())

    if type == "decision" and conf is None:
        conf = 0.8

    # Set v0.4.0 defaults
    if importance is None:
        importance = 0.5
    if memory_class is None:
        memory_class = 'episodic'
    if valid_from is None:
        valid_from = now

    # Write to local cache immediately (if available) - v0.7.0
    if _cache_available():
        _cache_memory(mem_id, what, type, now, conf, tags, importance,
                     entities=entities, refs=refs, memory_class=memory_class,
                     valid_from=valid_from)

    if sync:
        # Blocking write to Turso
        _write_memory(mem_id, what, type, now, conf, tags, entities, refs,
                     importance, memory_class, valid_from)
    else:
        # Background write to Turso
        def _bg_write():
            try:
                _write_memory(mem_id, what, type, now, conf, tags, entities, refs,
                            importance, memory_class, valid_from)
            finally:
                # Remove from pending list when done
                with _pending_writes_lock:
                    if thread in _pending_writes:
                        _pending_writes.remove(thread)

        thread = threading.Thread(target=_bg_write, daemon=True)
        with _pending_writes_lock:
            _pending_writes.append(thread)
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
    with _pending_writes_lock:
        threads = list(_pending_writes)  # Copy list

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
    if use_cache and _cache_available():
        results = _cache_query_index(search=search, type=type, tags=tags, n=n, conf=conf, tag_mode=tag_mode, strict=strict)

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
                        r.update({
                            'summary': full.get('summary'),
                            'entities': full.get('entities'),
                            'refs': full.get('refs'),
                            'memory_class': full.get('memory_class'),
                            'valid_from': full.get('valid_from'),
                            'valid_to': full.get('valid_to'),
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
                _cache_conn.execute("""
                    UPDATE memory_index
                    SET access_count = COALESCE(access_count, 0) + 1,
                        last_accessed = ?
                    WHERE id = ?
                """, (now, mem_id))

                # Update memory_full
                _cache_conn.execute("""
                    UPDATE memory_full
                    SET access_count = COALESCE(access_count, 0) + 1,
                        last_accessed = ?
                    WHERE id = ?
                """, (now, mem_id))

            _cache_conn.commit()
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
            _cache_conn.execute("DELETE FROM memory_index WHERE id = ?", (memory_id,))
            _cache_conn.execute("DELETE FROM memory_full WHERE id = ?", (memory_id,))
            _cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (memory_id,))
            _cache_conn.commit()
        except Exception as e:
            print(f"Warning: Failed to invalidate cache for {memory_id}: {e}")

    return True

def supersede(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None) -> str:
    """Create a patch that supersedes an existing memory. Type required. Returns new memory ID.

    v0.4.0: Sets valid_to on original memory and valid_from on new memory for bitemporal tracking.
    v0.13.0: Invalidates cache for superseded memory.
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Set valid_to on original memory to mark when it stopped being true
    _exec("UPDATE memories SET valid_to = ? WHERE id = ?", [now, original_id])

    # Invalidate cache for superseded memory (v0.13.0 bugfix)
    # Superseded memories should not appear in recall() results
    if _cache_available():
        try:
            _cache_conn.execute("DELETE FROM memory_index WHERE id = ?", (original_id,))
            _cache_conn.execute("DELETE FROM memory_full WHERE id = ?", (original_id,))
            _cache_conn.execute("DELETE FROM memory_fts WHERE id = ?", (original_id,))
            _cache_conn.commit()
        except Exception as e:
            print(f"Warning: Failed to invalidate cache for superseded memory {original_id}: {e}")

    # Create new memory with valid_from set to now
    return remember(summary, type, tags=tags, conf=conf, refs=[original_id], valid_from=now)

# --- Salience adjustment functions (v0.10.0) ---

def strengthen(memory_id: str, factor: float = 1.5) -> None:
    """Boost salience for a memory (therapy/consolidation use).

    Increases salience by multiplying current value by factor.
    Used during therapy sessions to reinforce confirmed patterns.

    Args:
        memory_id: Memory UUID
        factor: Multiplication factor (default 1.5, higher = stronger boost)

    Example:
        strengthen("abc-123", factor=2.0)  # Double the salience
    """
    if factor <= 0:
        raise ValueError("Factor must be positive")

    # Update Turso database
    _exec("""
        UPDATE memories
        SET salience = COALESCE(salience, 1.0) * ?
        WHERE id = ?
    """, [factor, memory_id])

    # Update cache if available
    if _cache_available():
        try:
            _cache_conn.execute("""
                UPDATE memory_index
                SET salience = COALESCE(salience, 1.0) * ?
                WHERE id = ?
            """, (factor, memory_id))

            _cache_conn.execute("""
                UPDATE memory_full
                SET salience = COALESCE(salience, 1.0) * ?
                WHERE id = ?
            """, (factor, memory_id))

            _cache_conn.commit()
        except Exception as e:
            print(f"Warning: Cache salience update failed: {e}")


def weaken(memory_id: str, factor: float = 0.5) -> None:
    """Reduce salience for a memory (therapy/consolidation use).

    Decreases salience by multiplying current value by factor.
    Used during therapy sessions to downrank noise or obsolete memories.

    Args:
        memory_id: Memory UUID
        factor: Multiplication factor (default 0.5, lower = weaker)

    Example:
        weaken("xyz-789", factor=0.25)  # Reduce to 25% salience
    """
    if factor <= 0 or factor >= 1:
        raise ValueError("Factor must be between 0 and 1")

    # Update Turso database
    _exec("""
        UPDATE memories
        SET salience = COALESCE(salience, 1.0) * ?
        WHERE id = ?
    """, [factor, memory_id])

    # Update cache if available
    if _cache_available():
        try:
            _cache_conn.execute("""
                UPDATE memory_index
                SET salience = COALESCE(salience, 1.0) * ?
                WHERE id = ?
            """, (factor, memory_id))

            _cache_conn.execute("""
                UPDATE memory_full
                SET salience = COALESCE(salience, 1.0) * ?
                WHERE id = ?
            """, (factor, memory_id))

            _cache_conn.commit()
        except Exception as e:
            print(f"Warning: Cache salience update failed: {e}")


# --- Config table functions (profile + ops) ---

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

def config_list(category: str = None) -> list:
    """List config entries, optionally filtered by category."""
    if category:
        return _exec("SELECT * FROM config WHERE category = ? ORDER BY key", [category])
    return _exec("SELECT * FROM config ORDER BY category, key")

def profile() -> list:
    """Load profile config for conversation start."""
    return config_list("profile")

def ops() -> list:
    """Load operational config for conversation start."""
    return config_list("ops")


def _warm_cache():
    """Background cache population - fetches all memories from Turso."""
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
                    'importance': m.get('importance')
                })
            _cache_populate_index(memory_index)
            _cache_populate_full(full_memories)
    except Exception:
        pass  # Cache warming is best-effort


def boot() -> str:
    """Boot sequence: load profile + ops, start async cache population.

    Returns formatted string with complete profile and ops values.
    Spawns background thread to populate memory cache for fast recall().
    """
    import threading

    # Initialize cache
    _init_local_cache()

    # Fetch only profile + ops (fast, small query)
    results = _exec_batch([
        "SELECT * FROM config WHERE category = 'profile' ORDER BY key",
        "SELECT * FROM config WHERE category = 'ops' ORDER BY key",
    ])
    profile_data = results[0]
    ops_data = results[1]

    # Cache config immediately
    if _cache_available():
        _cache_config(profile_data + ops_data)

    # Start async cache warming
    threading.Thread(target=_warm_cache, daemon=True).start()

    # Format output
    output = []
    if profile_data:
        output.append("=== PROFILE ===")
        for p in profile_data:
            output.append(f"{p['key']}:\n{p['value']}")

    if ops_data:
        output.append("\n=== OPS ===")
        for o in ops_data:
            output.append(f"{o['key']}:\n{o['value']}")

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

# Short aliases
r = remember
q = recall
j = journal

__all__ = [
    "remember", "recall", "forget", "supersede", "remember_bg", "flush",  # memories
    "recall_since", "recall_between",  # date-filtered queries
    "config_get", "config_set", "config_delete", "config_list",  # config
    "profile", "ops", "boot", "boot_fast", "journal", "journal_recent", "journal_prune",  # convenience loaders
    "therapy_scope", "therapy_session_count", "decisions_recent",  # therapy helpers
    "group_by_type", "group_by_tag",  # analysis helpers
    "handoff_pending", "handoff_complete",  # handoff workflow
    "muninn_export", "muninn_import",  # export/import
    "cache_stats",  # v0.7.0 cache diagnostics
    "strengthen", "weaken",  # v0.10.0 salience adjustment
    "r", "q", "j", "TYPES"  # aliases & constants
]
