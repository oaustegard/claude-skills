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
_EMBEDDING_API_KEY = None

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
            -- Standalone table (not contentless) for simpler sync
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                id UNINDEXED,
                summary,
                tags
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

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_memory_index_type ON memory_index(type);
            CREATE INDEX IF NOT EXISTS idx_memory_index_t ON memory_index(t);
            CREATE INDEX IF NOT EXISTS idx_config_cache_category ON config_cache(category);
        """)
        _cache_conn.commit()

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
                       conf: float = None, tag_mode: str = "any") -> list:
    """Query memory_index using FTS5 for text search (v0.9.0).

    When search is provided, uses FTS5 MATCH for ranked full-text search
    instead of LIKE. Results are ordered by BM25 relevance.

    Args:
        tag_mode: "any" (default) matches any tag, "all" requires all tags

    Returns list of dicts with cache data. If has_full=0,
    full content needs to be fetched from Turso.
    """
    if not _cache_available():
        return []

    try:
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

            cursor = _cache_conn.execute(f"""
                SELECT i.*, f.summary, f.entities, f.refs, f.memory_class,
                       f.valid_from, f.valid_to, f.access_count, f.last_accessed,
                       bm25(memory_fts) as rank
                FROM memory_fts fts
                JOIN memory_index i ON fts.id = i.id
                LEFT JOIN memory_full f ON i.id = f.id
                WHERE memory_fts MATCH ?
                  AND {where}
                ORDER BY rank
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
            (id, type, t, tags, summary_preview, confidence, importance, has_full)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (mem_id, type, now, tags_json, what[:100], conf, importance))

        # Insert full content
        entities = kwargs.get('entities')
        refs = kwargs.get('refs')
        if isinstance(entities, list):
            entities = json.dumps(entities)
        if isinstance(refs, list):
            refs = json.dumps(refs)

        _cache_conn.execute("""
            INSERT OR REPLACE INTO memory_full
            (id, summary, entities, refs, memory_class, valid_from, access_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
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
    global _TOKEN, _HEADERS, _EMBEDDING_API_KEY
    if _TOKEN is None:
        # 1. Prefer environment variable (for Claude Code)
        _TOKEN = os.environ.get("TURSO_TOKEN")
        
        # 2. Fall back to .env file in project knowledge
        if not _TOKEN:
            env_file = _load_env_file(Path("/mnt/project/muninn.env"))
            _TOKEN = env_file.get("TURSO_TOKEN")
            # Also load embedding key from .env if present
            if _EMBEDDING_API_KEY is None:
                _EMBEDDING_API_KEY = env_file.get("EMBEDDING_API_KEY")
        
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

    if _EMBEDDING_API_KEY is None:
        _EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY")

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

def _embed(text: str) -> list[float] | None:
    """Generate embedding vector for text using OpenAI text-embedding-3-small.

    Returns list of 1536 floats, or None if API key not configured.
    Uses exponential backoff retry for 503/429 errors.
    """
    _init()
    if not _EMBEDDING_API_KEY:
        return None

    def _do_embed():
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {_EMBEDDING_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "text-embedding-3-small",
                "input": text
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]

    try:
        return _retry_with_backoff(_do_embed, max_retries=3, base_delay=1.0)
    except Exception as e:
        # Fail gracefully - embedding is optional
        print(f"Warning: Embedding generation failed after retries: {e}")
        return None

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
                  tags: list, entities: list, refs: list, embedding: list,
                  importance: float, memory_class: str, valid_from: str) -> None:
    """Internal helper: write memory to Turso (blocking)."""
    # vector32() doesn't accept NULL, so we use conditional SQL
    if embedding:
        _exec(
            """INSERT INTO memories (id, type, t, summary, confidence, tags, entities, refs,
               session_id, created_at, updated_at, embedding, importance, memory_class, valid_from, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, vector32(?), ?, ?, ?, 0)""",
            [mem_id, type, now, what, conf,
             json.dumps(tags or []), json.dumps(entities or []), json.dumps(refs or []),
             "session", now, now, json.dumps(embedding), importance, memory_class, valid_from]
        )
    else:
        # Insert without embedding when not available
        _exec(
            """INSERT INTO memories (id, type, t, summary, confidence, tags, entities, refs,
               session_id, created_at, updated_at, embedding, importance, memory_class, valid_from, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, 0)""",
            [mem_id, type, now, what, conf,
             json.dumps(tags or []), json.dumps(entities or []), json.dumps(refs or []),
             "session", now, now, importance, memory_class, valid_from]
        )

def remember(what: str, type: str, *, tags: list = None, conf: float = None,
             entities: list = None, refs: list = None, embed: bool = True,
             importance: float = None, memory_class: str = None, valid_from: str = None,
             sync: bool = True) -> str:
    """Store a memory with optional embedding. Type is required. Returns memory ID.

    Args:
        what: Memory content/summary
        type: Memory type (decision, world, anomaly, experience)
        tags: Optional list of tags
        conf: Optional confidence score (0.0-1.0)
        entities: Optional list of entities
        refs: Optional list of referenced memory IDs
        embed: Generate and store embedding for semantic search (default True)
        importance: Optional importance score (0.0-1.0, default 0.5)
        memory_class: Optional classification ('episodic' or 'semantic', default 'episodic')
        valid_from: Optional timestamp when fact became true (defaults to creation time)
        sync: If True (default), block until write completes. If False, write in background.
               Use sync=True for critical memories (handoffs, decisions). Use sync=False for
               fast writes where eventual consistency is acceptable.

    Returns:
        Memory ID (UUID)

    v0.6.0: Added sync parameter for background writes. Use flush() to wait for all pending writes.
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

    # Generate embedding if requested
    embedding = None
    if embed:
        embedding = _embed(what)

    # Write to local cache immediately (if available) - v0.7.0
    if _cache_available():
        _cache_memory(mem_id, what, type, now, conf, tags, importance,
                     entities=entities, refs=refs, memory_class=memory_class,
                     valid_from=valid_from)

    if sync:
        # Blocking write to Turso
        _write_memory(mem_id, what, type, now, conf, tags, entities, refs,
                     embedding, importance, memory_class, valid_from)
    else:
        # Background write to Turso
        def _bg_write():
            try:
                _write_memory(mem_id, what, type, now, conf, tags, entities, refs,
                            embedding, importance, memory_class, valid_from)
            finally:
                # Remove from pending list when done
                with _pending_writes_lock:
                    if thread in _pending_writes:
                        _pending_writes.remove(thread)

        thread = threading.Thread(target=_bg_write, daemon=True)
        with _pending_writes_lock:
            _pending_writes.append(thread)
        thread.start()

    return mem_id

def remember_bg(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None, embed: bool = True,
                importance: float = None, memory_class: str = None, valid_from: str = None) -> str:
    """Deprecated: Use remember(..., sync=False) instead.

    Fire-and-forget memory storage. Type required. Returns immediately, writes in background.

    Args:
        Same as remember(), including v0.4.0 parameters (importance, memory_class, valid_from).

    Returns:
        Memory ID (UUID)
    """
    return remember(what, type, tags=tags, conf=conf, entities=entities, refs=refs, embed=embed,
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
           use_cache: bool = True, semantic_fallback: bool = True,
           semantic_threshold: int = 2) -> list:
    """Query memories with flexible filters.

    v0.7.0: Uses local cache with progressive disclosure when available.
    v0.9.0: Uses FTS5 for ranked text search instead of LIKE.
            Adds semantic fallback when FTS5 returns few results.

    Args:
        search: Text to search for in memory summaries (FTS5 ranked search)
        n: Max number of results
        tags: Filter by tags
        type: Filter by memory type
        conf: Minimum confidence threshold
        tag_mode: "any" (default) matches any tag, "all" requires all tags
        use_cache: If True (default), check local cache first (much faster)
        semantic_fallback: If True (default), use semantic search when FTS5 returns
                          fewer than semantic_threshold results
        semantic_threshold: Trigger semantic fallback when FTS5 returns fewer
                           than this many results (default 2)
    """
    if isinstance(search, int):
        return _query(limit=search)

    # Try cache first (progressive disclosure)
    if use_cache and _cache_available():
        results = _cache_query_index(search=search, type=type, tags=tags, n=n, conf=conf, tag_mode=tag_mode)

        # Semantic fallback: if FTS5 returns few results and search was provided,
        # try semantic search to find conceptually related memories (v0.9.0)
        if search and semantic_fallback and len(results) < semantic_threshold:
            try:
                semantic_results = semantic_recall(search, n=n, type=type, conf=conf, tags=tags)
                # Merge results, preferring FTS5 matches (already ranked by relevance)
                seen_ids = {r['id'] for r in results}
                for sr in semantic_results:
                    if sr['id'] not in seen_ids:
                        results.append(sr)
                        seen_ids.add(sr['id'])
                        if len(results) >= n:
                            break
            except RuntimeError:
                # Semantic search not available (no API key) - continue with FTS5 results only
                pass

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

            return results

    # Fallback to direct Turso query
    return _query(search=search, tags=tags, type=type, conf=conf, limit=n, tag_mode=tag_mode)

def semantic_recall(query: str, *, n: int = 5, type: str = None,
                    conf: float = None, tags: list = None) -> list:
    """Find memories semantically similar to query using vector search.

    Requires EMBEDDING_API_KEY environment variable to be set.
    Returns memories ranked by cosine similarity.

    Args:
        query: Natural language query
        n: Max number of results (default 5)
        type: Filter by memory type
        conf: Minimum confidence threshold
        tags: Filter by tags (any match)

    Returns:
        List of memory dicts with added 'similarity' field (0.0-1.0)
    """
    # Generate embedding for query
    query_embedding = _embed(query)
    if not query_embedding:
        raise RuntimeError(
            "Semantic search requires EMBEDDING_API_KEY environment variable. "
            "Set it to an OpenAI API key to use text-embedding-3-small."
        )

    # Build WHERE clause for filters
    # Exclude soft-deleted memories, memories without embeddings, and superseded memories
    conditions = [
        "memories.deleted_at IS NULL",
        "memories.embedding IS NOT NULL",
        # Exclude memories that are superseded (appear in any other memory's refs field)
        "memories.id NOT IN (SELECT value FROM memories m2, json_each(m2.refs) WHERE m2.deleted_at IS NULL)"
    ]
    if type:
        conditions.append(f"memories.type = '{type}'")
    if conf is not None:
        conditions.append(f"memories.confidence >= {conf}")
    if tags:
        tag_conds = " OR ".join(f"memories.tags LIKE '%\"{t}\"%'" for t in tags)
        conditions.append(f"({tag_conds})")

    where = " AND ".join(conditions)

    # Use vector_top_k with index for efficient similarity search
    try:
        sql = f"""
            SELECT memories.*,
                   1 - vector_distance_cos(memories.embedding, vector32(?)) AS similarity
            FROM vector_top_k('memories_embedding_idx', vector32(?), {n * 2}) AS v
            JOIN memories ON memories.rowid = v.id
            WHERE {where}
            ORDER BY similarity DESC
            LIMIT {n}
        """
        results = _exec(sql, [json.dumps(query_embedding), json.dumps(query_embedding)])
    except Exception as e:
        # Fallback: If vector index not available, use brute-force similarity
        print(f"Warning: Vector index search failed, using fallback: {e}")
        sql = f"""
            SELECT memories.*,
                   1 - vector_distance_cos(memories.embedding, vector32(?)) AS similarity
            FROM memories
            WHERE {where}
            ORDER BY similarity DESC
            LIMIT {n}
        """
        results = _exec(sql, [json.dumps(query_embedding)])

    # Track access for returned memories
    if results:
        _update_access_tracking([m["id"] for m in results])

    return results

def _update_access_tracking(memory_ids: list):
    """Update access_count and last_accessed for memories (v0.4.0)."""
    if not memory_ids:
        return
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    # Use SQL to increment access_count and set last_accessed
    placeholders = ", ".join("?" * len(memory_ids))
    _exec(f"""
        UPDATE memories
        SET access_count = COALESCE(access_count, 0) + 1,
            last_accessed = ?
        WHERE id IN ({placeholders})
    """, [now] + memory_ids)

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
    return True

def supersede(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None) -> str:
    """Create a patch that supersedes an existing memory. Type required. Returns new memory ID.

    v0.4.0: Sets valid_to on original memory and valid_from on new memory for bitemporal tracking.
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Set valid_to on original memory to mark when it stopped being true
    _exec("UPDATE memories SET valid_to = ? WHERE id = ?", [now, original_id])

    # Create new memory with valid_from set to now
    return remember(summary, type, tags=tags, conf=conf, refs=[original_id], valid_from=now)

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

def boot_fast(journal_n: int = 5, index_n: int = 500,
              use_cache: bool = True) -> tuple[list, list, list]:
    """Optimized boot: returns (profile, ops, journal) in one HTTP request (~130ms).

    Use this instead of calling profile(), ops(), journal_recent() separately,
    which would make 3 HTTP requests (~1100ms total).

    v0.7.0: Also populates local SQLite cache with memory index for fast recall().

    Args:
        journal_n: Number of recent journal entries (default 5)
        index_n: Number of memory headlines to cache (default 500)
        use_cache: If True, populate local cache for fast subsequent queries

    Returns:
        Tuple of (profile_list, ops_list, journal_list)

    Performance:
        - Separate calls: ~1100ms (3 HTTP requests)
        - boot_fast(): ~130ms (1 HTTP request, 8x faster)
        - Subsequent recall(): <5ms (local cache) vs ~150ms (network)
    """
    # Initialize local cache if enabled
    if use_cache:
        _init_local_cache()

    # Fetch config + full memory content in single request
    results = _exec_batch([
        "SELECT * FROM config WHERE category = 'profile' ORDER BY key",
        "SELECT * FROM config WHERE category = 'ops' ORDER BY key",
        ("SELECT * FROM config WHERE category = 'journal' ORDER BY key DESC LIMIT ?", [journal_n]),
        # Full memory content: fetch everything to eliminate mid-conversation network calls
        ("""SELECT *
            FROM memories
            WHERE deleted_at IS NULL
              AND id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)
            ORDER BY t DESC LIMIT ?""", [index_n]),
    ])

    profile_data = results[0]
    ops_data = results[1]
    journal_raw = results[2]
    full_memories = results[3]

    # Parse journal entries
    journal_data = []
    for e in journal_raw:
        try:
            parsed = json.loads(e["value"])
            parsed["_key"] = e["key"]
            journal_data.append(parsed)
        except json.JSONDecodeError:
            continue

    # Populate local cache with full content
    if use_cache and _cache_available():
        _cache_config(profile_data + ops_data + journal_raw)

        # Create index entries from full memories
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

    return profile_data, ops_data, journal_data


def boot(journal_n: int = 5, decisions_n: int = 10, decisions_conf: float = 0.7) -> tuple[list, list, list, list]:
    """Single-call boot: returns (profile, ops, journal, decision_index) in one HTTP request.

    Decision index contains headlines only (id, timestamp, tags, first 60 chars).
    Use recall(type="decision") to fetch full decision text when needed.

    For faster boot without decision_index, use boot_fast() instead.

    Args:
        journal_n: Number of recent journal entries (default 5)
        decisions_n: Number of decision headlines (default 10)
        decisions_conf: Minimum confidence for decisions (default 0.7)

    Returns:
        Tuple of (profile_list, ops_list, journal_list, decision_index)
    """
    _init()
    resp = requests.post(
        f"{_URL}/v2/pipeline",
        headers=_HEADERS,
        json={"requests": [
            {"type": "execute", "stmt": {
                "sql": "SELECT * FROM config WHERE category = ? ORDER BY key",
                "args": [{"type": "text", "value": "profile"}]
            }},
            {"type": "execute", "stmt": {
                "sql": "SELECT * FROM config WHERE category = ? ORDER BY key",
                "args": [{"type": "text", "value": "ops"}]
            }},
            {"type": "execute", "stmt": {
                "sql": "SELECT * FROM config WHERE category = ? ORDER BY key DESC LIMIT ?",
                "args": [{"type": "text", "value": "journal"}, {"type": "integer", "value": str(journal_n)}]
            }},
            {"type": "execute", "stmt": {
                "sql": """SELECT id, t, tags, SUBSTR(summary, 1, 60) as headline
                         FROM memories
                         WHERE type = 'decision'
                           AND (confidence >= ? OR confidence IS NULL)
                           AND deleted_at IS NULL
                         ORDER BY t DESC LIMIT ?""",
                "args": [
                    {"type": "float", "value": str(decisions_conf)},
                    {"type": "integer", "value": str(decisions_n)}
                ]
            }},
        ]}
    ).json()

    def parse_result(r):
        if r["type"] != "ok":
            raise RuntimeError(f"Query failed: {r.get('error', 'unknown')}")
        res = r["response"]["result"]
        cols = [c["name"] for c in res["cols"]]
        return [
            {cols[i]: (row[i].get("value") if row[i].get("type") != "null" else None)
             for i in range(len(cols))}
            for row in res["rows"]
        ]

    results = resp.get("results", [])
    if len(results) != 4:
        raise RuntimeError(f"Expected 4 results, got {len(results)}")

    profile_data = parse_result(results[0])
    ops_data = parse_result(results[1])
    journal_raw = parse_result(results[2])
    decision_index = parse_result(results[3])

    # Parse journal entries
    journal_data = []
    for e in journal_raw:
        try:
            parsed = json.loads(e["value"])
            parsed["_key"] = e["key"]
            journal_data.append(parsed)
        except json.JSONDecodeError:
            continue

    # Parse decision JSON fields (tags, entities, refs)
    decision_index = [_parse_memory_row(d) for d in decision_index]

    return profile_data, ops_data, journal_data, decision_index

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
    sessions = recall(search="Therapy Session", type="experience", tags=["therapy"], n=1)
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

            # Note: embeddings are NOT regenerated on import - they're preserved from export
            # To regenerate embeddings, export without embedding field or set embed=True manually
            remember(
                m["summary"],
                m["type"],
                tags=tags,
                conf=m.get("confidence"),
                entities=entities,
                refs=refs,
                embed=False  # Don't regenerate embeddings on import
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
    "remember", "recall", "forget", "supersede", "remember_bg", "flush", "semantic_recall",  # memories
    "recall_since", "recall_between",  # date-filtered queries
    "config_get", "config_set", "config_delete", "config_list",  # config
    "profile", "ops", "boot", "boot_fast", "journal", "journal_recent", "journal_prune",  # convenience loaders
    "therapy_scope", "therapy_session_count", "decisions_recent",  # therapy helpers
    "group_by_type", "group_by_tag",  # analysis helpers
    "handoff_pending", "handoff_complete",  # handoff workflow
    "muninn_export", "muninn_import",  # export/import
    "cache_stats",  # v0.7.0 cache diagnostics
    "r", "q", "j", "TYPES"  # aliases & constants
]
