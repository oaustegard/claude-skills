# Running the hunt across agents

Load this when the target has more than one independent area and the work is
worth parallel agents. One agent per area, each with its own harness. The
orchestrator reproduces, triages and fixes.

## Split by area, not by property kind

Areas that share no state each get a worker: search or query paths, containers
and serialization, stateful objects and caches, encode or numerics. A split by
property kind ("all round trips") sends four agents through the same code with
four partial models. On remex (2026-11-16) four area workers produced 68
failing regression cases across 19 defects. Three of them found the same
warm-cache guard bypass independently. Read that agreement as a confidence
signal, not as waste.

## The brief

Write the task, the deliverables and the constraints. Name the area's public
entry points and the contract documents (README, CLAUDE.md, docstrings). In
claude-workspace a hook appends the session context, so do not restate it
(`delegating-with-context`). Each worker gets:

1. The method: this skill's path, or the steps pasted in.
2. The target, installed and importable. State the commit SHA.
3. Deliverables in its own directory: `test_<area>_props.py`,
   `test_<area>_regressions.py` (one deterministic test per confirmed finding,
   failing on the current code), the mutant runner and its results, and event
   counts.
4. Constraints, each from a diagnosed failure:
   - **Do not modify the target and do not commit.** The orchestrator fixes the
     code, in a separate worktree, so harness runs stay comparable.
   - **Wait on long runs with a background job and its completion
     notification, never a `sleep` or polling loop.** Three of four remex
     workers were stopped by an auto-mode denial for exactly that
     (2026-11-16).
   - **Return the report as the final message.** The Write tool refuses report
     files from subagents ("Subagents should return findings as text"). Two
     remex workers lost their `REPORT.md` to this, so the orchestrator saves
     the report itself.
   - **Keep each pytest run under about five minutes**, and use `deadline=None`.
   - **Separate confirmed contract violations from ambiguous cases and from
     documented limitations.** Mark the ambiguous ones `xfail(strict=True)`.
   - **Investigate both sides of every failure.** The harness may be wrong.
5. A final-report format: findings by severity, each with the contract cited
   as `file:line`, a minimal repro, the regression test name, a suspected root
   cause, a fix sketch, and confirmed or ambiguous. Then properties passed with
   example counts, mutants and whether each was caught, and blind spots.

## Budget

On remex each Sonnet worker used about 400–490k tokens and ran 40–65 minutes,
and two of four hit the account's spend limit mid-run. A worker stopped this
way keeps its transcript: resume it with SendMessage once the limit resets.
A new agent starts from nothing. Tell the user the expected spend before
launching four.

## Orchestrator's half

1. Reproduce every confirmed finding in a plain script, outside the harness,
   before fixing it.
2. Fix in a worktree (`git worktree add ../target-fix -b fixes`) while workers
   keep running against the original checkout. Run each worker's regression
   file with `PYTHONPATH=<worktree>`.
3. Distil the fixed findings into one regression file in the target repo. Show
   every case failing on the old commit and passing on the new one.
4. Run the target's full suite. Expect a few existing tests to need changes
   where a guard now fires earlier. Read each one; do not loosen it.
5. Keep the discovery suites in an experiments repository, with a script that
   reruns them against both commits and writes the numbers the write-up cites.
