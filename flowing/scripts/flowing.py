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

import base64
import hashlib
import inspect
import json
import pickle
import sys
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
    as_completed,
)
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class StepState(Enum):
    # _run_step is synchronous and only ever returns a terminal state, so
    # PENDING/RUNNING/RETRYING would never be observable — they are omitted
    # rather than defined-but-never-assigned.
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    name: str
    state: StepState
    value: Any = None
    error: Optional[Exception] = None
    duration_ms: float = 0
    attempts: int = 0
    step_key: Optional[str] = None  # content-addressed key (set only when journaling)
    cached: bool = False            # True if this result was replayed from the journal


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
    # v1.1 control-flow primitives
    when: Optional[Callable] = None         # gate: receives gathered kwargs, returns bool. False -> SKIPPED
    validate: Optional[Callable] = None     # edge contract: receives gathered kwargs, raises on bad inputs. Raise -> FAILED, no retry
    retry_until: Optional[Callable] = None  # predicate loop: receives task return value, returns bool. False -> retry (uses retry= budget)

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


# Module-level registry of all TaskDefs created via the @task decorator.
# Used by Flow._collect_tasks to auto-discover detached tasks whose dependencies
# are reachable from declared terminals (v1.2.0). Without this, a detached task
# downstream of a terminal would silently never run, since the dep walk only
# traverses depends_on backward.
_TASK_REGISTRY: list[TaskDef] = []


def clear_registry() -> None:
    """Empty the module-level task registry.

    The registry accumulates every TaskDef created via @task for the life of
    the process. For run-once container use that is fine. Call this between
    independent flows in the same process (tests, REPLs) so detached
    auto-discovery can't pull a stale task into an unrelated graph.
    """
    _TASK_REGISTRY.clear()


# @lat: [[orchestration#DAG Workflow Runner]]
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
    when: Optional[Callable] = None,
    validate: Optional[Callable] = None,
    retry_until: Optional[Callable] = None,
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
            when=when,
            validate=validate,
            retry_until=retry_until,
        )
        _TASK_REGISTRY.append(td)
        return td

    if fn is not None:
        return wrap(fn)
    return wrap


def _log(msg: str, **kw):
    parts = [f"[flow] {msg}"]
    for k, v in kw.items():
        parts.append(f"{k}={v}")
    print(" ".join(parts), file=sys.stderr, flush=True)


def _fn_fingerprint(fn: Optional[Callable]) -> str:
    """Stable-ish fingerprint of a callable's behaviour.

    Prefers bytecode (co_code + stringified co_consts), which changes when the
    body changes but is stable across re-imports of unchanged source. Falls
    back to source text, then to a qualified-name repr. Never raises.
    """
    if fn is None:
        return ""
    try:
        code = fn.__code__
        return "bc:" + hashlib.sha256(
            code.co_code + repr(code.co_consts).encode("utf-8", "replace")
        ).hexdigest()
    except Exception:
        pass
    try:
        return "src:" + hashlib.sha256(
            inspect.getsource(fn).encode("utf-8", "replace")
        ).hexdigest()
    except Exception:
        return "id:" + getattr(fn, "__qualname__", repr(fn))


STEP_KEY_VERSION = 1


def compute_step_key(td: TaskDef, dep_keys: list[str]) -> str:
    """Content-addressed, chained key for one task.

    Hashes, in order: the version, the sorted dependency keys (so an upstream
    change propagates through the chain — pi-flow's prefix sensitivity), and
    the fingerprints of the task body plus its when/validate/retry_until
    control callables. The result is `v<version>:<sha256>`.

    What is deliberately NOT in the key: name, retry/backoff/timeout knobs,
    detached flag. Tuning a reliability knob or renaming must not bust the
    cache; changing behaviour must.
    """
    h = hashlib.sha256()
    h.update(f"v{STEP_KEY_VERSION}\n".encode())
    for k in sorted(dep_keys):
        h.update(b"dep:")
        h.update(k.encode())
        h.update(b"\n")
    for label, f in (("fn", td.fn), ("when", td.when),
                     ("validate", td.validate), ("retry_until", td.retry_until)):
        h.update(label.encode())
        h.update(b"=")
        h.update(_fn_fingerprint(f).encode())
        h.update(b"\n")
    return f"v{STEP_KEY_VERSION}:{h.hexdigest()}"


