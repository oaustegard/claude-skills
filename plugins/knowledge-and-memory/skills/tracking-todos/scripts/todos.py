"""Tracking-todos: session task list with Claude Code TodoWrite semantics.

Storage: Muninn config entry 'active-todos' (category='ops') as JSON array.
Schema matches Claude Code exactly: {content, status, activeForm}.
"""

import json
import sys

from scripts import config_get, config_set

CONFIG_KEY = "active-todos"
VALID_STATUS = ("pending", "in_progress", "completed")


def get_todos():
    """Return current todo list (possibly empty).

    If the stored value is missing, empty, or structurally invalid, returns []
    and prints a warning to stderr. Silent recovery is deliberate: callers
    should be able to read todos without worrying about historical corruption
    (e.g. a schema change). Inspect the raw config value directly if you
    suspect data loss.
    """
    raw = config_get(CONFIG_KEY)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(
            f"[tracking-todos] WARNING: stored todos are not valid JSON ({e}). "
            f"Returning empty list. Raw value length: {len(raw)}",
            file=sys.stderr,
        )
        return []
    try:
        _validate(parsed)
    except ValueError as e:
        print(
            f"[tracking-todos] WARNING: stored todos failed validation ({e}). "
            f"Returning empty list.",
            file=sys.stderr,
        )
        return []
    return parsed


def write_todos(todos):
    """Replace entire todo list.

    Matches Claude Code semantics: if every todo is 'completed', clears the
    stored list instead of persisting an all-done state. Returns the
    passed-in list regardless of storage clearing, so the caller can render
    the final completed state before moving on.

    Raises ValueError on schema violations or >1 in_progress.
    """
    _validate(todos)
    all_done = len(todos) > 0 and all(t["status"] == "completed" for t in todos)
    to_store = [] if all_done else todos
    config_set(CONFIG_KEY, json.dumps(to_store), category="ops")
    return todos


def abandon():
    """Clear the todo list unconditionally. Use when starting fresh work
    that makes prior todos irrelevant."""
    config_set(CONFIG_KEY, "[]", category="ops")


def render(todos=None):
    """Pretty-print todos for display. Returns a string."""
    if todos is None:
        todos = get_todos()
    if not todos:
        return "(no active todos)"
    marks = {"pending": "☐", "in_progress": "▶", "completed": "✓"}
    lines = []
    for t in todos:
        label = t["activeForm"] if t["status"] == "in_progress" else t["content"]
        lines.append(f"  {marks[t['status']]} {label}")
    return "\n".join(lines)


def _validate(todos):
    if not isinstance(todos, list):
        raise ValueError(f"todos must be a list, got {type(todos).__name__}")
    in_progress_count = 0
    for i, t in enumerate(todos):
        if not isinstance(t, dict):
            raise ValueError(f"todos[{i}] must be a dict")
        for field in ("content", "status", "activeForm"):
            if field not in t:
                raise ValueError(f"todos[{i}] missing field: {field}")
            if not isinstance(t[field], str) or not t[field].strip():
                raise ValueError(f"todos[{i}].{field} must be a non-empty string")
        if t["status"] not in VALID_STATUS:
            raise ValueError(
                f"todos[{i}].status must be one of {VALID_STATUS}, got {t['status']!r}"
            )
        if t["status"] == "in_progress":
            in_progress_count += 1
    if in_progress_count > 1:
        raise ValueError(
            f"at most one todo may be in_progress at a time (found {in_progress_count})"
        )
