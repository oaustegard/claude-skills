# Project setup: what the project must provide before a swarm can work on it

The harness is generic; these are the project-side conditions the 2026-10-12 haiku-cc
run showed it depends on. Each names its signal.

## Failing-test supply, ahead of the swarm

The queue is only as deep as the failing tests. Haiku cleared haiku-cc's conformance
suites in 70 minutes (67 merges, $2.62) and the queue drained at 04:33. Before launch:

- Collect suites with **thousands** of tests, and at least one tier of real programs
  (whole-program builds: one root cause, hundreds of tests; sqlite's
  `__sync_synchronize` fix cost $0.007). A generator (csmith for C) gives unbounded supply.
- Keep a **suite builder** running ahead of the swarm: one agent (Agent tool, it is
  under ten tasks) or a session that adds suites and commits them.
- The builder works in **its own worktree** and commits atomically to main. Diagnosed
  2026-10-12: builders edited the shared main checkout, preflight reported a dirty
  tree, and the loop had to run with `--force`. `git worktree add ../builder main`, work
  there, `git -C ../builder commit`, then fast-forward main from it.
- Signal: `status` SIGNALS `SUPPLY LOW` (fewer than 10 dispatchable items) or
  `PARTITION EXHAUSTED`.

New suites need no restart. The loop checks every two minutes for new, edited or
deleted suite directories (committed, or present on disk but never baselined) and
baselines only those (`merge.refresh_suites`). A change elsewhere in the tests tree
(the runner itself) triggers a full refresh.

## The test command's output decides cluster quality

Contract: `{test_id: {status, reason, stage}}`, `test_id = "<suite>/<rest>"`.
Two runner bugs cost hours on 2026-10-12:
- reasons truncated with the absolute `path:line:col` prefix still in front, so the
  message itself was cut off. **Strip locations before truncating.**
- a broken stage regex labelled every failure `parse`. **Validate stage labels.**

Run `swarm.py doctor --run-suite <suite>` before launch, and on `known.json` after
the first baseline. It fails on contract violations and warns on: one stage holding
over 90% of failures, empty reasons, truncated located reasons, one signature per test
(nothing is masked), one signature holding half the failures (too generic: haiku-cc's
`run: case did not ...` lumps 100 redis tests).

## Flaky tests

A race test that fails with a different count every run, or a suite that times out
under load, rejects good candidates. The gate re-runs every suspected regression once
at half parallelism. For a test that is flaky in itself, add its glob to
`tests.quarantine`: it is never counted as a regression and never queued. Signal:
the same test in `regressions (...)` rejections from unrelated clusters.

## Code architecture a swarm can edit in parallel

Conflicts were the largest single loss on 2026-10-12 (about 170 lost merge races).
The harness turns each into a rebase task, but the project removes the hot spots:
**self-registering modules, so a new entry is a new file**, never an edit to a shared
list. A builtin is `builtins/<family>.py` with a `@builtin` decorator; a handler is a
module discovered by a package scan; a type keyword is its own file. `status` lists
"conflict hot spots" by file; on haiku-cc at 18:30Z they were
`hcc/parser/builtins.py (65)`, `hcc/codegen/__init__.py (30)`. Put the rule in the
project's contract file and in the worker prompt (the template has it).

**Land structural refactors early, or freeze deliberately.** A big refactor mid-run on
2026-10-12 needed a 34-minute freeze of main and a port of 81 in-flight commits. Do it
before launch, or `stop` the loop, land it, then relaunch: workers that finish against
the old layout come back as conflicts and become rebase tasks.

## Hygiene the gate relies on

- **gitignore build artefacts at project init** (`__pycache__/`, `*.pyc`, build dirs).
  Preflight refuses to launch when they are tracked; `paths.junk` keeps them out of
  candidate diffs. `__pycache__` was committed on 2026-10-12.
- **Pin the language version** the fastest interpreter supports, and gate on it with
  `gate.compat_command`. haiku-cc pinned Python 3.11 (PyPy's ceiling) and byte-compiles
  `hcc/` under PyPy per candidate (`tests/bin/hcc-pycheck`).
- **Dispatch the interpreter per input when it pays.** PyPy was 2.1x faster on large
  translation units and 1.8x slower on small tests (JIT warm-up): `tests/bin/hcc-auto`
  picks by input size (200 KB). Driver **cache keys must not contain worktree paths**,
  or every worktree misses the cache: install such wrappers at a tree-independent path.
- `always_suites` must be fast (under a minute): it runs at every gate.

## Worker prompt

Start from [assets/worker_prompt.template.md](../assets/worker_prompt.template.md). It
keeps the parts that held on 2026-10-12: own worktree, no git commits, scratch outside
the repo, smoke baseline before editing, minimal general fix, no edits to tests,
add-a-file rule, the result JSON contract, and "revert and report failed with notes"
(the notes feed the next attempt and feature mode).
