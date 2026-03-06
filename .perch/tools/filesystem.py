"""Filesystem tools for perch sessions.

Allows the LLM to read files from the repository on demand.
"""

import os
from pathlib import Path

# Repo root for path resolution and containment checks
_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


FILESYSTEM_TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Read a file from the repository. Use to access SKILL.md files, "
            "configuration, or any repo content. Path is relative to repo root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to repo root.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate to this many chars (default 10000).",
                    "default": 10000,
                },
            },
            "required": ["path"],
        },
    },
]


def execute_read_file(input: dict) -> str:
    """Read a file from the repository, validating the path stays within repo root."""
    rel_path = input["path"]
    max_chars = input.get("max_chars", 10000)

    # Resolve and validate path stays within repo
    target = (_REPO_ROOT / rel_path).resolve()
    if not str(target).startswith(str(_REPO_ROOT)):
        return f"Error: path escapes repository root: {rel_path}"

    if not target.exists():
        return f"File not found: {rel_path}"

    if not target.is_file():
        return f"Not a file: {rel_path}"

    try:
        content = target.read_text(errors="replace")
    except Exception as e:
        return f"Error reading {rel_path}: {e}"

    if len(content) > max_chars:
        return content[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"
    return content


FILESYSTEM_EXECUTORS = {
    "read_file": execute_read_file,
}