def _run_step(td: TaskDef, results: dict[str, StepResult]) -> StepResult:
    kwargs = {}
    for dep in td.depends_on:
        r = results[dep.name]
        if r.state != StepState.SUCCEEDED:
            _log(f"SKIP {td.name}", reason=f"dependency {dep.name} did not succeed (state={r.state.value})")
            return StepResult(name=td.name, state=StepState.SKIPPED, attempts=0)
        kwargs[dep.name] = r.value

    # GATE 1: when() — conditional skip. Truthy -> proceed; falsy -> SKIPPED (downstream cascades).
    if td.when is not None:
        try:
            if not td.when(**kwargs):
                _log(f"SKIP {td.name}", reason="when() returned False")
                return StepResult(name=td.name, state=StepState.SKIPPED, attempts=0)
        except Exception as e:
            _log(f"FAIL {td.name}", reason=f"when() raised: {str(e)[:120]}")
            return StepResult(name=td.name, state=StepState.FAILED, error=e, attempts=0)

    # GATE 2: validate() — edge contract. Raise -> FAILED with NO retry (bad inputs won't fix themselves).
    if td.validate is not None:
        try:
            td.validate(**kwargs)
        except Exception as e:
            _log(f"FAIL {td.name}", reason=f"validate() raised: {str(e)[:120]}")
            return StepResult(name=td.name, state=StepState.FAILED, error=e, attempts=0)

    max_attempts = 1 + td.retry
    last_error = None
    last_value = None
    last_dur = 0.0

    for attempt in range(1, max_attempts + 1):
        _log(f"{'RUN' if attempt == 1 else 'RETRY'} {td.name}",
             attempt=f"{attempt}/{max_attempts}")

        t0 = time.monotonic()
        try:
            if td.timeout_s is not None:
                # Run the body in a one-shot worker so a hung call can't stall
                # the whole flow. Python can't kill a running thread, so on
                # timeout the orphaned worker keeps going until the container
                # exits — acceptable for run-once ephemeral use. shutdown is
                # wait=False precisely so we don't re-block on that orphan.
                one_shot = ThreadPoolExecutor(max_workers=1)
                fut = one_shot.submit(td.fn, **kwargs)
                try:
                    value = fut.result(timeout=td.timeout_s)
                except FuturesTimeoutError:
                    raise TimeoutError(
                        f"{td.name} exceeded timeout_s={td.timeout_s}"
                    ) from None
                finally:
                    one_shot.shutdown(wait=False)
            else:
                value = td.fn(**kwargs)
            last_dur = (time.monotonic() - t0) * 1000

            # GATE 3: retry_until() — predicate-driven loop. True -> done; False -> retry (consumes retry budget).
            if td.retry_until is not None:
                try:
                    ok = td.retry_until(value)
                except Exception as e:
                    _log(f"FAIL {td.name}", reason=f"retry_until() raised: {str(e)[:120]}")
                    return StepResult(
                        name=td.name, state=StepState.FAILED, error=e,
                        value=value, duration_ms=last_dur, attempts=attempt,
                    )
                if not ok:
                    last_value = value
                    last_error = ValueError(
                        f"retry_until predicate returned False (attempt {attempt}/{max_attempts})"
                    )
                    _log(f"PREDICATE_FAIL {td.name}", ms=f"{last_dur:.0f}",
                         attempt=f"{attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        delay_ms = min(
                            td.retry_backoff_base_ms * (2 ** (attempt - 1)),
                            td.retry_max_backoff_ms,
                        )
                        time.sleep(delay_ms / 1000)
                        continue
                    # Out of attempts; predicate still False -> FAILED with last value preserved
                    return StepResult(
                        name=td.name, state=StepState.FAILED, error=last_error,
                        value=last_value, duration_ms=last_dur, attempts=attempt,
                    )

            _log(f"OK {td.name}", ms=f"{last_dur:.0f}")
            return StepResult(
                name=td.name, state=StepState.SUCCEEDED,
                value=value, duration_ms=last_dur, attempts=attempt,
            )
        except Exception as e:
            last_dur = (time.monotonic() - t0) * 1000
            last_error = e
            _log(f"FAIL {td.name}", ms=f"{last_dur:.0f}",
                 error=str(e)[:120], attempt=f"{attempt}/{max_attempts}")
            if attempt < max_attempts:
                delay_ms = min(
                    td.retry_backoff_base_ms * (2 ** (attempt - 1)),
                    td.retry_max_backoff_ms,
                )
                time.sleep(delay_ms / 1000)

    return StepResult(
        name=td.name, state=StepState.FAILED, error=last_error,
        duration_ms=last_dur, attempts=max_attempts,
    )


