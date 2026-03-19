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

    def run(self) -> dict[str, StepResult]:
        all_tasks: set[TaskDef] = set()
        stack = list(self.terminals)
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

        all_layers: list[list[TaskDef]] = []
        current = [t for t, d in in_degree.items() if d == 0]
        visited = 0
        while current:
            all_layers.append(current)
            visited += len(current)
            next_layer = []
            for t in current:
                for dep in dependents[t]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        next_layer.append(dep)
            current = next_layer

        if visited != len(all_tasks):
            raise ValueError("Cycle detected in task graph")

        total_tasks = sum(len(l) for l in all_layers)
        _log(f"START", tasks=total_tasks, layers=len(all_layers),
             terminals=",".join(t.name for t in self.terminals))

        flow_t0 = time.monotonic()

        for layer_idx, layer in enumerate(all_layers):
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
                failed = [r for r in self.results.values() if r.state == StepState.FAILED]
                if failed:
                    break

        flow_dur = (time.monotonic() - flow_t0) * 1000
        succeeded = sum(1 for r in self.results.values() if r.state == StepState.SUCCEEDED)
        failed = sum(1 for r in self.results.values() if r.state == StepState.FAILED)
        skipped = sum(1 for r in self.results.values() if r.state == StepState.SKIPPED)

        _log(f"DONE", ms=f"{flow_dur:.0f}",
             succeeded=succeeded, failed=failed, skipped=skipped)
        return self.results

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
            lines.append(f"  {status:9s} {name} ({dur}{att}){err}")
        return "\n".join(lines)
