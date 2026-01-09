"""
Turso HTTP API layer for remembering skill.

This module handles:
- Environment file loading (_load_env_file)
- Credential initialization (_init)
- HTTP request retry logic (_retry_with_backoff)
- SQL execution via Turso HTTP API (_exec, _exec_batch)
- JSON field parsing (_parse_memory_row)

Imports from: state
"""

import requests
import json
import os
import time
from pathlib import Path

from . import state


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
    """Lazy-load credentials and URL from environment, .env file, or legacy project file."""
    if state._TOKEN is None:
        # Load .env file once for both URL and TOKEN
        env_file = _load_env_file(Path("/mnt/project/muninn.env"))

        # 1. Load TURSO_URL (prefer env var, fall back to .env, then default)
        state._URL = os.environ.get("TURSO_URL")
        if not state._URL:
            state._URL = env_file.get("TURSO_URL")
        if not state._URL:
            state._URL = state._DEFAULT_URL

        # 2. Load TURSO_TOKEN (prefer env var, fall back to .env, then legacy file)
        state._TOKEN = os.environ.get("TURSO_TOKEN")
        if not state._TOKEN:
            state._TOKEN = env_file.get("TURSO_TOKEN")

        # 3. Legacy fallback to separate token file
        if not state._TOKEN:
            token_path = Path("/mnt/project/turso-token.txt")
            if token_path.exists():
                state._TOKEN = token_path.read_text().strip()

        # Clean token: remove whitespace that may be present
        if state._TOKEN:
            state._TOKEN = state._TOKEN.strip().replace(" ", "")

        # Final validation after cleaning
        if not state._TOKEN:
            raise RuntimeError(
                "Missing TURSO_TOKEN credential.\n"
                "Set TURSO_TOKEN in:\n"
                "  1. Environment variables, OR\n"
                "  2. /mnt/project/muninn.env (recommended), OR\n"
                "  3. /mnt/project/turso-token.txt (legacy)\n"
                "\nFor /mnt/project/muninn.env, format should be:\n"
                "  TURSO_TOKEN=your_token_here\n"
                "  TURSO_URL=https://assistant-memory-oaustegard.aws-us-east-1.turso.io"
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
