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

Rollback (edit, verify, restore on red):
    @task(undo=restore)
    def before():
        return snapshot(["src/a.py", "src/b.py"])

    @task(depends_on=[before])
    def edit(before): ...

    @task(depends_on=[edit])
    def verify(edit): ...   # raises on a failing test run

    Flow(verify).run()      # verify fails -> before's undo restores both files
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import os
import pickle
import sys
import time
from collections.abc import Callable
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from concurrent.futures import (
    TimeoutError as FuturesTimeoutError,
)
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class StepState(Enum):
    # _run_step is synchronous and only ever returns a terminal state, so
    # PENDING/RUNNING/RETRYING would never be observable — they are omitted
    # rather than defined-but-never-assigned.
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    # Succeeded, then undone because a later main task failed (v1.6). Either
    # its own undo= ran, or it sits downstream of a task whose undo= ran, so
    # its inputs no longer exist. resume() re-runs it; the journal forgets it.
    ROLLED_BACK = "rolled_back"


@dataclass
class StepResult:
    name: str
    state: StepState
    value: Any = None
    error: Exception | None = None
    duration_ms: float = 0
    attempts: int = 0
    step_key: str | None = None  # content-addressed key (set only when journaling)
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
    timeout_s: float | None = None
    detached: bool = False
    # v1.1 control-flow primitives
    when: Callable | None = None         # gate: receives gathered kwargs, returns bool. False -> SKIPPED
    validate: Callable | None = None     # edge contract: receives gathered kwargs, raises on bad inputs. Raise -> FAILED, no retry
    retry_until: Callable | None = None  # predicate loop: receives task return value, returns bool. False -> retry (uses retry= budget)
    # v1.6 compensation
    undo: Callable | None = None         # receives the task's return value; called in reverse completion order when the main DAG fails

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
    fn: Callable | None = None,
    *,
    depends_on: list[TaskDef] | None = None,
    retry: int = 0,
    retry_backoff_base_ms: int = 1000,
    retry_max_backoff_ms: int = 30_000,
    timeout_s: float | None = None,
    name: str | None = None,
    detached: bool = False,
    when: Callable | None = None,
    validate: Callable | None = None,
    retry_until: Callable | None = None,
    undo: Callable | None = None,
) -> TaskDef:
    if undo is not None and detached:
        raise ValueError(
            "undo= cannot be combined with detached=True: detached tasks run "
            "after the main DAG and a main failure never rolls them back"
        )

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
            undo=undo,
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


def _fn_fingerprint(fn: Callable | None) -> str:
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
    detached flag, undo. Tuning a reliability knob, renaming, or changing how
    a step is reversed must not bust the cache; changing what it produces must.
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


@dataclass
class FileSnapshot:
    """Byte-exact contents of a set of files, taken by snapshot().

    files maps each absolute path to its bytes, or to None when the file did
    not exist. missing_dirs lists directories that did not exist either, so
    restore() can remove the ones an edit created for a new file.
    """
    files: dict[str, bytes | None]
    missing_dirs: list[str] = field(default_factory=list)


def snapshot(paths) -> FileSnapshot:
    """Record the current bytes of each path (None for a missing file).

    Pair it with restore() as a task's undo= so a failing later step puts the
    files back:  @task(undo=restore) def before(): return snapshot([...])
    """
    files: dict[str, bytes | None] = {}
    missing: set[str] = set()
    for p in paths:
        ap = os.path.abspath(os.fspath(p))
        try:
            with open(ap, "rb") as fh:
                files[ap] = fh.read()
        except FileNotFoundError:
            files[ap] = None
            d = os.path.dirname(ap)
            while d and not os.path.exists(d):
                missing.add(d)
                d = os.path.dirname(d)
    return FileSnapshot(files=files, missing_dirs=sorted(missing))


