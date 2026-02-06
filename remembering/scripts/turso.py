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
