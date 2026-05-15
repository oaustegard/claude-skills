---
name: flowing
description: DAG workflow runner that encodes control flow in code, not prose. Use when a procedure has 3+ steps with branching, retries, or validation that must be enforced — gates as `when=`, edge contracts as `validate=`, predicate loops as `retry_until=`. The runner owns the graph; the LLM provides leaves. Also covers parallel execution, checkpoint resume, detached side-effects.
metadata:
  version: 1.3.2
---

# Flowing — Control Flow in Code, Not Prose

When a procedure needs 3+ steps with branches, retries, or contracts, encode it as a DAG of Python tasks instead of prose imperatives. Prose like "first X, then Y, then if Z retry 3×" is read and generated past. A `@task` graph is structural: a step physically cannot run until its inputs are bound, and gates that fire on bad inputs can't be skipped.

The runner owns control flow — branching, retrying, validating, propagating failures, parallelizing. You provide judgment at the leaves. Runner: `scripts/flowing.py`.

## Quick Start

```python
from flowing import task, Flow

@task
def fetch_data():
    return {"items": [1, 2, 3]}

@task(depends_on=[fetch_data])
def process(fetch_data):          # param name must match the dep's name
    return sum(fetch_data["items"])

@task(depends_on=[process])
def store(process):
    print(f"Result: {process}")

Flow(store).run()                 # topo-sorts, runs each layer, parallel within a layer
```

Each task receives its dependencies as kwargs named after them. Independent tasks in the same layer run in parallel.

## Control-Flow Primitives

Encode branches and contracts as graph structure, not `if` statements inside task bodies.

### `when=` — conditional gate

Run the task only if the predicate (over gathered dep values) is truthy. Falsy → SKIPPED, and the skip propagates to dependents.

```python
@task(depends_on=[fetch], when=lambda fetch: fetch["needs_processing"])
def process(fetch):
    return transform(fetch["payload"])
```

### `validate=` — edge contract

Check gathered dep values before the body runs. Raise → FAILED with **no retry** (bad inputs don't fix themselves). Pass → proceed.

```python
def must_have_items(fetch):
    if not fetch.get("items"):
        raise ValueError("fetch returned empty payload")

@task(depends_on=[fetch], validate=must_have_items)
def process(fetch):
    return sum(fetch["items"])
```

### `retry_until=` — predicate-driven loop

Run the body, then call `retry_until(value)`. True → done. False → retry, consuming the `retry=` budget. Use for self-correcting LLM steps: generate, check, regenerate.

```python
@task(retry=4, retry_until=lambda r: r["valid"])
def generate_until_valid():
    candidate = llm_call(...)
    return {"valid": passes_schema(candidate), "candidate": candidate}
```

Distinct from `retry=` alone, which only retries on a raised exception.

## Other capabilities

- **Parallel execution** — independent tasks in a layer run on a thread pool (`max_workers=`).
- **`detached=True`** — side-effect tasks (memory writes, notifications) that run after the main DAG and never block it on failure.
- **Resume** — `flow.run()` → fix → `flow.resume()` re-runs from the failure point, keeping succeeded tasks cached. `flow.override(task, value)` injects a corrected result.
- **`timeout_s=`**, **`retry=`** with exponential backoff, **`fail_fast=`**.

Read [references/reference.md](references/reference.md) before using anything beyond the quick start and the three primitives above — it covers every `@task` parameter, the `Flow` methods, resume/override, detached auto-discovery, and the `validate=`/`when=` signature-matching gotcha.

## When to use

- A procedure has branches that matter → `when=` makes them structural.
- Steps have input contracts → `validate=` makes them enforceable.
- An LLM step needs to converge → `retry_until=` puts the check in the loop.
- 3+ independent operations that can parallelize.
- Multi-step pipelines where late failures shouldn't waste early work.
- Side-effects that shouldn't block the critical path → `detached=True`.

## When NOT to use

- A single sequential operation — just call the function.
- The next step needs *reasoning* about the prior result that can't be a predicate — use a think loop.
- Async or distributed workflows — this is single-container, thread-pool based.

## Authoring discipline

If you find yourself writing prose like *"first call X, validate Y, then if Z retry up to 3 times"* — that is a flowing graph. Refactor before shipping. Prose imperatives don't enforce; `@task` graphs do.
