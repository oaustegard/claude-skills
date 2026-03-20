"""
flowing — lightweight DAG workflow runner for Claude.ai containers.

Declare steps. Wire dependencies. Run once. No think loops.

Usage:
    from flowing import task, Flow

    @task
    def fetch_data():
        return {"items": [1, 2, 3]}

    @task(depends_on=[fetch_data])
    def process(fetch_data):
        return sum(fetch_data["items"])

    @task(depends_on=[process])
    def store(process):
        print(f"Result: {process}")

    Flow(store).run()

Resume from failure:
    flow = Flow(terminal)
    results = flow.run()       # step 3 fails
    flow.override(step_3, corrected_value)
    results = flow.resume()    # runs step 4+ with corrected step 3

Detached side-effects:
    @task(depends_on=[create_issue], detached=True)
    def store_memory(create_issue):
        remember(create_issue["url"], ...)
    # Failure here does NOT block the main pipeline
"""

from __future__ import annotations

import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional


class StepState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    name: str
    state: StepState
    value: Any = None
    error: Optional[Exception] = None
    duration_ms: float = 0
    attempts: int = 0


@dataclass
class TaskDef:
    """A declared workflow step."""
    name: str
    fn: Callable
    depends_on: list[TaskDef] = field(default_factory=list)
    retry: int = 0
    retry_backoff_base_ms: int = 1000
    retry_max_backoff_ms: int = 30_000
    timeout_s: Optional[float] = None
    detached: bool = False

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


def task(
    fn: Optional[Callable] = None,
    *,
    depends_on: Optional[list[TaskDef]] = None,
    retry: int = 0,
    retry_backoff_base_ms: int = 1000,
    retry_max_backoff_ms: int = 30_000,
    timeout_s: Optional[float] = None,
    name: Optional[str] = None,
    detached: bool = False,
) -> TaskDef:
    def wrap(f: Callable) -> TaskDef:
        td = TaskDef(
            name=name or f.__name__,
            fn=f,
            depends_on=depends_on or [],
            retry=retry,
            retry_backoff_base_ms=retry_backoff_base_ms,
            retry_max_backoff_ms=retry_max_backoff_ms,
            timeout_s=timeout_s,
            detached=detached,
        )
        return td

    if fn is not None:
        return wrap(fn)
    return wrap


def _topo_sort(terminal: TaskDef) -> list[list[TaskDef]]:
    all_tasks: set[TaskDef] = set()
    stack = [terminal]
    while stack:
        t = stack.pop()
        if t not in all_tasks:
            all_tasks.add(t)
            stack.extend(t.depends_on)

    in_degree: dict[TaskDef, int] = {t: 0 for t in all_tasks}
    dependents: dict[TaskDef, list[TaskDef]] = {t: [] for t in all_tasks}
    for t in all_tasks:
        for dep in t.depends_on:
            in_degree[t] += 1
            dependents[dep].append(t)

    layers: list[list[TaskDef]] = []
    current = [t for t, d in in_degree.items() if d == 0]
    visited = 0

    while current:
        layers.append(current)
        visited += len(current)
        next_layer = []
        for t in current:
            for dep in dependents[t]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_layer.append(dep)
        current = next_layer

    if visited != len(all_tasks):
        raise ValueError(
            f"Cycle detected in task graph. "
            f"Visited {visited}/{len(all_tasks)} tasks."
        )
    return layers


def _log(msg: str, **kw):
    parts = [f"[flow] {msg}"]
    for k, v in kw.items():
        parts.append(f"{k}={v}")
    print(" ".join(parts), file=sys.stderr, flush=True)


def _run_step(td: TaskDef, results: dict[str, StepResult]) -> StepResult:
    kwargs = {}
    for dep in td.depends_on:
        r = results[dep.name]
        if r.state != StepState.SUCCEEDED:
            _log(f"SKIP {td.name}", reason=f"dependency {dep.name} failed")
            return StepResult(name=td.name, state=StepState.SKIPPED, attempts=0)
        kwargs[dep.name] = r.value

    max_attempts = 1 + td.retry
    last_error = None

    for attempt in range(1, max_attempts + 1):
        _log(f"{'RUN' if attempt == 1 else 'RETRY'} {td.name}",
             attempt=f"{attempt}/{max_attempts}")

        t0 = time.monotonic()
        try:
            value = td.fn(**kwargs)
            dur = (time.monotonic() - t0) * 1000
            _log(f"OK {td.name}", ms=f"{dur:.0f}")
            return StepResult(
                name=td.name, state=StepState.SUCCEEDED,
                value=value, duration_ms=dur, attempts=attempt,
            )
        except Exception as e:
            dur = (time.monotonic() - t0) * 1000
            last_error = e
            _log(f"FAIL {td.name}", ms=f"{dur:.0f}",
                 error=str(e)[:120], attempt=f"{attempt}/{max_attempts}")
            if attempt < max_attempts:
                delay_ms = min(
                    td.retry_backoff_base_ms * (2 ** (attempt - 1)),
                    td.retry_max_backoff_ms,
                )
                time.sleep(delay_ms / 1000)

    return StepResult(
        name=td.name, state=StepState.FAILED, error=last_error,
        duration_ms=(time.monotonic() - t0) * 1000 if 't0' in dir() else 0,
        attempts=max_attempts,
    )


