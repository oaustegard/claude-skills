---
name: flowing
description: DAG workflow runner that encodes control flow in code, not prose. Use when a procedure has 3+ steps with branching, retries, or validation that must be enforced — gates as `when=`, edge contracts as `validate=`, predicate loops as `retry_until=`. The runner owns the graph; the LLM provides leaves. Also covers parallel execution, checkpoint resume, detached side-effects.
metadata:
  version: 1.3.0
---

# Flowing — Control Flow in Code, Not Prose

When a procedure needs 3+ steps with branches, retries, or contracts, encode it as a DAG of Python tasks. The runner owns the control flow — branching, retrying, validating, propagating failures. The LLM provides judgment at the leaves.

This is the alternative to writing "first X, then Y, then if Z, retry up to 3 times..." in prose. Prose imperatives are read and generated past. A `@task` graph is structural: the next step physically cannot run until the prior step's output is bound to its parameter, and gates that fire on missing/bad inputs can't be skipped.

## Quick Start

```python
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
```

## Control-Flow Primitives

### `when=` — conditional gate

Run this task only if the predicate (over gathered dep values) is truthy. Falsy → SKIPPED, and the skip propagates to dependents.

```python
@task(depends_on=[fetch], when=lambda fetch: fetch["needs_processing"])
def process(fetch):
    return transform(fetch["payload"])
```

Use for branch selection: route through one task or another based on upstream state. Cleaner than an `if` inside a task body that no-ops downstream tasks via flags.

### `validate=` — edge contract

Validate gathered dep values before the task body runs. Raise → FAILED with **no retry** (bad inputs don't fix themselves). Succeed → proceed to the body.

```python
def must_have_items(fetch):
    if not fetch.get("items"):
        raise ValueError("fetch returned empty payload")

@task(depends_on=[fetch], validate=must_have_items)
def process(fetch):
    return sum(fetch["items"])
```

Use to make the contract between tasks explicit. The validator is the gate; without a passing validator, the body never runs. Compare to "remember to check inputs at the top of the task" — that's prose.

#### Validator and predicate signatures

`validate=` and `when=` callables receive gathered dep values as kwargs *by dep name*, the same way task bodies do. A validator written for a specific dep:

```python
def must_have_title(fetch_url_meta):
    if not fetch_url_meta.get("title"):
        raise ValueError("missing title")
```

works only on tasks whose dep is named `fetch_url_meta`. Reuse it on a task whose dep is named `fetch_bad_meta` and you get `TypeError: must_have_title() got an unexpected keyword argument 'fetch_bad_meta'` at validate time, surfacing as a confusing FAIL with the wrong reason.

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

Same applies to `when=` predicates.

### `retry_until=` — predicate-driven loop

Run the body, then call `retry_until(value)`. True → return the value. False → retry, consuming the `retry=` budget. Useful for self-correcting LLM steps: generate, validate, regenerate.

```python
@task(retry=4, retry_until=lambda r: r["valid"])
def generate_until_valid():
    candidate = llm_call(...)
    return {"valid": passes_schema(candidate), "candidate": candidate}
```

Distinct from `retry=` alone, which only retries on raised exception. `retry_until` retries on *output shape* — the predicate is your gate. On exhaustion, the last value is preserved on the FAILED result for diagnostics.

## Other API

### `@task` decorator (full)

```python
@task(
    depends_on=[other_task],
    retry=2,
    retry_backoff_base_ms=1000,
    retry_max_backoff_ms=30_000,
    timeout_s=60.0,
    detached=True,
    name="custom_name",
    when=lambda **deps: bool,        # v1.1: skip if False
    validate=lambda **deps: None,    # v1.1: raise on bad inputs (no retry)
    retry_until=lambda result: bool, # v1.1: retry body until predicate True
)
def my_step(other_task):
    return result
```

`timeout_s` (v1.3): if set, the body runs in a one-shot worker and a call that
overruns is aborted as a retryable `TimeoutError` — it consumes the `retry=`
budget like any other failure. Python can't kill the orphaned thread, so it
keeps running until the container exits; fine for run-once ephemeral use, not a
hard cancel.

A task body receives each dependency as a kwarg named after the dependency's
TaskDef name. As of v1.3 a mismatch (the body has no parameter of that name and
no `**kwargs`) is caught at `flow.run()` with a clear `ValueError` instead of a
confusing mid-run `TypeError`.

### `Flow` class

```python
flow = Flow(terminal_task, max_workers=5, fail_fast=True)
results = flow.run()
flow.summary()
flow.value(some_task)
```

`fail_fast` stops the *next* layer from starting once a task in the current
layer fails; siblings already running in parallel can't be killed and run to
completion on their pool threads.

`clear_registry()` (module-level function) empties the registry that `@task`
appends to. For run-once container use you never need it; call it between
independent flows in the same process (tests, REPLs) so detached
auto-discovery can't pull a stale task into an unrelated graph.

### Resume from failure

```python
flow = Flow(terminal)
results = flow.run()                    # step_3 fails
flow.override(step_3, corrected_value)  # inject fix
results = flow.resume()                 # step_1, step_2 cached; step_4+ runs
```

`flow.resume()` resets FAILED/SKIPPED tasks, keeps SUCCEEDED cached.
`flow.override(td, value)` manually injects a succeeded result.

### Detached tasks (non-blocking side-effects)

```python
@task(depends_on=[create_issue], detached=True)
def store_memory(create_issue):
    remember(create_issue["url"], ...)
```

Run in topologically-sorted layers after the main DAG. Failures collected in `flow.detached_failures`, never trigger `fail_fast`. Dependencies must all be SUCCEEDED for a detached task to run.

#### Auto-discovery (v1.2.0)

A detached task whose `depends_on` are all reachable from the declared terminals is **auto-discovered** — you don't need to pass it as a terminal:

```python
@task
def main_step(): ...

@task(depends_on=[main_step], detached=True)
def store(main_step): ...

Flow(main_step).run()   # `store` runs automatically after main_step succeeds
```

Detached tasks may depend on other detached tasks; the chain is layered and runs in dependency order. Detached tasks whose deps are NOT reachable from any terminal are ignored — they belong to a different graph and should be terminals of their own `Flow`.

## When to use

- **Procedure has branches that matter.** `when=` makes them structural.
- **Steps have input contracts.** `validate=` makes the contract enforceable.
- **An LLM step needs to converge.** `retry_until=` puts the validator in the loop.
- **3+ independent operations** that can parallelize.
- **Multi-step pipelines** where late failures shouldn't waste early work.
- **Side-effects** (memory storage, notifications) that shouldn't block the critical path.

## When NOT to use

- Single sequential operation (just call the function).
- Next step depends on *reasoning* about prior result that can't be expressed as a predicate (use a think loop with the LLM).
- Async/distributed workflows (this is single-container, ThreadPoolExecutor).

## Authoring discipline

If you find yourself writing prose like *"first call X, then validate Y, then if Z is good proceed, otherwise retry up to 3 times,"* that is a flowing graph. Refactor before shipping. Prose imperatives don't enforce; `@task` graphs do.
