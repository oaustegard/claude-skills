"""Remembering - Minimal persistent memory for Claude."""

import requests
import json
import uuid
import threading
from datetime import datetime, UTC
from pathlib import Path

_URL = "https://assistant-memory-oaustegard.aws-us-east-1.turso.io"
_TOKEN = None
_HEADERS = None

# Valid memory types (profile now lives in config table)
TYPES = {"decision", "world", "anomaly", "experience"}

def _init():
    """Lazy-load credentials."""
    global _TOKEN, _HEADERS
    if _TOKEN is None:
        _TOKEN = Path("/mnt/project/turso-token.txt").read_text().strip()
        _HEADERS = {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}

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
        return []
    
    res = r["response"]["result"]
    cols = [c["name"] for c in res["cols"]]
    return [
        {cols[i]: (row[i]["value"] if row[i]["type"] != "null" else None) for i in range(len(cols))}
        for row in res["rows"]
    ]

def remember(what: str, type: str, *, tags: list = None, conf: float = None,
             entities: list = None, refs: list = None) -> str:
    """Store a memory. Type is required. Returns memory ID."""
    if type not in TYPES:
        raise ValueError(f"Invalid type '{type}'. Must be one of: {', '.join(sorted(TYPES))}")
    
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mem_id = str(uuid.uuid4())
    
    if type == "decision" and conf is None:
        conf = 0.8
    
    _exec(
        """INSERT INTO memories (id, type, t, summary, confidence, tags, entities, refs, session_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [mem_id, type, now, what, conf,
         json.dumps(tags or []), json.dumps(entities or []), json.dumps(refs or []), 
         "session", now, now]
    )
    return mem_id

def remember_bg(what: str, type: str, *, tags: list = None, conf: float = None,
                entities: list = None, refs: list = None) -> None:
    """Fire-and-forget memory storage. Type required. Returns immediately, writes in background."""
    def _do():
        remember(what, type, tags=tags, conf=conf, entities=entities, refs=refs)
    threading.Thread(target=_do, daemon=True).start()

def recall(search: str = None, *, n: int = 10, tags: list = None,
           type: str = None, conf: float = None) -> list:
    """Query memories with flexible filters."""
    if isinstance(search, int):
        return _query(limit=search)
    return _query(search=search, tags=tags, type=type, conf=conf, limit=n)

def _query(search: str = None, tags: list = None, type: str = None,
           conf: float = None, limit: int = 10) -> list:
    """Internal query implementation."""
    conditions = ["deleted_at IS NULL"]
    
    if search:
        conditions.append(f"summary LIKE '%{search}%'")
    if tags:
        tag_conds = " OR ".join(f"tags LIKE '%\"{t}\"%'" for t in tags)
        conditions.append(f"({tag_conds})")
    if type:
        conditions.append(f"type = '{type}'")
    if conf is not None:
        conditions.append(f"confidence >= {conf}")
    
    where = " AND ".join(conditions)
    order = "confidence DESC" if conf else "t DESC"
    
    return _exec(f"SELECT * FROM memories WHERE {where} ORDER BY {order} LIMIT {limit}")

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

def config_set(key: str, value: str, category: str) -> None:
    """Set a config value. Category must be 'profile', 'ops', or 'journal'."""
    if category not in ("profile", "ops", "journal"):
        raise ValueError(f"Invalid category '{category}'. Must be 'profile', 'ops', or 'journal'")
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _exec(
        "INSERT OR REPLACE INTO config (key, value, category, updated_at) VALUES (?, ?, ?, ?)",
        [key, value, category, now]
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
    key = f"j-{now.strftime('%Y%m%d-%H%M%S')}"
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

# Short aliases
r = remember
q = recall
j = journal

__all__ = [
    "remember", "recall", "forget", "supersede", "remember_bg",  # memories
    "config_get", "config_set", "config_delete", "config_list",  # config
    "profile", "ops", "journal", "journal_recent", "journal_prune",  # convenience loaders
    "r", "q", "j", "TYPES"  # aliases & constants
]
