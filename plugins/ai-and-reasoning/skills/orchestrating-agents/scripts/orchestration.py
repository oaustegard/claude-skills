"""
Advanced Orchestration Primitives

Builds on claude_client and task_state to provide:
- Exponential backoff retry for failed invocations (Task 4)
- Reconciliation hooks for validating work before dispatch (Task 5)
- Concurrency control with global and per-category limits (Task 6)

All functions maintain backward compatibility with existing invoke_parallel
interfaces — new parameters are optional with sensible defaults.
"""

import time
import threading
from typing import Callable, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from claude_client import (
    invoke_claude,
    ClaudeInvocationError,
    StallDetector,
    _format_system_with_cache,
)
from task_state import TaskTracker, TaskState, TERMINAL_STATES


# ---------------------------------------------------------------------------
# Task 4: Exponential Backoff
# ---------------------------------------------------------------------------

def compute_backoff_delay(
    attempt: int,
    *,
    is_continuation: bool = False,
    base_ms: float = 1000.0,
    max_ms: float = 10000.0,
) -> float:
    """
    Compute retry delay in seconds following Symphony patterns.

    - Continuation retries (success path): fixed 1-second delay
    - Failure retries: exponential backoff capped at max_ms

    Args:
        attempt: The retry attempt number (1-based)
        is_continuation: True for continuation retries (fixed 1s delay)
        base_ms: Base delay in milliseconds for failure backoff (default: 1000)
        max_ms: Maximum delay in milliseconds (default: 10000)

    Returns:
        Delay in seconds
    """
    if is_continuation:
        return 1.0
    delay_ms = min(base_ms * (2 ** (attempt - 1)), max_ms)
    return delay_ms / 1000.0


# @lat: [[orchestration#Orchestration Layer]]
def invoke_with_retry(
    prompt: Union[str, list[dict]],
    *,
    max_retries: int = 3,
    base_delay_ms: float = 1000.0,
    max_delay_ms: float = 10000.0,
    is_continuation: bool = False,
    model: str = "claude-sonnet-4-6",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    **kwargs,
) -> str:
    """
    Invoke Claude with automatic retry and exponential backoff.

    Args:
        prompt: The user message
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay_ms: Base delay in ms for exponential backoff (default: 1000)
        max_delay_ms: Maximum delay in ms (default: 10000)
        is_continuation: Use fixed 1s delay instead of exponential (default: False)
        model: Claude model identifier
        system: Optional system prompt
        max_tokens: Maximum response tokens
        temperature: Sampling temperature
        **kwargs: Additional parameters passed to invoke_claude

    Returns:
        str: Response text

    Raises:
        ClaudeInvocationError: If all retries are exhausted
    """
    last_error = None
    for attempt in range(1, max_retries + 2):  # +2: 1 initial + max_retries
        try:
            return invoke_claude(
                prompt=prompt,
                model=model,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        except ClaudeInvocationError as e:
            last_error = e
            # Don't retry on client errors (4xx except 429)
            if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                raise
            if attempt <= max_retries:
                delay = compute_backoff_delay(
                    attempt,
                    is_continuation=is_continuation,
                    base_ms=base_delay_ms,
                    max_ms=max_delay_ms,
                )
                time.sleep(delay)
            else:
                raise
    # Should not reach here, but just in case
    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Task 5: Reconciliation Hook
# ---------------------------------------------------------------------------

# @lat: [[orchestration#Orchestration Layer]]
def invoke_parallel_with_reconciliation(
    prompts: list[dict],
    *,
    reconcile: Optional[Callable[[list[dict], "TaskTracker"], list[dict]]] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False,
    max_retries: int = 3,
    stall_timeout: Optional[float] = None,
    on_stall: Optional[Callable] = None,
) -> list[str | None]:
    """
    Parallel invocations with reconciliation, retry, and stall detection.

    Before dispatching tasks, the optional reconcile callback validates
    ongoing work and can filter/modify the prompt list.

    Args:
        prompts: List of prompt dicts (same format as invoke_parallel)
        reconcile: Optional callback(prompts, tracker) -> filtered_prompts.
            Called before dispatch to validate and prune work items.
            Return a subset of prompts to actually execute.
        model: Claude model identifier
        max_tokens: Max tokens per response
        max_workers: Max concurrent invocations (default: 5, max: 10)
        shared_system: Shared system context for caching
        cache_shared_system: Cache the shared system prompt
        max_retries: Max retries per task on failure (default: 3)
        stall_timeout: Seconds before considering a task stalled (None = disabled)
        on_stall: Callback(task_id, idle_seconds) when stall detected

    Returns:
        List of response strings (None for cancelled/failed tasks).
        Order matches input prompts.
    """
    if not prompts:
        return []

    max_workers = max(1, min(max_workers, 10))

    # Initialize task tracker
    tracker = TaskTracker(max_retries=max_retries)
    for i, p in enumerate(prompts):
        task_id = p.get("task_id", f"task-{i}")
        category = p.get("category")
        tracker.add(task_id, category=category)

    # Reconciliation: let the caller prune/validate before dispatch
    active_prompts = list(enumerate(prompts))
    if reconcile:
        prompt_list = [p for _, p in active_prompts]
        filtered = reconcile(prompt_list, tracker)
        # Map filtered prompts back to original indices
        filtered_set = set(id(p) for p in filtered)
        cancelled = [
            (i, p) for i, p in active_prompts
            if id(p) not in filtered_set
        ]
        for i, p in cancelled:
            task_id = p.get("task_id", f"task-{i}")
            try:
                tracker.claim(task_id)
                tracker.cancel(task_id)
            except Exception:
                tracker.cancel(task_id)
        active_prompts = [
            (i, p) for i, p in active_prompts
            if id(p) in filtered_set
        ]

    # Setup stall detector if configured
    stall_detector = None
    if stall_timeout:
        stall_detector = StallDetector(timeout=stall_timeout, on_stall=on_stall)
        stall_detector.start_monitoring()

    # Format shared system
    formatted_shared = _format_system_with_cache(shared_system, cache_shared_system)

    results: list[str | None] = [None] * len(prompts)

    def execute_task(idx: int, prompt_dict: dict) -> tuple[int, str | None]:
        task_id = prompt_dict.get("task_id", f"task-{idx}")

        try:
            tracker.claim(task_id)
            tracker.start(task_id)
        except Exception:
            return (idx, None)

        if stall_detector:
            stall_detector.register(task_id)

        prompt = prompt_dict["prompt"]
        params = {k: v for k, v in prompt_dict.items()
                  if k not in ("prompt", "task_id", "category")}
        params.setdefault("model", model)
        params.setdefault("max_tokens", max_tokens)

        if formatted_shared:
            individual = params.get("system")
            if individual:
                if isinstance(formatted_shared, str):
                    shared_blocks = [{"type": "text", "text": formatted_shared}]
                else:
                    shared_blocks = formatted_shared
                if isinstance(individual, str):
                    ind_blocks = [{"type": "text", "text": individual}]
                else:
                    ind_blocks = individual
                params["system"] = shared_blocks + ind_blocks
            else:
                params["system"] = formatted_shared

        last_error = None
        while True:
            try:
                if stall_detector:
                    stall_detector.heartbeat(task_id)

                result = invoke_claude(prompt, **params)
                tracker.complete(task_id)
                return (idx, result)

            except ClaudeInvocationError as e:
                last_error = e
                # Don't retry client errors (except 429)
                if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                    tracker.fail(task_id, error=str(e))
                    return (idx, None)

                tracker.fail(task_id, error=str(e))
                try:
                    tracker.retry(task_id)
                    info = tracker.get(task_id)
                    delay = compute_backoff_delay(info.attempt)
                    time.sleep(delay)
                    tracker.claim(task_id)
                    tracker.start(task_id)
                except RuntimeError:
                    # Max retries exceeded
                    return (idx, None)
            finally:
                if stall_detector:
                    stall_detector.unregister(task_id)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(execute_task, i, p): i
            for i, p in active_prompts
        }
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    if stall_detector:
        stall_detector.stop_monitoring()

    return results


