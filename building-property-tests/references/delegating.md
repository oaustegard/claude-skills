# Running the hunt across agents

One agent per independent area (query paths, containers/serialization, stateful objects and caches, encode/numerics), not per property kind. The orchestrator reproduces, triages and fixes.

Tell the user the expected spend first: about 400–500k tokens per Sonnet worker.

## Brief

Write the task, deliverables and constraints; name the area's entry points and contract documents. Do not restate session context (`delegating-with-context` appends it). Include:

1. This skill's path.
2. The target, installed and importable, and its commit SHA.
3. Deliverables in the worker's own directory: `test_<area>_props.py`, `test_<area>_regressions.py` (one deterministic test per confirmed finding, failing on current code), mutant runner and results, event counts.
4. Constraints:
   - Do not modify the target; do not commit.
   - Wait on long runs with a background job and its completion notification; never a `sleep` or polling loop (auto mode denies it).
   - Return the report as the final message; subagents cannot write report files.
   - Keep each pytest run under ~5 minutes; `deadline=None`.
   - Separate confirmed, ambiguous (`xfail(strict=True)`) and documented-limitation cases.
   - Check both sides of every failure; the harness may be wrong.
5. Report format: findings by severity, each with contract `file:line`, minimal repro, regression test name, suspected root cause, fix sketch, confirmed/ambiguous; then properties passed with example counts, mutants caught or not, blind spots.

A worker stopped by a spend limit keeps its transcript: resume it with SendMessage after the reset, do not respawn. Save each worker's final report to its directory yourself.

## Orchestrator

1. Reproduce every confirmed finding in a plain script before fixing.
2. Fix in a worktree while workers run against the original; run each worker's regressions with `PYTHONPATH=<worktree>`.
3. Distil fixed findings into one regression file in the target repo; show each case failing on the old commit and passing on the new.
4. Run the target's full suite; read any existing test that now fails because a guard fires earlier, and do not loosen it.
5. Keep discovery suites in an experiments repo with a script that reruns them on both commits.
