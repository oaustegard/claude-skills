"""
Turso HTTP API layer for remembering skill.

This module handles:
- Credential initialization via env files, configuring skill, or env vars (_init)
- HTTP request retry logic (_retry_with_backoff)
- SQL execution via Turso HTTP API (_exec, _exec_batch)
- JSON field parsing (_parse_memory_row)

Imports from: state
"""

import importlib
import importlib.util
import json
import os
import time
import requests
from pathlib import Path

from . import state


# Well-known env file locations, searched in priority order (#263)
_ENV_FILE_PATHS = [
    Path("/mnt/project/turso.env"),
    Path("/mnt/project/muninn.env"),
    Path.home() / ".muninn" / ".env",
]


def _load_env_file(path: Path) -> dict:
    """Parse a simple KEY=VALUE env file, ignoring comments and blank lines.

    Args:
        path: Path to the env file

    Returns:
        Dict of key-value pairs found in the file
    """
    env = {}
    if not path.exists():
        return env
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes if present
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[key] = value
    except Exception:
        pass  # File unreadable, skip silently
    return env


def _init():
    """Lazy-load credentials and URL.

    Search order for each variable:
    1. Environment variables (already set in process)
    2. configuring skill (auto-detects .env files in Claude.ai)
    3. Well-known env file paths (#263: turso.env, muninn.env, ~/.muninn/.env)
    4. Legacy /mnt/project/turso-token.txt (token only)
    5. Default URL if no URL found
    """
    if state._TOKEN is None:
        # Try to load configuring skill (for Claude.ai environments)
        env_loader = None
        spec = importlib.util.find_spec("configuring")
        if spec is not None:
            env_module = importlib.import_module("configuring")
            env_loader = getattr(env_module, "get_env", None)

        # Scan well-known env files once (#263)
        env_file_vars = {}
        for env_path in _ENV_FILE_PATHS:
            loaded = _load_env_file(env_path)
            if loaded:
                # First matching file wins for each variable
                for k, v in loaded.items():
                    if k not in env_file_vars:
                        env_file_vars[k] = v

        # 1. Load TURSO_URL (priority: env var → configuring → env files → default)
        turso_url = os.environ.get("TURSO_URL")

        if not turso_url and env_loader is not None:
            turso_url = env_loader("TURSO_URL")

        if not turso_url:
            turso_url = env_file_vars.get("TURSO_URL")

        if not turso_url:
            turso_url = state._DEFAULT_URL_HOST

        # Normalize URL: add https:// if not present
        if turso_url and not turso_url.startswith(("http://", "https://")):
            state._URL = f"https://{turso_url}"
        else:
            state._URL = turso_url or state._DEFAULT_URL

        # 2. Load TURSO_TOKEN (priority: env var → configuring → env files → legacy file)
        state._TOKEN = os.environ.get("TURSO_TOKEN")

        if not state._TOKEN and env_loader is not None:
            state._TOKEN = env_loader("TURSO_TOKEN")

        if not state._TOKEN:
            state._TOKEN = env_file_vars.get("TURSO_TOKEN")

        # 3. Legacy fallback to separate token file (for backward compatibility)
        if not state._TOKEN:
            token_path = Path("/mnt/project/turso-token.txt")
            if token_path.exists():
                state._TOKEN = token_path.read_text().strip()

        # Clean token: remove whitespace that may be present
        if state._TOKEN:
            state._TOKEN = state._TOKEN.strip().replace(" ", "")

        # Final validation after cleaning
        if not state._TOKEN:
            searched = ", ".join(str(p) for p in _ENV_FILE_PATHS)
            raise RuntimeError(
                "Missing TURSO_TOKEN credential.\n"
                "Set TURSO_TOKEN in any of:\n"
                f"  1. Environment variable TURSO_TOKEN\n"
                f"  2. Env file at: {searched}\n"
                "  3. /mnt/project/turso-token.txt (legacy)\n"
                "  4. Claude Code ~/.claude/settings.json env block\n"
                "\nExample env file contents:\n"
                "  TURSO_TOKEN=your_token_here\n"
                "  TURSO_URL=assistant-memory-oaustegard.aws-us-east-1.turso.io"
            )

        state._HEADERS = {"Authorization": f"Bearer {state._TOKEN}", "Content-Type": "application/json"}


