# Flowing — API Reference

Full surface of `scripts/flowing.py`. The core workflow and the three
control-flow primitives are in [SKILL.md](../SKILL.md); read this when you need
anything beyond the quick start.

## `@task` decorator

```python
@task(
    depends_on=[other_task],         # TaskDefs this task consumes
    retry=2,                         # extra attempts on raised exception (total = 1 + retry)
    retry_backoff_base_ms=1000,      # exponential backoff base
    retry_max_backoff_ms=30_000,     # backoff ceiling
    timeout_s=60.0,                  # abort a hung body (see below)
    detached=True,                   # side-effect task; see "Detached tasks"
    name="custom_name",              # override the TaskDef name (default: function name)
    when=lambda **deps: bool,        # conditional gate — falsy skips the task
    validate=lambda **deps: None,    # edge contract — raise to FAIL with no retry
    retry_until=lambda result: bool, # predicate loop — falsy retries the body
)
def my_step(other_task):
    return result
```

### Dependency naming

A task body receives each dependency as a kwarg named after the dependency's
TaskDef name — its function name, or the `name=` override. If the body has no
parameter of that name and no `**kwargs`, `flow.run()` raises a clear
`ValueError` at graph-build time rather than failing mid-run with a `TypeError`.

### `timeout_s`

If set, the body runs in a one-shot worker thread; a call that overruns is
aborted as a retryable `TimeoutError` and consumes the `retry=` budget like any
other failure. Python can't kill the orphaned thread, so it keeps running until
the container exits — fine for run-once ephemeral use, but not a hard cancel.

## `Flow` class

```python
flow = Flow(terminal_task, max_workers=5, fail_fast=True)
results = flow.run()       # dict[str, StepResult]
flow.summary()             # human-readable status table
flow.value(some_task)      # return value of a succeeded task
```

`fail_fast` stops the *next* layer from starting once a task in the current
layer fails. Siblings already running in parallel can't be killed and run to
completion on their pool threads.

## Resume from failure

```python
flow = Flow(terminal)
results = flow.run()                    # step_3 fails
flow.override(step_3, corrected_value)  # inject a fix obtained out-of-band
results = flow.resume()                 # step_1, step_2 stay cached; step_4+ runs
```

`flow.resume()` clears FAILED/SKIPPED tasks from results and re-runs them,
keeping SUCCEEDED tasks cached. `flow.override(td, value)` manually injects a
succeeded result.

## Detached tasks (non-blocking side-effects)

```python
@task(depends_on=[create_issue], detached=True)
def store_memory(create_issue):
    remember(create_issue["url"], ...)
```

Detached tasks run in topologically-sorted layers after the main DAG. Failures
land in `flow.detached_failures` and never trigger `fail_fast`. All dependencies
must be SUCCEEDED for a detached task to run.

### Auto-discovery

A detached task whose `depends_on` are all reachable from the declared terminals
is auto-discovered — you don't pass it as a terminal:

```python
@task
def main_step(): ...

@task(depends_on=[main_step], detached=True)
def store(main_step): ...

Flow(main_step).run()   # `store` runs automatically after main_step succeeds
```

Detached tasks may depend on other detached tasks; the chain is layered and runs
in dependency order. Detached tasks whose deps are NOT reachable from any
terminal are ignored — they belong to a different graph and should be terminals
of their own `Flow`.

## `clear_registry()`

Module-level function that empties the registry `@task` appends to. For
run-once container use you never need it; call it between independent flows in
the same process (tests, REPLs) so detached auto-discovery can't pull a stale
task into an unrelated graph.

## `validate=` and `when=` signatures

`validate=` and `when=` callables receive gathered dep values as kwargs *by dep
name*, the same way task bodies do. A validator written for a specific dep:

```python
def must_have_title(fetch_url_meta):
    if not fetch_url_meta.get("title"):
        raise ValueError("missing title")
```

works only on tasks whose dep is named `fetch_url_meta`. Reuse it on a task
whose dep is named `fetch_bad_meta` and you get `TypeError: must_have_title()
got an unexpected keyword argument 'fetch_bad_meta'` at validate time, surfacing
as a confusing FAIL with the wrong reason.

Two patterns to avoid the trap:

```python
# A) Reusable: take **kwargs, look up by expected key
def must_have_title(**kwargs):
    meta = next(iter(kwargs.values()))
    if not meta.get("title"):
        raise ValueError("missing title")

# B) Factory: bind the dep name explicitly at task definition
def must_have_title_of(dep_name):
    def v(**kwargs):
        if not kwargs[dep_name].get("title"):
            raise ValueError(f"{dep_name}: missing title")
    return v

@task(depends_on=[fetch], validate=must_have_title_of("fetch"))
def process(fetch): ...
```
