---
name: flowing
description: DAG workflow runner that encodes control flow in code, not prose. Use when a procedure has 3+ steps with branching, retries, or validation that must be enforced — gates as `when=`, edge contracts as `validate=`, predicate loops as `retry_until=`. The runner owns the graph; the LLM provides leaves. Also covers parallel execution, checkpoint resume, detached side-effects.
metadata:
  version: 1.4.0
---

## NOT SUPERSEDED BY DYNAMIC WORKFLOWS — read first

Claude Code's dynamic workflows orchestrate **subagents** (separate contexts,
fan-out to 16-concurrent / 1000-agent). This skill is a **different primitive**:
single-context control flow over YOUR OWN tool calls, with durable side-effects
and checkpoint resume. The workflows runtime explicitly cannot touch the
filesystem or shell directly — its agents do the work and the script only
coordinates them. Flowing is the inverse: the script does the work.

Use flowing for an in-context pipeline (3+ steps, branches, retries, validation,
detached side-effects). Use a workflow when you need many subagents. They compose;
they do not compete. Do not abandon flowing for a workflow — you would lose the
durable side-effects and the cross-session checkpoint that hub-spoke depends on.

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
- **In-process resume** — `flow.run()` → fix → `flow.resume()` re-runs from the failure point, keeping succeeded tasks cached **in memory** (same process only). `flow.override(task, value)` injects a corrected result.
- **Durable journal (`journal_path=`)** — opt-in content-addressed replay that survives container death. `Flow(term, journal_path="/path/run.jsonl").run()` appends each succeeded task's result to an append-only JSONL keyed by a `step_key` = SHA-256 over the task's bytecode + its `when`/`validate`/`retry_until` bodies + its dependencies' keys (chained, so an upstream change propagates downstream). A later `run()` — even in a fresh container — replays the unchanged prefix from the journal and only executes tasks whose key is absent; editing a task body busts its key and re-runs it and its dependents, while cosmetic knobs (`retry=`, `timeout_s=`, `name`) do not. This is the cross-session checkpoint hub-spoke work relies on. Caveat: results are pickled, so non-picklable return values simply re-run; closure-captured values are not part of the key (only the task body's own code is).
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
