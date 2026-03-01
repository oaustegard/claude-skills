"""Memory tools for perch sessions.

Maps Anthropic tool-use calls to remembering.scripts functions.
"""

import sys
import os

# Ensure the repo root is on sys.path so `from remembering.scripts import ...` works
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from remembering.scripts import (
    recall, remember, supersede, forget, consolidate, _exec,
)


# -- Tool definitions (Anthropic Messages API format) --

MEMORY_TOOLS = [
    {
        "name": "recall",
        "description": (
            "Search memories by text, tags, or type. Returns matching memories "
            "ranked by relevance (BM25 + priority + recency). Use to find existing "
            "knowledge, check for duplicates, or gather context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Text to search for (FTS5 with Porter stemming).",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags. Matches any tag by default.",
                },
                "type": {
                    "type": "string",
                    "enum": ["decision", "world", "anomaly", "experience", "interaction", "procedure"],
                    "description": "Filter by memory type.",
                },
                "n": {
                    "type": "integer",
                    "description": "Max results to return (default 10).",
                    "default": 10,
                },
                "tag_mode": {
                    "type": "string",
                    "enum": ["any", "all"],
                    "description": "Match any tag or all tags (default: any).",
                    "default": "any",
                },
            },
            "required": [],
        },
    },
    {
        "name": "remember",
        "description": (
            "Store a new memory. Use for insights, observations, session logs, "
            "and synthesized knowledge. Each memory gets a UUID and is searchable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "what": {
                    "type": "string",
                    "description": "The memory content to store.",
                },
                "type": {
                    "type": "string",
                    "enum": ["decision", "world", "anomaly", "experience", "interaction", "procedure"],
                    "description": "Memory type.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization and retrieval.",
                },
                "priority": {
                    "type": "integer",
                    "enum": [-1, 0, 1, 2],
                    "description": "Priority: -1=background, 0=normal, 1=important, 2=critical.",
                    "default": 0,
                },
                "conf": {
                    "type": "number",
                    "description": "Confidence 0.0-1.0 (default varies by type).",
                },
            },
            "required": ["what", "type"],
        },
    },
    {
        "name": "supersede",
        "description": (
            "Replace an existing memory with an updated version. The original is "
            "soft-deleted and the new memory references it. Use when correcting or "
            "updating outdated information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "original_id": {
                    "type": "string",
                    "description": "ID (or unique prefix) of the memory to replace.",
                },
                "summary": {
                    "type": "string",
                    "description": "Updated memory content.",
                },
                "type": {
                    "type": "string",
                    "enum": ["decision", "world", "anomaly", "experience", "interaction", "procedure"],
                    "description": "Memory type for the replacement.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for the replacement memory.",
                },
            },
            "required": ["original_id", "summary", "type"],
        },
    },
    {
        "name": "forget",
        "description": (
            "Soft-delete a memory by ID. Use for duplicates, outdated entries, "
            "or noise reduction. The memory remains resolvable for reference chains."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "ID (or unique prefix) of the memory to delete.",
                },
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "consolidate",
        "description": (
            "Find clusters of related memories by tag and optionally merge them. "
            "Use dry_run=true first to preview what would be consolidated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to cluster by. If omitted, clusters all memories.",
                },
                "min_cluster": {
                    "type": "integer",
                    "description": "Minimum memories in a cluster to consider (default 3).",
                    "default": 3,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview only, don't actually merge (default true).",
                    "default": True,
                },
            },
            "required": [],
        },
    },
    {
        "name": "sql_query",
        "description": (
            "Execute raw SQL against the Turso memory database. Use for analytical "
            "queries like counting memories by type, finding patterns, or custom "
            "aggregations that recall() can't express."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL query to execute. Read-only queries recommended.",
                },
                "args": {
                    "type": "array",
                    "description": "Positional arguments for parameterized queries.",
                },
            },
            "required": ["sql"],
        },
    },
]


# -- Tool executors --

def execute_recall(input: dict) -> str:
    """Execute recall tool and return formatted results."""
    results = recall(
        search=input.get("search"),
        tags=input.get("tags"),
        type=input.get("type"),
        n=input.get("n", 10),
        tag_mode=input.get("tag_mode", "any"),
    )
    if not results:
        return "No memories found."
    lines = []
    for m in results:
        tags_str = ", ".join(m.tags) if m.tags else ""
        lines.append(
            f"[{m.id[:8]}] ({m.type}, p={m.priority}) {m.summary_preview}\n"
            f"  tags: [{tags_str}]  created: {m.created_at}"
        )
    return f"{len(results)} memories found:\n\n" + "\n\n".join(lines)


def execute_remember(input: dict) -> str:
    """Execute remember tool and return the new memory ID."""
    memory_id = remember(
        what=input["what"],
        type=input["type"],
        tags=input.get("tags"),
        priority=input.get("priority", 0),
        conf=input.get("conf"),
    )
    return f"Stored memory {memory_id[:8]}."


def execute_supersede(input: dict) -> str:
    """Execute supersede tool and return the new memory ID."""
    new_id = supersede(
        original_id=input["original_id"],
        summary=input["summary"],
        type=input["type"],
        tags=input.get("tags"),
    )
    return f"Superseded {input['original_id'][:8]} -> new memory {new_id[:8]}."


def execute_forget(input: dict) -> str:
    """Execute forget tool."""
    result = forget(memory_id=input["memory_id"])
    if result:
        return f"Deleted memory {input['memory_id'][:8]}."
    return f"Memory {input['memory_id'][:8]} not found or already deleted."


def execute_consolidate(input: dict) -> str:
    """Execute consolidate tool and return summary."""
    result = consolidate(
        tags=input.get("tags"),
        min_cluster=input.get("min_cluster", 3),
        dry_run=input.get("dry_run", True),
    )
    mode = "DRY RUN" if input.get("dry_run", True) else "EXECUTED"
    clusters = result.get("clusters", [])
    if not clusters:
        return f"[{mode}] No clusters found meeting threshold."
    lines = [f"[{mode}] {len(clusters)} cluster(s):"]
    for c in clusters:
        lines.append(f"  - {c.get('tag', 'unknown')}: {c.get('count', 0)} memories")
    return "\n".join(lines)


def execute_sql_query(input: dict) -> str:
    """Execute raw SQL and return results."""
    rows = _exec(input["sql"], args=input.get("args"))
    if not rows:
        return "Query returned no results."
    # Truncate large result sets
    if len(rows) > 50:
        return f"{len(rows)} rows returned (showing first 50):\n\n" + _format_rows(rows[:50])
    return f"{len(rows)} row(s):\n\n" + _format_rows(rows)


def _format_rows(rows: list) -> str:
    """Format SQL result rows as readable text."""
    if not rows:
        return ""
    lines = []
    for row in rows:
        parts = [f"{k}={v}" for k, v in row.items()]
        lines.append(" | ".join(parts))
    return "\n".join(lines)


# -- Executor dispatch --

MEMORY_EXECUTORS = {
    "recall": execute_recall,
    "remember": execute_remember,
    "supersede": execute_supersede,
    "forget": execute_forget,
    "consolidate": execute_consolidate,
    "sql_query": execute_sql_query,
}
