"""
Task discipline utilities for Muninn — structural enforcement for multi-step work.

This module provides:
- Task class: type-specific checklists, verification reports, cross-session persistence
- task(): factory function for creating tasks
- task_resume(): load persisted task by name
- incomplete_tasks(): list all pending tasks (used by boot)
- recall_gate: context manager enforcing recall() before analysis
- deliver(): fuse storage + output into single call (see recall_gate for enforce pattern)

v1.0.0: Initial implementation for #332 — structural enforcement for Muninn
"""

import json
import sys
import time
from contextlib import contextmanager
from datetime import datetime, UTC

# Task-type-specific checklists
CHECKLISTS = {
    "analysis":  ["recall", "synthesize", "verify", "store"],
    "research":  ["recall", "search", "read", "synthesize", "store"],
    "synthesis": ["recall", "outline", "write", "verify", "store"],
    "zeitgeist": ["recall", "sample", "cluster", "summarize", "store"],
    "default":   ["store"],
}

TASK_STATE_CATEGORY = "task-state"


def _turso_exec(sql, args=None):
    sys.path.insert(0, '/mnt/skills/user/remembering')
    from scripts.turso import _exec
    return _exec(sql, args or [])


def _task_key(name: str) -> str:
    return f"task-{name}"


def _save_task(name: str, task_type, steps: dict, created: float) -> None:
    """Persist task state to Turso config table."""
    try:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        value = json.dumps({
            'name': name,
            'task_type': task_type,
            'steps': steps,
            'created': created,
        })
        key = _task_key(name)
        _turso_exec(
            """INSERT OR REPLACE INTO config (key, value, category, updated_at)
               VALUES (?, ?, ?, ?)""",
            [key, value, TASK_STATE_CATEGORY, now]
        )
    except Exception:
        pass  # Persistence is best-effort; don't fail task operations


def _load_task_state(name: str) -> dict | None:
    """Load task state from Turso config table."""
    try:
        rows = _turso_exec(
            "SELECT value FROM config WHERE key=? AND category=?",
            [_task_key(name), TASK_STATE_CATEGORY]
        )
        if rows:
            return json.loads(rows[0]['value'])
    except Exception:
        pass
    return None


def _delete_task_state(name: str) -> None:
    """Remove task state from Turso config table."""
    try:
        _turso_exec(
            "DELETE FROM config WHERE key=? AND category=?",
            [_task_key(name), TASK_STATE_CATEGORY]
        )
    except Exception:
        pass


class Task:
    """Structural forcing function for multi-step work with type-specific checklists.

    Task types and their default steps:
        analysis:  recall → synthesize → verify → store
        research:  recall → search → read → synthesize → store
        synthesis: recall → outline → write → verify → store
        zeitgeist: recall → sample → cluster → summarize → store

    complete() generates a structured verification report and raises if incomplete.
    incomplete_prefix() adds "INCOMPLETE:" prefix to output when steps remain.
    """

    def __init__(self, name: str, steps=None, task_type: str = None,
                 require_store: bool = True, persist: bool = True):
        self.name = name
        self.task_type = task_type
        self.persist = persist
        self.steps = {}
        self.created = time.time()

        # Load type-specific checklist or custom steps
        if task_type and task_type in CHECKLISTS:
            for s in CHECKLISTS[task_type]:
                self.steps[s] = False
        elif steps:
            for s in steps:
                self.steps[s] = False
        else:
            for s in CHECKLISTS["default"]:
                self.steps[s] = False

        # Always ensure store step is present
        if require_store and 'store' not in self.steps:
            self.steps['store'] = False

        if self.persist:
            _save_task(self.name, self.task_type, self.steps, self.created)

    def done(self, step: str) -> 'Task':
        """Mark a step complete. Returns self for chaining."""
        if step not in self.steps:
            self.steps[step] = False  # auto-add
        self.steps[step] = True
        if self.persist:
            _save_task(self.name, self.task_type, self.steps, self.created)
        return self

    def pending(self) -> list:
        """Return list of incomplete steps."""
        return [s for s, done in self.steps.items() if not done]

    def status(self) -> str:
        """Return formatted status string."""
        type_tag = f" [{self.task_type}]" if self.task_type else ""
        lines = [f"Task: {self.name}{type_tag}"]
        for step, done in self.steps.items():
            mark = "✓" if done else "○"
            lines.append(f"  {mark} {step}")
        remaining = self.pending()
        if remaining:
            lines.append(f"  Pending: {', '.join(remaining)}")
        else:
            lines.append("  All steps complete")
        return "\n".join(lines)

    def incomplete_prefix(self, content: str) -> str:
        """Prefix content with INCOMPLETE: warning if required steps are missing."""
        remaining = self.pending()
        if remaining:
            return (
                f"INCOMPLETE: [{', '.join(remaining)} not done]\n\n{content}"
            )
        return content

    def complete(self) -> str:
        """Final gate with structured verification report.

        Returns a verification report string if all steps done.
        Raises RuntimeError with structured report if steps remain.
        """
        remaining = self.pending()
        elapsed = time.time() - self.created

        if remaining:
            lines = [
                f"❌ TASK INCOMPLETE: '{self.name}'",
                f"  Type: {self.task_type or 'custom'}",
                f"  Elapsed: {elapsed:.1f}s",
                "",
                "  Checklist:",
            ]
            for step, done in self.steps.items():
                mark = "✓" if done else "✗"
                lines.append(f"    [{mark}] {step}")
            lines.extend([
                "",
                f"  Blocked on: {', '.join(remaining)}",
                "  Call deliver() or t.done('store') to proceed.",
            ])
            raise RuntimeError("\n".join(lines))

        # Success — generate verification report
        lines = [
            f"✓ Task '{self.name}' complete ({elapsed:.1f}s)",
            f"  Type: {self.task_type or 'custom'}",
            "  Verified:",
        ]
        for step in self.steps:
            lines.append(f"    [✓] {step}")

        # Clean up persisted state
        if self.persist:
            _delete_task_state(self.name)

        return "\n".join(lines)