# ---------------------------------------------------------------------------
# Task 6: Concurrency Control
# ---------------------------------------------------------------------------

# @lat: [[orchestration#Orchestration Layer]]
class ConcurrencyLimiter:
    """
    Enforces global and per-category concurrency limits.

    Prevents resource starvation by limiting how many tasks can run
    simultaneously, both globally and within each category.

    Args:
        global_limit: Maximum total concurrent tasks (default: 10)
        category_limits: Dict of category -> max concurrent tasks.
            Categories not listed use global_limit.
    """

    def __init__(
        self,
        global_limit: int = 10,
        category_limits: Optional[dict[str, int]] = None,
    ):
        self._lock = threading.Lock()
        self.global_limit = global_limit
        self.category_limits = category_limits or {}
        self._global_semaphore = threading.Semaphore(global_limit)
        self._category_semaphores: dict[str, threading.Semaphore] = {}
        for cat, limit in self.category_limits.items():
            self._category_semaphores[cat] = threading.Semaphore(limit)

    def _get_category_semaphore(self, category: Optional[str]) -> Optional[threading.Semaphore]:
        if not category:
            return None
        with self._lock:
            if category not in self._category_semaphores:
                limit = self.category_limits.get(category, self.global_limit)
                self._category_semaphores[category] = threading.Semaphore(limit)
            return self._category_semaphores[category]

    def acquire(self, category: Optional[str] = None, timeout: float = None) -> bool:
        """
        Acquire execution slot (blocks until available or timeout).

        Args:
            category: Optional category for per-category limiting
            timeout: Max seconds to wait (None = block indefinitely)

        Returns:
            True if slot acquired, False if timed out
        """
        if not self._global_semaphore.acquire(timeout=timeout):
            return False

        cat_sem = self._get_category_semaphore(category)
        if cat_sem:
            if not cat_sem.acquire(timeout=timeout):
                self._global_semaphore.release()
                return False

        return True

    def release(self, category: Optional[str] = None) -> None:
        """Release an execution slot."""
        cat_sem = self._get_category_semaphore(category)
        if cat_sem:
            cat_sem.release()
        self._global_semaphore.release()


