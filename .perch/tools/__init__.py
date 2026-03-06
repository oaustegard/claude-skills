"""Tool registry and executor for perch sessions.

Provides TOOL_DEFINITIONS (Anthropic API format) and execute_tool() dispatcher.
All tools are available in all task modes — prompts guide focus, tools enable flexibility.
"""

from .memory import MEMORY_TOOLS, MEMORY_EXECUTORS
from .world import WORLD_TOOLS, WORLD_EXECUTORS
from .filesystem import FILESYSTEM_TOOLS, FILESYSTEM_EXECUTORS

# All tools indexed by name
_ALL_TOOLS = {t["name"]: t for t in MEMORY_TOOLS + WORLD_TOOLS + FILESYSTEM_TOOLS}
_ALL_EXECUTORS = {**MEMORY_EXECUTORS, **WORLD_EXECUTORS, **FILESYSTEM_EXECUTORS}


def get_tool_definitions(task: str) -> list:
    """Return all tool definitions regardless of task.

    All tools are available in every mode. The task prompt guides which tools
    are most relevant, but the LLM can use any tool if the situation calls for it.
    """
    return list(_ALL_TOOLS.values())


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
