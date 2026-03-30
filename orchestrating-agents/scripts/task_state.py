"""
Task Lifecycle State Machine

Provides formal state tracking for orchestrated tasks, inspired by Symphony
orchestration patterns. Tasks follow defined transitions:

    Unclaimed → Claimed → Running → Completed
                                  → Failed → RetryQueued → Claimed
                                  → Cancelled

Thread-safe for use with concurrent task execution.
"""

import enum
import threading
import time
from typing import Optional


# @lat: [[orchestration#Task State Machine]]
class TaskState(enum.Enum):
    """Valid states for a managed task."""
    UNCLAIMED = "unclaimed"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_QUEUED = "retry_queued"
    CANCELLED = "cancelled"


# Valid state transitions: current_state -> set of allowed next states
_VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.UNCLAIMED: {TaskState.CLAIMED, TaskState.CANCELLED},
    TaskState.CLAIMED: {TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.RUNNING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.FAILED: {TaskState.RETRY_QUEUED, TaskState.CANCELLED},
    TaskState.RETRY_QUEUED: {TaskState.CLAIMED, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),
    TaskState.CANCELLED: set(),
}

TERMINAL_STATES = {TaskState.COMPLETED, TaskState.CANCELLED}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, task_id: str, current: TaskState, target: TaskState):
        self.task_id = task_id
        self.current = current
        self.target = target
        super().__init__(
            f"Task '{task_id}': invalid transition {current.value} → {target.value}"
        )


class TaskInfo:
    """Immutable snapshot of a task's current state."""
    __slots__ = ("task_id", "state", "attempt", "created_at", "updated_at",
                 "category", "metadata")

    def __init__(self, task_id: str, state: TaskState, attempt: int,
                 created_at: float, updated_at: float,
                 category: Optional[str], metadata: Optional[dict]):
        self.task_id = task_id
        self.state = state
        self.attempt = attempt
        self.created_at = created_at
        self.updated_at = updated_at
        self.category = category
        self.metadata = metadata

    def __repr__(self) -> str:
        return (f"TaskInfo(id={self.task_id!r}, state={self.state.value}, "
                f"attempt={self.attempt}, category={self.category!r})")


class _TaskRecord:
    """Internal mutable task record (not exposed externally)."""
    def __init__(self, task_id: str, category: Optional[str] = None,
                 metadata: Optional[dict] = None):
        self.task_id = task_id
        self.state = TaskState.UNCLAIMED
        self.attempt = 0
        self.created_at = time.monotonic()
        self.updated_at = self.created_at
        self.category = category
        self.metadata = metadata or {}

    def snapshot(self) -> TaskInfo:
        return TaskInfo(
            task_id=self.task_id,
            state=self.state,
            attempt=self.attempt,
            created_at=self.created_at,
            updated_at=self.updated_at,
            category=self.category,
            metadata=dict(self.metadata),
        )