def restore(snap: FileSnapshot) -> list[str]:
    """Put every file in snap back to its recorded bytes. Returns changed paths.

    A file that existed is rewritten only if its bytes differ; a file that did
    not exist is deleted, then any directory created for it is removed if it
    is empty. Contents only: permissions and timestamps are not restored.
    """
    changed: list[str] = []
    for p, data in snap.files.items():
        if data is None:
            try:
                os.remove(p)
                changed.append(p)
            except FileNotFoundError:
                pass
            continue
        try:
            with open(p, "rb") as fh:
                if fh.read() == data:
                    continue
        except FileNotFoundError:
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        changed.append(p)
    for d in sorted(snap.missing_dirs, key=len, reverse=True):
        try:
            os.rmdir(d)  # only succeeds when empty
        except OSError:
            pass
    return changed


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
                 journal_path: str | None = None, rollback: bool = True):
        if not terminals:
            raise ValueError("Flow requires at least one terminal task")
        self.terminals = list(terminals)
        self.max_workers = max_workers
        self.fail_fast = fail_fast
        self.results: dict[str, StepResult] = {}
        self.detached_failures: list[StepResult] = []
        # Compensation (v1.6): when a main task fails, completed tasks with
        # undo= are undone in reverse completion order. rollback=False keeps
        # the failed state on disk for inspection.
        self.rollback = rollback
        self.rollback_failures: list[StepResult] = []
        self._live_order: list[TaskDef] = []  # main tasks that succeeded live in this call
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
            if entry.get("kind") == "RolledBack":
                # A later rollback cancels an earlier Completed for the key.
                self._journal_completed.pop(entry.get("key"), None)
                continue
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

    def _cached_result(self, td: TaskDef) -> StepResult | None:
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

    def _journal_rollback(self, result: StepResult) -> None:
        """Append a RolledBack entry so the next run re-executes this step."""
        if not self.journal_path or result.step_key is None:
            return
        line = json.dumps({"kind": "RolledBack", "key": result.step_key,
                           "name": result.name})
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _rollback(self) -> None:
        """Undo this call's completed main tasks after a main-DAG failure.

        Walks the tasks that succeeded live in this call in reverse completion
        order and calls each one's undo(value). A task downstream of an undone
        task is marked ROLLED_BACK as well: its inputs are gone, so resume()
        and the journal must re-run it. Cached (journal-replayed) results are
        never undone; their effects belong to an earlier run. An undo that
        raises leaves its task SUCCEEDED (the effect is still in place) and is
        recorded in self.rollback_failures; the walk continues.
        """
        if not self.rollback:
            return
        if not any(r.state == StepState.FAILED for r in self.results.values()):
            return
        if not any(t.undo is not None for t in self._live_order):
            return
        _log("ROLLBACK", candidates=len(self._live_order))
        undone: set[TaskDef] = set()
        for td in reversed(self._live_order):
            r = self.results.get(td.name)
            if r is None or r.state != StepState.SUCCEEDED or r.cached:
                continue
            if td.undo is not None:
                try:
                    td.undo(r.value)
                except Exception as e:
                    _log(f"ROLLBACK_FAIL {td.name}", error=str(e)[:120])
                    self.rollback_failures.append(replace(r, error=e))
                    continue
                _log(f"UNDONE {td.name}")
                undone.add(td)
        if not undone:
            return
        # Mark undone tasks and everything downstream of them, in completion order.
        rolled: set[TaskDef] = set()
        for td in self._live_order:
            r = self.results.get(td.name)
            if r is None or r.state != StepState.SUCCEEDED:
                continue
            if td in undone or any(dep in rolled for dep in td.depends_on):
                rolled.add(td)
                nr = replace(r, state=StepState.ROLLED_BACK)
                self.results[td.name] = nr
                self._journal_rollback(nr)

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
                    tripped = False
                    for future in as_completed(futures):
                        if future.cancelled():
                            continue
                        td = futures[future]
                        result = future.result()
                        if self.journal_path:
                            result.step_key = self._step_keys.get(td)
                        self.results[result.name] = result
                        self._journal_append(result)
                        if result.state == StepState.SUCCEEDED:
                            self._live_order.append(td)
                        if (self.fail_fast and not tripped
                                and result.state == StepState.FAILED):
                            tripped = True
                            _log(f"FAIL_FAST triggered by {result.name}")
                            # Cancel queued-but-unstarted siblings. Siblings
                            # already running can't be killed, so keep draining:
                            # their results must be recorded for rollback to
                            # undo what they did. The next layer won't start.
                            for f in futures:
                                f.cancel()
            else:
                for td in layer:
                    result = _run_step(td, self.results)
                    if self.journal_path:
                        result.step_key = self._step_keys.get(td)
                    self.results[result.name] = result
                    self._journal_append(result)
                    if result.state == StepState.SUCCEEDED:
                        self._live_order.append(td)
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
        self.rollback_failures = []
        self._live_order = []

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

        # Execute main DAG, then undo it if it failed (before detached tasks,
        # so a side-effect never fires for work that was rolled back)
        self._execute(main_layers)
        self._rollback()

        # Execute detached tasks (only if main DAG didn't fail, or their deps succeeded)
        self._execute_detached(detached_tasks)

        flow_dur = (time.monotonic() - flow_t0) * 1000
        succeeded = sum(1 for r in self.results.values() if r.state == StepState.SUCCEEDED)
        failed = sum(1 for r in self.results.values() if r.state == StepState.FAILED)
        skipped = sum(1 for r in self.results.values() if r.state == StepState.SKIPPED)
        rolled = sum(1 for r in self.results.values() if r.state == StepState.ROLLED_BACK)

        _log("DONE", ms=f"{flow_dur:.0f}",
             succeeded=succeeded, failed=failed, skipped=skipped, rolled_back=rolled)
        return self.results

    def resume(self) -> dict[str, StepResult]:
        """Re-run from failure point. SUCCEEDED tasks keep their cached values.
        FAILED and SKIPPED tasks are cleared from results and re-execute."""
        self.detached_failures = []
        self.rollback_failures = []
        self._live_order = []

        # Reset FAILED, SKIPPED and ROLLED_BACK tasks
        to_reset = [name for name, r in self.results.items()
                    if r.state in (StepState.FAILED, StepState.SKIPPED,
                                   StepState.ROLLED_BACK)]
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
        self._rollback()

        # Re-run detached tasks (they may have been skipped/failed before)
        self._execute_detached(detached_tasks)

        flow_dur = (time.monotonic() - flow_t0) * 1000
        succeeded = sum(1 for r in self.results.values() if r.state == StepState.SUCCEEDED)
        failed = sum(1 for r in self.results.values() if r.state == StepState.FAILED)
        skipped = sum(1 for r in self.results.values() if r.state == StepState.SKIPPED)
        rolled = sum(1 for r in self.results.values() if r.state == StepState.ROLLED_BACK)

        _log("DONE", ms=f"{flow_dur:.0f}",
             succeeded=succeeded, failed=failed, skipped=skipped, rolled_back=rolled)
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
