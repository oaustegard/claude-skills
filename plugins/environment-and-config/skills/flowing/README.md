# flowing

A lightweight DAG workflow runner for Claude's ephemeral containers. Declare steps, wire dependencies, run once — control flow lives in code, not in prose imperatives.

## The problem it solves

Multi-step procedures are usually written as prose: *"first fetch X, then validate Y, then if Z retry up to 3 times, otherwise skip ahead."* An LLM reads and **generates past** prose like that — the gate is a suggestion, not a wall. Skipped validation, retries that never happen, branches taken on stale state.

A `@task` graph is **structural** instead. A step physically cannot run until its inputs are bound to its parameters. A gate that fires on missing or bad input can't be stepped over. The runner owns branching, retrying, validating, failure propagation, and parallelism; the LLM only supplies judgment at the leaves.

```python
from flowing import task, Flow

@task
def fetch_data():
    return {"items": [1, 2, 3]}

@task(depends_on=[fetch_data])
def process(fetch_data):          # param name matches the dep's name
    return sum(fetch_data["items"])

@task(depends_on=[process])
def store(process):
    print(f"Result: {process}")

Flow(store).run()                 # topo-sorts into layers, parallel within a layer
```

## Control-flow primitives

The distinctive part — branches and contracts as graph structure, not `if` statements buried in task bodies.

| Primitive | What it does | Use for |
|---|---|---|
| `when=` | Predicate over dep values; falsy → task SKIPPED, skip cascades to dependents | Branch selection in the topology |
| `validate=` | Checks dep values before the body runs; raise → FAILED with **no retry** | Enforceable input contracts between steps |
| `retry_until=` | Predicate over the return value; falsy → retry, consuming the `retry=` budget | Self-correcting LLM steps (generate → check → regenerate) |

`retry_until=` is distinct from `retry=` alone: `retry=` only retries on a raised exception, `retry_until=` retries on *output shape*.

## Also handles

- **Parallel execution** — independent tasks in a layer run on a thread pool.
- **Resume** — `run()` → fix → `resume()` re-runs from the failure point, keeping succeeded tasks cached. `override()` injects a corrected value for a step resolved out-of-band.
- **Detached side-effects** — `detached=True` tasks (memory writes, notifications) run after the main DAG and never block it on failure.
- **`timeout_s=`**, **`retry=`** with exponential backoff, **`fail_fast=`**.

## Layout

| File | Audience | Contents |
|---|---|---|
| [`SKILL.md`](SKILL.md) | Claude | Trigger, mental model, quick start, the three primitives, when / when-not-to-use |
| [`references/reference.md`](references/reference.md) | Claude | Full API — every `@task` parameter, `Flow` methods, resume/override, detached auto-discovery, signature gotchas |
| [`scripts/flowing.py`](scripts/flowing.py) | — | The runner itself (no third-party dependencies) |
| [`tests/test_flowing.py`](tests/test_flowing.py) | — | 28 tests — `python3 -m unittest tests.test_flowing` |
| [`CHANGELOG.md`](CHANGELOG.md) | — | Version history |

## When to reach for it

Use it when a procedure has branches that matter, steps with input contracts, an LLM step that needs to converge, 3+ operations that can parallelize, or a pipeline where late failures shouldn't waste early work.

Skip it for a single sequential operation (just call the function), for a next step that needs open-ended *reasoning* about the prior result rather than a predicate (use a think loop), or for async / distributed workflows (this is single-container, thread-pool based).

## Complements

- **[orchestrating-agents](../orchestrating-agents)** — parallel API instances and delegated sub-tasks. `flowing` orders and gates work *within* one container; orchestrating-agents fans work *out* across many.
- **[tiling-tree](../tiling-tree)** — MECE partitioning of a problem space. Tiling-tree decides *what* the branches are; `flowing` enforces the execution order once they exist.
- **[tracking-todos](../tracking-todos)** — a human-legible checklist for loose, evolving work. `flowing` is for procedures whose shape is known up front and worth encoding as a graph.