# @lat: [[orchestration#Task State Machine]]
class TaskTracker:
    """
    Thread-safe task lifecycle manager.

    Tracks tasks through formal state transitions and prevents invalid
    operations like duplicate dispatch or claiming terminal tasks.

    Args:
        max_retries: Maximum retry attempts before a task stays in FAILED (default: 3)
    """

    def __init__(self, max_retries: int = 3):
        self._lock = threading.Lock()
        self._tasks: dict[str, _TaskRecord] = {}
        self.max_retries = max_retries

    def add(self, task_id: str, category: Optional[str] = None,
            metadata: Optional[dict] = None) -> TaskInfo:
        """
        Register a new task in UNCLAIMED state.

        Args:
            task_id: Unique identifier for the task
            category: Optional category for concurrency grouping
            metadata: Optional dict of extra data to attach

        Returns:
            TaskInfo snapshot of the new task

        Raises:
            ValueError: If task_id already exists
        """
        with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"Task '{task_id}' already exists")
            record = _TaskRecord(task_id, category, metadata)
            self._tasks[task_id] = record
            return record.snapshot()

    def transition(self, task_id: str, target: TaskState) -> TaskInfo:
        """
        Move a task to a new state.

        Args:
            task_id: The task to transition
            target: The desired new state

        Returns:
            TaskInfo snapshot after transition

        Raises:
            KeyError: If task_id not found
            InvalidTransitionError: If the transition is not valid
        """
        with self._lock:
            record = self._tasks[task_id]  # raises KeyError if missing
            if target not in _VALID_TRANSITIONS[record.state]:
                raise InvalidTransitionError(task_id, record.state, target)

            record.state = target
            record.updated_at = time.monotonic()

            # Increment attempt counter when entering CLAIMED from RETRY_QUEUED
            # (or first claim from UNCLAIMED counts as attempt 1 via _start_running)
            if target == TaskState.RUNNING:
                record.attempt += 1

            return record.snapshot()

    def claim(self, task_id: str) -> TaskInfo:
        """Shorthand: UNCLAIMED/RETRY_QUEUED → CLAIMED."""
        return self.transition(task_id, TaskState.CLAIMED)

    def start(self, task_id: str) -> TaskInfo:
        """Shorthand: CLAIMED → RUNNING (increments attempt count)."""
        return self.transition(task_id, TaskState.RUNNING)

    def complete(self, task_id: str) -> TaskInfo:
        """Shorthand: RUNNING → COMPLETED."""
        return self.transition(task_id, TaskState.COMPLETED)

    def fail(self, task_id: str, error: Optional[str] = None) -> TaskInfo:
        """
        Mark a task as failed. Stores error in metadata.

        Args:
            task_id: The task that failed
            error: Optional error description

        Returns:
            TaskInfo snapshot after failure
        """
        with self._lock:
            record = self._tasks[task_id]
            if TaskState.FAILED not in _VALID_TRANSITIONS[record.state]:
                raise InvalidTransitionError(task_id, record.state, TaskState.FAILED)
            record.state = TaskState.FAILED
            record.updated_at = time.monotonic()
            if error:
                record.metadata["last_error"] = error
            return record.snapshot()

    def retry(self, task_id: str) -> TaskInfo:
        """
        Queue a failed task for retry if under max_retries.

        Args:
            task_id: The failed task to retry

        Returns:
            TaskInfo snapshot after queuing

        Raises:
            InvalidTransitionError: If task is not in FAILED state
            RuntimeError: If max retries exceeded
        """
        with self._lock:
            record = self._tasks[task_id]
            if record.state != TaskState.FAILED:
                raise InvalidTransitionError(
                    task_id, record.state, TaskState.RETRY_QUEUED
                )
            if record.attempt >= self.max_retries:
                raise RuntimeError(
                    f"Task '{task_id}' exceeded max retries ({self.max_retries})"
                )
            record.state = TaskState.RETRY_QUEUED
            record.updated_at = time.monotonic()
            return record.snapshot()

    def cancel(self, task_id: str) -> TaskInfo:
        """Cancel a task from any non-terminal state."""
        return self.transition(task_id, TaskState.CANCELLED)

    def get(self, task_id: str) -> TaskInfo:
        """Get a snapshot of a task's current state."""
        with self._lock:
            return self._tasks[task_id].snapshot()

    def get_by_state(self, state: TaskState) -> list[TaskInfo]:
        """Get all tasks in a given state."""
        with self._lock:
            return [
                r.snapshot() for r in self._tasks.values()
                if r.state == state
            ]

    def get_by_category(self, category: str) -> list[TaskInfo]:
        """Get all tasks in a given category."""
        with self._lock:
            return [
                r.snapshot() for r in self._tasks.values()
                if r.category == category
            ]

    def active_count(self, category: Optional[str] = None) -> int:
        """
        Count tasks in non-terminal states.

        Args:
            category: If provided, count only tasks in this category
        """
        with self._lock:
            return sum(
                1 for r in self._tasks.values()
                if r.state not in TERMINAL_STATES
                and (category is None or r.category == category)
            )

    def is_all_terminal(self) -> bool:
        """Check if all tracked tasks have reached terminal states."""
        with self._lock:
            return all(
                r.state in TERMINAL_STATES for r in self._tasks.values()
            )

    def summary(self) -> dict[str, int]:
        """Return counts by state."""
        with self._lock:
            counts: dict[str, int] = {}
            for r in self._tasks.values():
                key = r.state.value
                counts[key] = counts.get(key, 0) + 1
            return counts

    def __len__(self) -> int:
        """Total number of tracked tasks."""
        return len(self._tasks)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self._tasks