def _retry_with_backoff(fn, max_retries=3, base_delay=1.0):
    """Retry a function with exponential backoff on transient errors.

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
            # Check if it's a retriable error (503, 429, SSL handshake failures)
            error_str = str(e)
            is_retriable = (
                '503' in error_str or
                '429' in error_str or
                'Service Unavailable' in error_str or
                'SSL' in error_str or
                'SSLError' in error_str or
                'HANDSHAKE_FAILURE' in error_str
            )
            if is_retriable:
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

    try:
        resp = requests.post(
            f"{state._URL}/v2/pipeline",
            headers=state._HEADERS,
            json={"requests": requests_list},
            timeout=30
        ).json()
    except requests.exceptions.SSLError as e:
        raise RuntimeError(
            f"SSL error connecting to Turso database. This often indicates missing or invalid credentials.\n"
            f"Check that TURSO_TOKEN is set in environment or /mnt/project/muninn.env\n"
            f"Original error: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Network error connecting to Turso database at {state._URL}\n"
            f"Check network connectivity and credentials (TURSO_TOKEN).\n"
            f"Original error: {e}"
        ) from e

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


def _escape_fts5_server(query: str) -> str:
    """Escape special FTS5 characters for server-side search.

    FTS5 special chars: " * ( ) : ^
    Strips them and joins words with OR + prefix matching.

    Args:
        query: Raw search string

    Returns:
        FTS5-safe query expression
    """
    special_chars = '"*():^'
    escaped = query
    for char in special_chars:
        escaped = escaped.replace(char, ' ')

    words = [w.strip() for w in escaped.split() if w.strip()]
    if not words:
        return '""'

    return ' OR '.join(f'"{w}"*' for w in words)


def _fts5_search(search: str, *, n: int = 10, type: str = None,
                 tags: list = None, tag_mode: str = "any",
                 conf: float = None, session_id: str = None,
                 since: str = None, until: str = None,
                 episodic: bool = False) -> list:
    """Server-side FTS5 search via Turso with BM25 × recency × priority ranking.

    Queries the memory_fts virtual table on Turso, joining with the memories
    table for filtering and composite scoring. Returns ranked results without
    needing the local SQLite cache.

    Standard composite score formula:
        bm25_score × (1 + priority × 0.3) × recency_decay

    Episodic composite score formula (v5.1.0, #296):
        bm25_score × (1 + priority × 0.3) × recency_decay × access_boost

    Where:
        recency_decay = 1 / (1 + age_in_days × 0.01)
        access_boost = 1 + ln(1 + access_count) × 0.2  (episodic mode only)

    BM25 column weights: id=0, summary=1.0, tags=1.0
    (v5.1.0: tags weight increased from 0.5 to 1.0 for better tag search, #309)

    Args:
        search: Text to search for (required)
        n: Max results (default 10)
        type: Filter by memory type
        tags: Filter by tags
        tag_mode: "any" (default) or "all" for tag matching
        conf: Minimum confidence threshold
        session_id: Filter by session identifier
        since: Inclusive lower bound on timestamp (ISO format)
        until: Inclusive upper bound on timestamp (ISO format)
        episodic: If True, include access-pattern boosting in score (#296)

    Returns:
        List of memory dicts with bm25_score and composite_score fields.
        Results are ordered by composite_score (best first).

    Raises:
        RuntimeError: If FTS5 table doesn't exist or query fails

    v5.1.0: Added episodic scoring mode (#296), increased tag weight (#309).
    v4.5.0: Initial implementation (#298).
    """
    fts_query = _escape_fts5_server(search)

    # Build WHERE conditions for the memories table (alias m)
    conditions = [
        "m.deleted_at IS NULL",
        "m.id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]
    params = [fts_query]  # First param is the MATCH query

    if type:
        conditions.append("m.type = ?")
        params.append(type)

    if tags:
        if tag_mode == "all":
            for t in tags:
                conditions.append("m.tags LIKE ?")
                params.append(f'%"{t}"%')
        else:
            tag_conds = []
            for t in tags:
                tag_conds.append("m.tags LIKE ?")
                params.append(f'%"{t}"%')
            conditions.append(f"({' OR '.join(tag_conds)})")

    if conf is not None:
        conditions.append("m.confidence >= ?")
        params.append(conf)

    if session_id is not None:
        conditions.append("m.session_id = ?")
        params.append(session_id)

    if since is not None:
        conditions.append("m.t >= ?")
        params.append(since)

    if until is not None:
        conditions.append("m.t <= ?")
        params.append(until)

    where = " AND ".join(conditions)
    params.append(n)

    # v5.1.0: BM25 weights — id=0, summary=1.0, tags=1.0 (tags raised from 0.5, #309)
    bm25_expr = "bm25(memory_fts, 0, 1.0, 1.0)"

    # v5.1.0: Episodic scoring adds access-pattern boost (#296)
    if episodic:
        composite_expr = (
            f"{bm25_expr}"
            f" * (1.0 + COALESCE(m.priority, 0) * 0.3)"
            f" * (1.0 / (1.0 + (julianday('now') - julianday(m.t)) * 0.01))"
            f" * (1.0 + ln(1.0 + COALESCE(m.access_count, 0)) * 0.2)"
        )
    else:
        composite_expr = (
            f"{bm25_expr}"
            f" * (1.0 + COALESCE(m.priority, 0) * 0.3)"
            f" * (1.0 / (1.0 + (julianday('now') - julianday(m.t)) * 0.01))"
        )

    sql = f"""
        SELECT m.*,
               {bm25_expr} AS bm25_score,
               {composite_expr} AS composite_score
        FROM memory_fts f
        JOIN memories m ON f.id = m.id
        WHERE memory_fts MATCH ?
          AND {where}
        ORDER BY composite_score ASC
        LIMIT ?
    """

    return _exec(sql, params)


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

    try:
        resp = requests.post(
            f"{state._URL}/v2/pipeline",
            headers=state._HEADERS,
            json={"requests": [{"type": "execute", "stmt": stmt}]},
            timeout=30
        ).json()
    except requests.exceptions.SSLError as e:
        raise RuntimeError(
            f"SSL error connecting to Turso database. This often indicates missing or invalid credentials.\n"
            f"Check that TURSO_TOKEN is set in environment or /mnt/project/muninn.env\n"
            f"Original error: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Network error connecting to Turso database at {state._URL}\n"
            f"Check network connectivity and credentials (TURSO_TOKEN).\n"
            f"Original error: {e}"
        ) from e

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