def task(name: str, steps=None, task_type: str = None,
         require_store: bool = True, persist: bool = True) -> Task:
    """Create a tracked task with type-specific checklist.

    Args:
        name:          Task identifier (used for persistence key)
        steps:         Custom step list (overrides task_type checklist)
        task_type:     One of: analysis, research, synthesis, zeitgeist
        require_store: Auto-include 'store' step (default True)
        persist:       Save state to Turso for cross-session continuity (default True)

    Usage:
        t = task("Analyze bluesky trends", task_type="analysis")
        t.done("recall"); t.done("synthesize"); t.done("verify")
        deliver(content, "world", tags=["trends"], task=t)
        t.complete()  # → structured verification report

        # Or custom steps:
        t = task("Fetch and parse", steps=["fetch", "parse", "output"])
    """
    return Task(name, steps, task_type, require_store, persist)


def task_resume(name: str) -> Task | None:
    """Load a persisted task by name for cross-session continuity.

    Usage:
        t = task_resume("Analyze bluesky trends")
        if t:
            print(t.status())  # see where we left off
        else:
            t = task("Analyze bluesky trends", task_type="analysis")
    """
    state = _load_task_state(name)
    if not state:
        return None
    t = Task.__new__(Task)
    t.name = state['name']
    t.task_type = state.get('task_type')
    t.steps = state.get('steps', {})
    t.created = state.get('created', time.time())
    t.persist = True
    return t


def incomplete_tasks() -> list:
    """List all persisted incomplete tasks (surfaced at boot).

    Returns list of Task objects with at least one pending step.
    Used by boot() to surface cross-session work-in-progress.
    """
    try:
        rows = _turso_exec(
            "SELECT value FROM config WHERE category=?",
            [TASK_STATE_CATEGORY]
        )
        result = []
        for row in rows:
            try:
                state = json.loads(row.get('value', '{}'))
                t = Task.__new__(Task)
                t.name = state['name']
                t.task_type = state.get('task_type')
                t.steps = state.get('steps', {})
                t.created = state.get('created', 0)
                t.persist = True
                if t.pending():
                    result.append(t)
            except Exception:
                continue
        return result
    except Exception:
        return []


@contextmanager
def recall_gate(topic: str, require_results: bool = True):
    """Context manager that enforces recall() before analysis proceeds.

    Forces Muninn to query memory before analyzing topics with prior history.
    Raises if recall wasn't called within the context OR if no results returned
    (when require_results=True).

    Usage:
        with recall_gate("bluesky zeitgeist") as gate:
            results = gate.recall("bluesky trends")  # tracked recall
            # ... analyze results
        # Raises RecallGateError if recall wasn't invoked or returned empty

    Args:
        topic:           Topic being analyzed (for error messages)
        require_results: Raise if recall returns no results (default True)
    """
    gate = _RecallGate(topic, require_results)
    try:
        yield gate
        gate._verify()
    except _RecallGateError:
        raise
    except Exception:
        raise


class _RecallGateError(RuntimeError):
    pass


class _RecallGate:
    """Internal gate object yielded by recall_gate context manager."""

    def __init__(self, topic: str, require_results: bool):
        self.topic = topic
        self.require_results = require_results
        self._recalled = False
        self._result_count = 0

    def recall(self, query: str = None, **kwargs) -> list:
        """Perform recall and track invocation.

        Args:
            query:    Recall query (defaults to gate topic)
            **kwargs: Passed to remembering.scripts.recall()

        Returns:
            List of matching memories
        """
        sys.path.insert(0, '/mnt/skills/user/remembering')
        from scripts import recall as _recall
        results = _recall(query or self.topic, **kwargs)
        self._recalled = True
        self._result_count = len(results) if results else 0
        return results

    def _verify(self):
        """Raise if recall wasn't invoked or returned empty (if required)."""
        if not self._recalled:
            raise _RecallGateError(
                f"recall_gate violation: recall() not called before analyzing '{self.topic}'.\n"
                "Use gate.recall(query) within the context to query prior memory."
            )
        if self.require_results and self._result_count == 0:
            raise _RecallGateError(
                f"recall_gate: recall('{self.topic}') returned 0 results.\n"
                "If this is genuinely new territory, use recall_gate(require_results=False)."
            )