# @lat: [[orchestration#DAG Workflow Runner]]
class Flow:
    def __init__(self, *terminals: TaskDef, max_workers: int = 5, fail_fast: bool = True,
                 journal_path: Optional[str] = None):
        if not terminals:
            raise ValueError("Flow requires at least one terminal task")
        self.terminals = list(terminals)
        self.max_workers = max_workers
        self.fail_fast = fail_fast
        self.results: dict[str, StepResult] = {}
        self.detached_failures: list[StepResult] = []
        # Content-addressed durable journal (opt-in). When set, run() replays
        # the unchanged prefix from disk and only executes tasks whose
        # step_key is absent — surviving container death and re-running any
        # task whose body changed (and, via key chaining, its dependents).
        self.journal_path = journal_path
        self._journal_completed: dict[str, Any] = {}  # step_key -> value
        self._step_keys: dict[TaskDef, str] = {}

    def _load_journal(self) -> None:
        """Load completed step_keys -> values from the JSONL journal.

        Append-only, tolerant of a truncated trailing line (crash mid-write).
        A value that fails to unpickle is dropped, so its task simply re-runs.
        """
        self._journal_completed = {}
        if not self.journal_path:
            return
        try:
            with open(self.journal_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # truncated final line — discard
            if entry.get("kind") != "Completed":
                continue
            try:
                val = pickle.loads(base64.b64decode(entry["value"]))
            except Exception:
                continue  # unpicklable/corrupt -> treat as not-cached
            self._journal_completed[entry["key"]] = val

    def _compute_keys(self, tasks: set[TaskDef]) -> None:
        """Compute chained step_keys for all tasks in dependency order."""
        self._step_keys = {}
        remaining = set(tasks)
        # Iterate to fixed point: a task is keyable once all its in-graph deps
        # have keys. Detached-or-not, deps may sit in another partition.
        while remaining:
            progressed = False
            for t in list(remaining):
                dep_keys = []
                ready = True
                for dep in t.depends_on:
                    if dep in tasks:
                        if dep not in self._step_keys:
                            ready = False
                            break
                        dep_keys.append(self._step_keys[dep])
                if not ready:
                    continue
                self._step_keys[t] = compute_step_key(t, dep_keys)
                remaining.discard(t)
                progressed = True
            if not progressed:
                # Dependency outside `tasks` (shouldn't happen) — key on body only.
                for t in list(remaining):
                    self._step_keys[t] = compute_step_key(t, [])
                    remaining.discard(t)

    def _cached_result(self, td: TaskDef) -> Optional[StepResult]:
        """Return a replayed SUCCEEDED result if td's step_key is journaled."""
        if not self.journal_path:
            return None
        key = self._step_keys.get(td)
        if key is not None and key in self._journal_completed:
            return StepResult(
                name=td.name, state=StepState.SUCCEEDED,
                value=self._journal_completed[key], step_key=key, cached=True,
            )
        return None

    def _journal_append(self, result: StepResult) -> None:
        """Append a Completed entry for a freshly-succeeded, non-cached task."""
        if not self.journal_path or result.cached:
            return
        if result.state != StepState.SUCCEEDED or result.step_key is None:
            return
        try:
            blob = base64.b64encode(pickle.dumps(result.value)).decode("ascii")
        except Exception as e:
            _log(f"JOURNAL_SKIP {result.name}", reason=f"unpicklable value: {str(e)[:80]}")
            return
        line = json.dumps({"kind": "Completed", "key": result.step_key,
                           "name": result.name, "value": blob})
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _collect_tasks(self) -> tuple[set[TaskDef], set[TaskDef]]:
        """Collect all tasks, separating main DAG from detached tasks.

        v1.2.0: Auto-discovers detached tasks whose dependencies are all
        reachable from declared terminals. Iterates to fixed point so that
        chains of detached tasks (detachB -> detachA -> main) are picked up.
        Detached tasks whose deps are NOT reachable are ignored — they belong
        to a different graph.
        """
        all_tasks: set[TaskDef] = set()
        stack = list(self.terminals)
        while stack:
            t = stack.pop()
            if t not in all_tasks:
                all_tasks.add(t)
                stack.extend(t.depends_on)

        # Fixed-point pull-in of detached tasks from the module registry whose
        # deps are all already reachable. Repeat until no new task is added so
        # detached-on-detached chains resolve correctly.
        while True:
            added = False
            for t in _TASK_REGISTRY:
                if t.detached and t not in all_tasks:
                    if t.depends_on and all(dep in all_tasks for dep in t.depends_on):
                        all_tasks.add(t)
                        added = True
            if not added:
                break

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

    def _validate_signatures(self, tasks: set[TaskDef]) -> None:
        """Fail at graph-build time if a task body can't receive a dep by name.

        Deps are passed to the body as kwargs keyed by the producer's TaskDef
        name. If the consumer's signature has no matching parameter (and no
        **kwargs), the run would otherwise die mid-flight with a confusing
        TypeError. Catch it here with a message that names both ends.
        """
        for t in tasks:
            if not t.depends_on:
                continue
            try:
                params = inspect.signature(t.fn).parameters
            except (ValueError, TypeError):
                continue  # builtins / C functions — can't introspect, skip
            if any(p.kind == inspect.Parameter.VAR_KEYWORD
                   for p in params.values()):
                continue  # **kwargs absorbs anything
            accepted = {
                name for name, p in params.items()
                if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                              inspect.Parameter.KEYWORD_ONLY)
            }
            for dep in t.depends_on:
                if dep.name not in accepted:
                    raise ValueError(
                        f"Task '{t.name}' depends on '{dep.name}', but its "
                        f"function has no parameter named '{dep.name}'. "
                        f"Rename the parameter to match, add **kwargs, or set "
                        f"@task(name=...) on the dependency."
                    )

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

            # Journal replay: tasks whose step_key is already Completed return
            # their cached value without re-running. A miss falls through to a
            # live run; key chaining means an edited task's dependents miss too.
            if self.journal_path:
                cached_hits = []
                live = []
                for t in layer:
                    cr = self._cached_result(t)
                    if cr is not None:
                        self.results[t.name] = cr
                        cached_hits.append(t.name)
                    else:
                        live.append(t)
                if cached_hits:
                    _log("CACHED", tasks=",".join(cached_hits))
                layer = live
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
                        td = futures[future]
                        result = future.result()
                        if self.journal_path:
                            result.step_key = self._step_keys.get(td)
                        self.results[result.name] = result
                        self._journal_append(result)
                        if self.fail_fast and result.state == StepState.FAILED:
                            _log(f"FAIL_FAST triggered by {result.name}")
                            # Cancels queued-but-unstarted siblings. Siblings
                            # already running can't be killed — they finish on
                            # their pool threads — but fail_fast's real job is
                            # done: the next layer won't start.
                            pool.shutdown(wait=False, cancel_futures=True)
                            break
            else:
                for td in layer:
                    result = _run_step(td, self.results)
                    if self.journal_path:
                        result.step_key = self._step_keys.get(td)
                    self.results[result.name] = result
                    self._journal_append(result)
                    if self.fail_fast and result.state == StepState.FAILED:
                        _log(f"FAIL_FAST triggered by {result.name}")
                        break

            if self.fail_fast:
                failed = [r for r in self.results.values()
                          if r.state == StepState.FAILED]
                if failed:
                    break

    def _execute_detached(self, detached_tasks: set[TaskDef]) -> None:
        """Run detached tasks in topologically-sorted layers after the main DAG.
        Failures collected in self.detached_failures, not propagated.

        v1.2.0: Layered execution (was single-layer). A detached task may
        depend on another detached task; layering ensures the dependency
        runs first and its result is available.
        """
        if not detached_tasks:
            return

        detached_layers = self._build_layers(detached_tasks)

        for layer in detached_layers:
            # Filter to tasks whose deps (main + earlier detached layers) all succeeded
            runnable = []
            for t in layer:
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

            # Journal replay for detached side-effects: a cached hit means the
            # side-effect already fired on a prior run — don't re-fire it.
            if self.journal_path and runnable:
                still = []
                cached_hits = []
                for t in runnable:
                    cr = self._cached_result(t)
                    if cr is not None:
                        self.results[t.name] = cr
                        cached_hits.append(t.name)
                    else:
                        still.append(t)
                if cached_hits:
                    _log("CACHED_DETACHED", tasks=",".join(cached_hits))
                runnable = still

            if not runnable:
                continue

            _log("DETACHED", tasks=",".join(t.name for t in runnable))

            if len(runnable) > 1:
                with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                    futures = {
                        pool.submit(_run_step, td, self.results): td
                        for td in runnable
                    }
                    for future in as_completed(futures):
                        td = futures[future]
                        result = future.result()
                        if self.journal_path:
                            result.step_key = self._step_keys.get(td)
                        self.results[result.name] = result
                        self._journal_append(result)
                        if result.state == StepState.FAILED:
                            self.detached_failures.append(result)
            else:
                for td in runnable:
                    result = _run_step(td, self.results)
                    if self.journal_path:
                        result.step_key = self._step_keys.get(td)
                    self.results[result.name] = result
                    self._journal_append(result)
                    if result.state == StepState.FAILED:
                        self.detached_failures.append(result)

    def run(self) -> dict[str, StepResult]:
        """Execute the full DAG from scratch."""
        self.results = {}
        self.detached_failures = []

        main_tasks, detached_tasks = self._collect_tasks()
        self._validate_signatures(main_tasks | detached_tasks)
        if self.journal_path:
            self._compute_keys(main_tasks | detached_tasks)
            self._load_journal()
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
        FAILED and SKIPPED tasks are cleared from results and re-execute."""
        self.detached_failures = []

        # Reset FAILED and SKIPPED tasks
        to_reset = [name for name, r in self.results.items()
                    if r.state in (StepState.FAILED, StepState.SKIPPED)]
        for name in to_reset:
            del self.results[name]

        main_tasks, detached_tasks = self._collect_tasks()
        if self.journal_path:
            self._compute_keys(main_tasks | detached_tasks)
            self._load_journal()
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
        # Build the detached-name set once — including auto-discovered
        # detached tasks, which a terminal-only walk would miss.
        _, detached_tasks = self._collect_tasks()
        detached_names = {t.name for t in detached_tasks}
        lines = []
        for name, r in self.results.items():
            status = r.state.value.upper()
            dur = f"{r.duration_ms:.0f}ms"
            att = f"x{r.attempts}" if r.attempts > 1 else ""
            err = f" err={r.error}" if r.error else ""
            det = " [detached]" if name in detached_names else ""
            lines.append(f"  {status:9s} {name} ({dur}{att}){det}{err}")
        return "\n".join(lines)
