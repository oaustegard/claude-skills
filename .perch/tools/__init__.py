"""Tool registry and executor for perch sessions.

Provides TOOL_DEFINITIONS (Anthropic API format) and execute_tool() dispatcher.
"""

from .memory import MEMORY_TOOLS, MEMORY_EXECUTORS
from .world import WORLD_TOOLS, WORLD_EXECUTORS

# All tools indexed by name
_ALL_TOOLS = {t["name"]: t for t in MEMORY_TOOLS + WORLD_TOOLS}
_ALL_EXECUTORS = {**MEMORY_EXECUTORS, **WORLD_EXECUTORS}

# Tool sets per task type
TASK_TOOLS = {
    "sleep": [
        "recall", "remember", "supersede", "forget", "consolidate", "sql_query",
    ],
    "zeitgeist": [
        "recall", "remember",
        "bsky_feed", "bsky_search", "bsky_trending", "fetch_url",
    ],
    "fly": [
        "recall", "remember", "supersede",
        "bsky_search", "fetch_url",
    ],
}


def get_tool_definitions(task: str) -> list:
    """Return Anthropic-format tool definitions for the given task."""
    tool_names = TASK_TOOLS.get(task, [])
    return [_ALL_TOOLS[name] for name in tool_names if name in _ALL_TOOLS]


def execute_tool(name: str, input: dict) -> str:
    """Execute a tool by name and return the result as a string.

    Returns error message string on failure (never raises).
    """
    executor = _ALL_EXECUTORS.get(name)
    if not executor:
        return f"Unknown tool: {name}"
    try:
        return executor(input)
    except Exception as e:
        return f"Tool {name} failed: {type(e).__name__}: {e}"