class Flow:
    def __init__(self, *terminals: TaskDef, max_workers: int = 5, fail_fast: bool = True):
        if not terminals:
            raise ValueError("Flow requires at least one terminal task")
        self.terminals = list(terminals)
        self.max_workers = max_workers
        self.fail_fast = fail_fast
        self.results: dict[str, StepResult] = {}
        self.detached_failures: list[StepResult] = []

    def _collect_tasks(self) -> tuple[set[TaskDef], set[TaskDef]]:
        """Collect all tasks, separating main DAG from detached tasks."""
        all_tasks: set[TaskDef] = set()
        stack = list(self.terminals)
        while stack:
            t = stack.pop()
            if t not in all_tasks:
                all_tasks.add(t)
                stack.extend(t.depends_on)

        main_tasks = {t for t in all_tasks if not t.detached}
        detached_tasks = {t for t in all_tasks if t.detached}
        return main_tasks, detached_tasks

    def _build_layers(self, tasks: set[TaskDef]) -> list[list[TaskDef]]:
        """Topological sort into parallel execution layers."""
        in_degree: dict[TaskDef, int] = {t: 0 for t in tasks}
        dependents: dict[TaskDef, list[TaskDef]] = {t: [] for t in tasks}
        for t in tasks:
            for dep in t.depends_on:
                if dep in tasks:
                    in_degree[t] += 1
                    dependents[dep].append(t)

        layers: list[list[TaskDef]] = []
        current = [t for t, d in in_degree.items() if d == 0]
        visited = 0
        while current:
            layers.append(current)
            visited += len(current)
            next_layer = []
            for t in current:
                for dep in dependents[t]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        next_layer.append(dep)
            current = next_layer

        if visited != len(tasks):
            raise ValueError("Cycle detected in task graph")
        return layers

    def _execute(self, layers: list[list[TaskDef]], skip_succeeded: bool = False) -> None:
        """Execute layers. If skip_succeeded=True, skip tasks already SUCCEEDED in self.results."""
        for layer_idx, layer in enumerate(layers):
            # Filter out already-succeeded tasks when resuming
            if skip_succeeded:
                layer = [t for t in layer if not (
                    t.name in self.results and
                    self.results[t.name].state == StepState.SUCCEEDED
                )]
                if not layer:
                    continue

            parallel = len(layer) > 1
            _log(f"LAYER {layer_idx}",
                 tasks=",".join(t.name for t in layer), parallel=parallel)

            if parallel:
                with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                    futures = {
                        pool.submit(_run_step, td, self.results): td
                        for td in layer
                    }
                    for future in as_completed(futures):
                        result = future.result()
                        self.results[result.name] = result
                        if self.fail_fast and result.state == StepState.FAILED:
                            _log(f"FAIL_FAST triggered by {result.name}")
                            for f in futures:
                                f.cancel()
                            break
            else:
                for td in layer:
                    result = _run_step(td, self.results)
                    self.results[result.name] = result
                    if self.fail_fast and result.state == StepState.FAILED:
                        _log(f"FAIL_FAST triggered by {result.name}")
                        break

            if self.fail_fast:
                failed = [r for r in self.results.values()
                          if r.state == StepState.FAILED]
                if failed:
                    break

    def _execute_detached(self, detached_tasks: set[TaskDef]) -> None:
        """Run detached tasks in one final parallel layer. Failures collected, not propagated."""
        if not detached_tasks:
            return

        # Only run detached tasks whose dependencies all succeeded
        runnable = []
        for t in detached_tasks:
            deps_ok = all(
                t_dep.name in self.results and
                self.results[t_dep.name].state == StepState.SUCCEEDED
                for t_dep in t.depends_on
            )
            if deps_ok:
                runnable.append(t)
            else:
                skip_result = StepResult(
                    name=t.name, state=StepState.SKIPPED, attempts=0)
                self.results[t.name] = skip_result

        if not runnable:
            return

        _log("DETACHED", tasks=",".join(t.name for t in runnable))

        if len(runnable) > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {
                    pool.submit(_run_step, td, self.results): td
                    for td in runnable
                }
                for future in as_completed(futures):
                    result = future.result()
                    self.results[result.name] = result
                    if result.state == StepState.FAILED:
                        self.detached_failures.append(result)
        else:
            for td in runnable:
                result = _run_step(td, self.results)
                self.results[result.name] = result
                if result.state == StepState.FAILED:
                    self.detached_failures.append(result)

    def run(self) -> dict[str, StepResult]:
        """Execute the full DAG from scratch."""
        self.results = {}
        self.detached_failures = []

        main_tasks, detached_tasks = self._collect_tasks()
        main_layers = self._build_layers(main_tasks)

        total_tasks = sum(len(l) for l in main_layers) + len(detached_tasks)
        _log("START", tasks=total_tasks, layers=len(main_layers),
             terminals=",".join(t.name for t in self.terminals),
             detached=len(detached_tasks))

        flow_t0 = time.monotonic()

        # Execute main DAG
        self._execute(main_layers)

        # Execute detached tasks (only if main DAG didn't fail, or their deps succeeded)
        self._execute_detached(detached_tasks)

        flow_dur = (time.monotonic() - flow_t0) * 1000
        succeeded = sum(1 for r in self.results.values() if r.state == StepState.SUCCEEDED)
        failed = sum(1 for r in self.results.values() if r.state == StepState.FAILED)
        skipped = sum(1 for r in self.results.values() if r.state == StepState.SKIPPED)

        _log("DONE", ms=f"{flow_dur:.0f}",
             succeeded=succeeded, failed=failed, skipped=skipped)
        return self.results

    def resume(self) -> dict[str, StepResult]:
        """Re-run from failure point. SUCCEEDED tasks keep their cached values.
        FAILED and SKIPPED tasks reset to PENDING and re-execute."""
        self.detached_failures = []

        # Reset FAILED and SKIPPED tasks
        to_reset = [name for name, r in self.results.items()
                    if r.state in (StepState.FAILED, StepState.SKIPPED)]
        for name in to_reset:
            del self.results[name]

        main_tasks, detached_tasks = self._collect_tasks()
        main_layers = self._build_layers(main_tasks)

        cached = sum(1 for r in self.results.values() if r.state == StepState.SUCCEEDED)
        _log("RESUME", cached=cached, reset=len(to_reset))

        flow_t0 = time.monotonic()

        # Execute with skip_succeeded=True
        self._execute(main_layers, skip_succeeded=True)

        # Re-run detached tasks (they may have been skipped/failed before)
        self._execute_detached(detached_tasks)

        flow_dur = (time.monotonic() - flow_t0) * 1000
        succeeded = sum(1 for r in self.results.values() if r.state == StepState.SUCCEEDED)
        failed = sum(1 for r in self.results.values() if r.state == StepState.FAILED)
        skipped = sum(1 for r in self.results.values() if r.state == StepState.SKIPPED)

        _log("DONE", ms=f"{flow_dur:.0f}",
             succeeded=succeeded, failed=failed, skipped=skipped)
        return self.results

    def override(self, td: TaskDef, value: Any) -> None:
        """Manually set a result without re-running the task.
        Use when you have fixed the problem externally and have the correct value."""
        self.results[td.name] = StepResult(
            name=td.name, state=StepState.SUCCEEDED,
            value=value, duration_ms=0, attempts=0,
        )

    def value(self, td: TaskDef) -> Any:
        r = self.results.get(td.name)
        if r is None:
            raise KeyError(f"Task {td.name} not found in results")
        if r.state != StepState.SUCCEEDED:
            raise RuntimeError(f"Task {td.name} did not succeed (state={r.state})")
        return r.value

    def summary(self) -> str:
        lines = []
        for name, r in self.results.items():
            status = r.state.value.upper()
            dur = f"{r.duration_ms:.0f}ms"
            att = f"x{r.attempts}" if r.attempts > 1 else ""
            err = f" err={r.error}" if r.error else ""
            det = " [detached]" if any(
                t.name == name and t.detached
                for t in self._all_task_defs()
            ) else ""
            lines.append(f"  {status:9s} {name} ({dur}{att}){det}{err}")
        return "\n".join(lines)

    def _all_task_defs(self) -> set[TaskDef]:
        """Collect all TaskDef objects in the graph."""
        all_tasks: set[TaskDef] = set()
        stack = list(self.terminals)
        while stack:
            t = stack.pop()
            if t not in all_tasks:
                all_tasks.add(t)
                stack.extend(t.depends_on)
        return all_tasks