def invoke_parallel_managed(
    prompts: list[dict],
    *,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False,
    max_retries: int = 3,
    reconcile: Optional[Callable] = None,
    concurrency_limiter: Optional[ConcurrencyLimiter] = None,
    stall_timeout: Optional[float] = None,
    on_stall: Optional[Callable] = None,
) -> list[str | None]:
    """
    Full-featured parallel invocations with all Symphony patterns.

    Combines concurrency control, reconciliation, retry with backoff,
    stall detection, and task lifecycle tracking.

    Args:
        prompts: List of prompt dicts. Each may include:
            - 'prompt' (required): The user message
            - 'task_id' (optional): Unique task identifier
            - 'category' (optional): Category for concurrency limits
            - Other invoke_claude parameters
        model: Claude model identifier
        max_tokens: Max tokens per response
        max_workers: Max thread pool workers (default: 5, max: 10)
        shared_system: Shared system context
        cache_shared_system: Cache shared system prompt
        max_retries: Max retries per task (default: 3)
        reconcile: Optional callback(prompts, tracker) -> filtered_prompts
        concurrency_limiter: Optional ConcurrencyLimiter instance
        stall_timeout: Seconds before stall detection triggers (None = disabled)
        on_stall: Callback when stall detected

    Returns:
        List of response strings (None for failed/cancelled tasks)
    """
    if not prompts:
        return []

    max_workers = max(1, min(max_workers, 10))

    tracker = TaskTracker(max_retries=max_retries)
    for i, p in enumerate(prompts):
        task_id = p.get("task_id", f"task-{i}")
        category = p.get("category")
        tracker.add(task_id, category=category)

    # Reconciliation
    active_prompts = list(enumerate(prompts))
    if reconcile:
        prompt_list = [p for _, p in active_prompts]
        filtered = reconcile(prompt_list, tracker)
        filtered_set = set(id(p) for p in filtered)
        for i, p in active_prompts:
            if id(p) not in filtered_set:
                task_id = p.get("task_id", f"task-{i}")
                try:
                    tracker.claim(task_id)
                    tracker.cancel(task_id)
                except Exception:
                    tracker.cancel(task_id)
        active_prompts = [(i, p) for i, p in active_prompts if id(p) in filtered_set]

    # Stall detection
    stall_detector = None
    if stall_timeout:
        stall_detector = StallDetector(timeout=stall_timeout, on_stall=on_stall)
        stall_detector.start_monitoring()

    formatted_shared = _format_system_with_cache(shared_system, cache_shared_system)
    results: list[str | None] = [None] * len(prompts)

    def execute_task(idx: int, prompt_dict: dict) -> tuple[int, str | None]:
        task_id = prompt_dict.get("task_id", f"task-{idx}")
        category = prompt_dict.get("category")

        # Concurrency control
        if concurrency_limiter:
            if not concurrency_limiter.acquire(category, timeout=120.0):
                tracker.cancel(task_id)
                return (idx, None)

        try:
            tracker.claim(task_id)
            tracker.start(task_id)

            if stall_detector:
                stall_detector.register(task_id)

            prompt = prompt_dict["prompt"]
            params = {k: v for k, v in prompt_dict.items()
                      if k not in ("prompt", "task_id", "category")}
            params.setdefault("model", model)
            params.setdefault("max_tokens", max_tokens)

            if formatted_shared:
                individual = params.get("system")
                if individual:
                    if isinstance(formatted_shared, str):
                        shared_blocks = [{"type": "text", "text": formatted_shared}]
                    else:
                        shared_blocks = formatted_shared
                    if isinstance(individual, str):
                        ind_blocks = [{"type": "text", "text": individual}]
                    else:
                        ind_blocks = individual
                    params["system"] = shared_blocks + ind_blocks
                else:
                    params["system"] = formatted_shared

            while True:
                try:
                    if stall_detector:
                        stall_detector.heartbeat(task_id)
                    result = invoke_claude(prompt, **params)
                    tracker.complete(task_id)
                    return (idx, result)
                except ClaudeInvocationError as e:
                    if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                        tracker.fail(task_id, error=str(e))
                        return (idx, None)
                    tracker.fail(task_id, error=str(e))
                    try:
                        tracker.retry(task_id)
                        info = tracker.get(task_id)
                        delay = compute_backoff_delay(info.attempt)
                        time.sleep(delay)
                        tracker.claim(task_id)
                        tracker.start(task_id)
                    except RuntimeError:
                        return (idx, None)
        finally:
            if stall_detector:
                stall_detector.unregister(task_id)
            if concurrency_limiter:
                concurrency_limiter.release(category)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(execute_task, i, p): i
            for i, p in active_prompts
        }
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    if stall_detector:
        stall_detector.stop_monitoring()

    return results
