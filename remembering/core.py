"""Turso HTTP API layer for remembering skill."""

import requests
import json
import uuid
import re
from datetime import datetime, UTC
from pathlib import Path

_URL = "https://assistant-memory-oaustegard.aws-us-east-1.turso.io"
_TOKEN = None
_HEADERS = None

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

# Type inference patterns
_TYPE_PATTERNS = {
    "decision": re.compile(r"\b(prefers?|likes?|wants?|should|always|never|best|better|worse)\b", re.I),
    "world": re.compile(r"\b(TODO|TASK|need to|deadline|blocked|waiting|external|fact)\b", re.I),
    "anomaly": re.compile(r"\b(error|bug|issue|broken|failed|unexpected)\b", re.I),
}

def infer_type(summary: str) -> str:
    """Infer memory type from summary content."""
    for mtype, pattern in _TYPE_PATTERNS.items():
        if pattern.search(summary):
            return mtype
    return "experience"

def store(summary: str, type: str = None, tags: list = None, entities: list = None, 
          confidence: float = None, refs: list = None) -> str:
    """Store a memory. Returns the memory ID."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mem_id = str(uuid.uuid4())
    
    # Auto-infer type if not specified
    if type is None:
        type = infer_type(summary)
    
    # Auto-set confidence for decisions
    if type == "decision" and confidence is None:
        confidence = 0.8
    
    _exec(
        """INSERT INTO memories (id, type, t, summary, confidence, tags, entities, refs, session_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [mem_id, type, now, summary, confidence,
         json.dumps(tags or []), json.dumps(entities or []), json.dumps(refs or []), 
         "session", now, now]
    )
    return mem_id

def query(search: str = None, tags: list = None, type: str = None, 
          conf: float = None, limit: int = 10) -> list:
    """Query memories with flexible filters."""
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
