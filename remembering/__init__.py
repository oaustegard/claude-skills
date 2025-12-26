"""Remembering - Minimal persistent memory for Claude."""

import requests
import json
import uuid
import threading
import os
from datetime import datetime, UTC
from pathlib import Path

_URL = "https://assistant-memory-oaustegard.aws-us-east-1.turso.io"
_TOKEN = None
_HEADERS = None
_EMBEDDING_API_KEY = None

# Valid memory types (profile now lives in config table)
TYPES = {"decision", "world", "anomaly", "experience"}

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

def _embed(text: str) -> list[float] | None:
    """Generate embedding vector for text using OpenAI text-embedding-3-small.

    Returns list of 1536 floats, or None if API key not configured.
    """
    _init()
    if not _EMBEDDING_API_KEY:
        return None

    try:
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
    except Exception as e:
        # Fail gracefully - embedding is optional
        print(f"Warning: Embedding generation failed: {e}")
        return None

def _exec(sql, args=None):
    """Execute SQL, return list of dicts."""
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
    return [
        {cols[i]: (row[i].get("value") if row[i].get("type") != "null" else None) for i in range(len(cols))}
        for row in res["rows"]
    ]

def remember(what: str, type: str, *, tags: list = None, conf: float = None,
             entities: list = None, refs: list = None, embed: bool = True) -> str:
    """Store a memory with optional embedding. Type is required. Returns memory ID.

    Args:
        what: Memory content/summary
        type: Memory type (decision, world, anomaly, experience)
        tags: Optional list of tags
        conf: Optional confidence score (0.0-1.0)
        entities: Optional list of entities
        refs: Optional list of referenced memory IDs
        embed: Generate and store embedding for semantic search (default True)
    """
    if type not in TYPES:
        raise ValueError(f"Invalid type '{type}'. Must be one of: {', '.join(sorted(TYPES))}")

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mem_id = str(uuid.uuid4())

    if type == "decision" and conf is None:
        conf = 0.8

    # Generate embedding if requested
    embedding = None
    if embed:
        embedding = _embed(what)

    # vector32() doesn't accept NULL, so we use conditional SQL
    if embedding:
        _exec(
            """INSERT INTO memories (id, type, t, summary, confidence, tags, entities, refs,
               session_id, created_at, updated_at, embedding)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, vector32(?))""",
            [mem_id, type, now, what, conf,
             json.dumps(tags or []), json.dumps(entities or []), json.dumps(refs or []),
             "session", now, now, json.dumps(embedding)]
        )
    else:
        # Insert without embedding when not available
        _exec(
            """INSERT INTO memories (id, type, t, summary, confidence, tags, entities, refs,
               session_id, created_at, updated_at, embedding)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            [mem_id, type, now, what, conf,
             json.dumps(tags or []), json.dumps(entities or []), json.dumps(refs or []),
             "session", now, now]
        )
    return mem_id

def remember_bg(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None, embed: bool = True) -> None:
    """Fire-and-forget memory storage. Type required. Returns immediately, writes in background.

    Args:
        Same as remember(), including embed parameter for semantic search support.
    """
    def _do():
        remember(what, type, tags=tags, conf=conf, entities=entities, refs=refs, embed=embed)
    threading.Thread(target=_do, daemon=True).start()

def recall(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None, tag_mode: str = "any") -> list:
    """Query memories with flexible filters.

    Args:
        search: Text to search for in memory summaries (LIKE match)
        n: Max number of results
        tags: Filter by tags
        type: Filter by memory type
        conf: Minimum confidence threshold
        tag_mode: "any" (default) matches any tag, "all" requires all tags
    """
    if isinstance(search, int):
        return _query(limit=search)
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
        "deleted_at IS NULL",
        "embedding IS NOT NULL",
        # Exclude memories that are superseded (appear in any other memory's refs field)
        "id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)"
    ]
    if type:
        conditions.append(f"type = '{type}'")
    if conf is not None:
        conditions.append(f"confidence >= {conf}")
    if tags:
        tag_conds = " OR ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        conditions.append(f"({tag_conds})")

    where = " AND ".join(conditions)

    # Use vector_top_k with index for efficient similarity search
    try:
        sql = f"""
            SELECT m.*,
                   1 - vector_distance_cos(m.embedding, vector32(?)) AS similarity
            FROM vector_top_k('memories_embedding_idx', vector32(?), {n * 2}) AS v
            JOIN memories m ON m.rowid = v.id
            WHERE {where}
            ORDER BY similarity DESC
            LIMIT {n}
        """
        return _exec(sql, [json.dumps(query_embedding), json.dumps(query_embedding)])
    except Exception as e:
        # Fallback: If vector index not available, use brute-force similarity
        print(f"Warning: Vector index search failed, using fallback: {e}")
        sql = f"""
            SELECT *,
                   1 - vector_distance_cos(embedding, vector32(?)) AS similarity
            FROM memories
            WHERE {where}
            ORDER BY similarity DESC
            LIMIT {n}
        """
        return _exec(sql, [json.dumps(query_embedding)])

def _query(search: str = None, tags: list = None, type: str = None,
           conf: float = None, limit: int = 10, tag_mode: str = "any") -> list:
    """Internal query implementation.

    Args:
        tag_mode: "any" (default) matches any tag, "all" requires all tags
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

    return _exec(f"SELECT * FROM memories WHERE {where} ORDER BY {order} LIMIT {limit}")

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
    return _exec(f"SELECT * FROM memories WHERE {where} ORDER BY t DESC LIMIT {n}")

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
    return _exec(f"SELECT * FROM memories WHERE {where} ORDER BY t DESC LIMIT {n}")

def forget(memory_id: str) -> bool:
    """Soft-delete a memory."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _exec("UPDATE memories SET deleted_at = ? WHERE id = ?", [now, memory_id])
    return True

def supersede(original_id: str, summary: str, type: str, *,
              tags: list = None, conf: float = None) -> str:
    """Create a patch that supersedes an existing memory. Type required. Returns new memory ID."""
    return remember(summary, type, tags=tags, conf=conf, refs=[original_id])

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
    "remember", "recall", "forget", "supersede", "remember_bg", "semantic_recall",  # memories
    "recall_since", "recall_between",  # date-filtered queries
    "config_get", "config_set", "config_delete", "config_list",  # config
    "profile", "ops", "journal", "journal_recent", "journal_prune",  # convenience loaders
    "therapy_scope", "therapy_session_count",  # therapy helpers
    "group_by_type", "group_by_tag",  # analysis helpers
    "muninn_export", "muninn_import",  # export/import
    "r", "q", "j", "TYPES"  # aliases & constants
]
