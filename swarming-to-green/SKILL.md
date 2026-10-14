---
name: swarming-to-green
description: Runs a long swarm of hundreds to thousands of cheap headless coding workers that drive a large failing-test backlog to green. Failures are clustered by signature, each worker fixes one cluster in its own git worktree, a serial no-regression merge gate lands the fixes, the loop resumes across restarts for hours, and it federates across sibling sessions over git branches when one container's CPU is not enough. Use for "fix these thousands of failing tests with a Haiku swarm", "drive the test suite to green with hundreds of agents", "build this compiler or interpreter against a conformance suite", "launch, relaunch or check in on the swarm loop", "the swarm is stuck, idle or rejecting everything", "parallel agents fixing tests keep hitting merge conflicts and regressions", "add sibling containers to the swarm", or "compare models on the tail the swarm could not fix". Ships the harness, a per-project TOML config, a fake-worker selftest, check-in signals and the 2026-10-12 haiku-cc failure catalogue.
metadata:
  version: 0.7.0
---

# Swarming to green

A loop that turns a test suite's failures into merged fixes, unattended, for hours:

```
known.json --cluster by signature--> work items --one headless worker each, own worktree-->
  result JSON --serial gate: apply on main, compat check, run smoke + targets + sample,
  zero regressions, >=1 target flips--> fast-forward main --> re-check the whole cluster --> repeat
```

Every mechanism in it fixed a failure that cost hours on 2026-10-12, when Haiku 5.5
workers built hcc (a C compiler in Python) against ~42K tests: 1,051 hub workers, 464
merges, $24.88 of worker spend by 18:30Z. The catalogue of those failures, each with
its signal and where it is handled, is
[references/run-2026-10-12.md](references/run-2026-10-12.md).

```bash
SK=/mnt/skills/user/swarming-to-green       # or <claude-skills clone>/swarming-to-green
SWARM="python3 $SK/scripts/swarm.py"             # every command below; --root defaults to the git toplevel
```

## When to use it, and when not

Use it when **all** hold: a test command can report every test's status as JSON;
there are hundreds or more failing tests; a fix can be checked by re-running tests; and
the work will run for hours, longer than anyone watches.

| situation | use instead |
|---|---|
| fewer than ten tasks, e.g. setup, a suite builder, a refactor | the Agent tool directly (on 2026-10-12, 3 setup agents were run through claude -p for no gain) |
| a one-off fan-out of independent tasks (judges, extractors, per-file reviews) with no merging | `dispatching-subagents` |
| which model or effort a worker gets, and how to escalate | `agent-routing` (this skill's measured answer for test-fix work is in "Which model" below) |
| a fixed multi-step pipeline with no model in the loop | `flowing` |
| parallel Claude calls from claude.ai chat | `orchestrating-chat-agents` (`orchestrating-agents` is its deprecated name) |
| a handful of failing tests | fix them yourself, or one Agent-tool worker per cluster |
| no machine-readable test output yet | write the runner first ("Project setup"), then come back |

**Abandon the run** when the signals say the harness, not the workers, is the problem:
`SAME FAILURE`, `DENIALS` or `GATE REJECTS ALL` twice in a row after a fix. Stop the
loop (`$SWARM stop`), fix the cause, `unpark` if the fix invalidates earlier attempts,
relaunch. Spending through a harness bug is how the abandoned tail was made.

## Preflight checklist

Do every item before the first real launch. Each one cost hours when missed.

1. **Failing-test supply first.** Haiku drained haiku-cc's conformance suites in 70
   minutes and the queue sat empty. Have thousands of failing tests, a tier of real
   programs (one build failure blocks hundreds of tests), and a suite builder that
   works in its own worktree and commits to main. The loop baselines new suites within
   two minutes. Details: [references/project-setup.md](references/project-setup.md).
2. **Plan containers now if workers do real compute.** When each worker compiles and
   runs tests, CPU caps the swarm whatever the launch mechanism: 4 vCPU held haiku-cc
   at load 10-22 for eight hours before siblings were added. Decide the partition and
   the number of sibling sessions at preflight: [references/scaling-out.md](references/scaling-out.md).
3. **Disk.** `df -h /tmp <root>/..` needs 10 GB or more free. Worker scratch reached
   14 GB and stale worktrees 5.6 GB on 2026-10-12. The loop deletes scratch on reap,
   sweeps stale worktrees at start, and stops launching below `run.min_free_gb`.
4. **The 2-hour background cap.** A background Bash job dies at 2 hours, and at 30
   minutes if you omit `timeout`. Launch with `timeout: 7200000` and `--max-minutes 110`;
   the loop exits cleanly, workers keep running, and the next launch adopts them.
5. **Coordinator models.** Every session you create inherits your model unless you
   pass `model`. Idle Opus siblings cost about $1.40 per check-in. Give siblings and
   experiment sessions a Sonnet or Haiku model.
6. **Push namespace.** Federation pushes `<prefix>main/state/cand/*`. A push-policy guard
   (claude-workspace `scripts/guards.py` `_ALLOWED_PREFIXES`) must allow the prefix.
7. **Gitignore build artefacts and pin the language version** the fast interpreter
   supports; set `gate.compat_command` to enforce the pin.

## Setup

1. **Config.** Copy [assets/swarm.example.toml](assets/swarm.example.toml) to
   `<root>/swarm.toml` and fill `tests.command`, `paths.code/allowed/forbidden`,
   `queue.ladder`, `gate.always_suites/cheap_suites`, `gate.compat_command`,
   `worker.system_prompt`, `worker.repro_command`, and `worker.deny` for whatever the
   workers must never run (network fetches when the answer is on the internet). Every key:
   [references/config.md](references/config.md). A complete working config for haiku-cc
   is [assets/haiku-cc.toml](assets/haiku-cc.toml).
2. **Worker prompt.** Start from [assets/worker_prompt.template.md](assets/worker_prompt.template.md).
   Keep the result-JSON contract, "no git commits", "scratch outside the repo",
   "add a file, don't edit a shared list", and "revert and report failed with notes".
3. **Check the runner's output:** `$SWARM doctor --run-suite <a suite>`. It exits 1 on
   a contract violation and prints WARN lines for a stage label on over 90% of failures,
   truncated located reasons, or signatures that do not cluster. Fix the runner before
   launch: on 2026-10-12 a broken stage regex labelled every failure `parse`. A stage
   that holds nearly every failure by design (decompilation: all `missing` at the start,
   nearly all `match` later) goes in `tests.one_stage_ok`.
4. **Selftest the harness** (no model calls, about 3 minutes):
   ```bash
   $SWARM selftest; echo "selftest exit=$?"
   ```
   Exit 0 means every check passed. Read the exit code, never a `tail` of the output.
5. **Dry look at the queue:** `$SWARM refresh` (first baseline), then `$SWARM queue --top 20`.
   The top items should be the clusters you would hand out first. If they are not, fix
   `queue.ladder` now.

## Launch

One Bash call, `run_in_background: true`, `timeout: 7200000`. Run the loop itself, not
a waiter, not `nohup`, and not inside a subagent (a subagent's background job dies
with the subagent):

```bash
cd <root> && $SWARM run --concurrency 24 --max-usd 50 --max-minutes 110 \
    --batch 6 --sample 80 >> runs/swarm.log 2>&1
```

In the same turn: `ps aux | grep '[s]warm.py run'` shows it, and
`tail -5 runs/swarm.log` shows `LAUNCH` lines or a first `full refresh`. Preflight
failures print `preflight:` lines and exit 2; fix them rather than passing `--force`.
Then end the turn and arm the first check-in:
`send_later(delay_minutes=50, initiation="own_followup", message="swarm check-in: ...")`.

Useful flags: `--only 'suiteA/*,suiteB/*'` (dispatch only these), `--suites` (what this
node's gate runs), `--model`, `--effort`, `--max-workers N`, `--no-launch`.

## Check-in protocol

Every ~50 minutes, by a self-re-arming `send_later`. Never loop on `sleep`.

```bash
tail -40 runs/swarm.log; $SWARM status; df -h /tmp <root>/..
```

Read the `SIGNALS:` block at the end of `status` and act:

| signal | meaning | act |
|---|---|---|
| none, loop alive | healthy | re-arm the check-in |
| loop not running / `DEAD (stale pid file)` | `--max-minutes` exit, the 2-hour cap, or a crash | read the log tail for a traceback; relaunch the same command |
| `REFRESHING` | a refresh owns the gate tree; merging is paused | wait; a full refresh past an hour means raise `gate.full_every` (or set it to 0 and rely on the sweep), a quick one past ~10 min means trim `gate.quick_suites`, a sweep step past ~20 min means that suite is too slow to rotate: split it |
| `SWEEP BEHIND` | a suite has gone over twice `gate.sweep_lag` merges without running on main | refreshes are starving the rotation or merges outpace it: lower `quick_every` or raise `sweep_lag`, never turn the sweep off mid-run |
| `SWEEP REGRESSIONS` | a sweep step found regressions it could not revert | read the log's `bisect`/`revert` lines; revert the culprit by hand while it is at most `sweep_lag` merges back |
| `SWEEP ERROR` | the test command produced nothing for a suite on its sweep | `doctor --run-suite <suite>`; until fixed, that suite's pass count is unchecked |
| `QUICK REGRESSIONS` | the last quick refresh found regressions it could not revert | read the log's `bisect`/`revert` lines; revert the culprit by hand now, while it is at most `gate.quick_every` merges back |
| `GATE BACKLOG` | finished workers outrun the gate | raise `--batch`, lower `--sample`, or lower `--concurrency` so the gate gets CPU (haiku-cc: ~15 to ~41 merges/h) |
| `CPU-BOUND` (log: `THROTTLE`) | load above the throttle with work waiting | scale out: [references/scaling-out.md](references/scaling-out.md) |
| `SUPPLY LOW` | under 10 dispatchable items | start or speed up a suite builder now |
| `PARTITION EXHAUSTED` (log: `IDLE`) | nothing dispatchable on this node | add supply, re-partition, `unpark` after a harness fix, or stand the node down |
| `SAME FAILURE` | most recent workers fail with one reason | a prompt, auth or permission bug: stop, fix, relaunch |
| `DENIALS` | workers hit permission denials | check `worker.allow` against what the prompt tells them to do |
| `GATE REJECTS ALL` | nothing merged in the last 15 gated | read `.swarm/rejected/`; one test named in all = stale known state or a cross-partition regression: `refresh --only-suites <suite>` |
| `DISK LOW` (log: `DISK`) | free space under 2x `min_free_gb` | find the hog (`du -sh /tmp/* <wt_root>/*`); the loop already stopped launching |
| `UNBASELINED SUITES` | suite dirs the baseline never ran | normally clears within 2 minutes; else `refresh --only-suites` |
| `ONE STAGE` | one stage label on over 90% of failures | the runner's stage detection is broken: `doctor`, fix the runner |

Also read the plain lines: `quick refresh:` (cadence, merges since the last, and its
last result: regressions found, reverted, left), `sweep:` (the bound, the worst lag and the
last step's outcome), `base check:` (items not launched because their tests already passed
at HEAD), `conflict hot spots` (a shared file workers keep
colliding on: make it self-registering, see project-setup), `top rejection/failure
reasons`, `last merge ... ago`, and `known now` pass counts.

## Scaling out

When one container's CPU is the cap, add sibling sessions, each owning a partition of
the suites, joined through branches of one git repo with a hub that owns main and
re-gates every candidate. The full procedure (when, partitioning, transport and its
guard prerequisites, the sibling brief, `create_session` parameters, the cross-partition
gate rule, stand-down and ledger collection, isolated experiment sessions) is
[references/scaling-out.md](references/scaling-out.md). Brief template:
[assets/sibling-brief.md](assets/sibling-brief.md). Bootstrap script:
`scripts/sibling_setup.sh`.

## Which model

Default: **Haiku plus the harness's retry ladder.** Treat Sonnet as an optional rung for
a cluster that has failed the whole Haiku ladder, and never escalate a tail the harness
created.

Measured 2026-10-12 on haiku-cc over three escalation runs (40, 4 and 10 clusters after
base checks; same prompt, budget and base; each patch graded in isolation):

| arm | solve rate | $ per solve |
|---|---|---|
| Haiku 5.5, default effort | 76/80, 8/8, 19/20 runs | $0.011-0.012 |
| Haiku 5.5, high effort | 8/8, 20/20 (runs 2-3) | $0.018-0.023 |
| Sonnet 5.5, medium | 80/80, 8/8, 20/20 | $0.075-0.087 (about 7x Haiku) |

Over 54 clusters, cold Sonnet solved 2 that cold Haiku did not (run 1, c06 and c16).
Haiku feature-mode workers in the live swarm fixed both later for $0.054 and $0.022:
the retry path (notes from failed attempts, feature budget, effort ladder) closed both
gaps. Run 3 was the tail the swarm had abandoned; Haiku solved it cold once the
harness bugs that had parked it were fixed. The harness made that tail, not a Haiku
capability limit. Scope: one compiler workload, small n. Re-measure on a new workload
with `$SWARM compare select|run|report`, in its own container
(`compare` selects from the abandoned tail at HEAD and base-checks the selection,
because random failing clusters saturate and known state goes stale).

A second workload had a real Haiku ceiling. On matching decompilation (2026-10-13, gcc
`-O2`, 1,768 functions) the tail Haiku left was large, loop-heavy functions, and each
effort step past `high` bought fewer of them at a steeper price per function flipped:
default $0.039, `high` $0.20, `high` feature $0.58, `xhigh` $1.30, `max` $3.90. Climb
past `high` to learn where the ceiling is, not to clear a tail cheaply. Details:
[references/run-2026-10-13.md](references/run-2026-10-13.md).

The ladder the harness runs per signature: attempt 1 at the configured effort; after a
real failure (a lost merge race is not one) at the next rung of `worker.effort_ladder`
(default `["", "high"]`; Haiku 5.5 also takes `xhigh` and `max`); after `feature_after`
failures a single feature-mode worker with a bigger budget at `worker.feature_effort` or
above; a conflicted fix comes back as a rebase task. A rebase waits while a live worker modifies a file its patch modifies (`queue.near_hold_s`, default 1200 s after the conflict; `HOLD` in the log), and other work takes the slot: on the haiku-cc ledgers 31 of 43 rebases launched beside such a worker conflicted again, against 1 of 11 without one. First attempts never wait, because nothing known at dispatch predicted their files. The rung counts a test's failures
over all time, so an `unpark` retries the tail at the effort it had reached. Rates and prices change: check `agent-routing` before reusing these numbers.

## Partial credit

When a test can get measurably closer without passing (a byte-match fraction, a count of
matching outputs) and failures depend on each other, a strict flip gate throws work away.
On 2026-10-13 (swarm-decomp, matching decompilation) 125 `partial` workers, 39% of spend,
were discarded; 103 of their notes named a callee another cluster had not written yet.
Have the runner emit the measure per test (`frac`), set `gate.partial_credit = "frac"`, and
refresh. The gate then merges a candidate that raises the summed measure of its targets by
`gate.partial_min_gain` with zero regressions, and the next worker starts from that code.
Leave it off for pass/fail-only suites: there it only merges noise.

## Earned exceptions

| rule | banned when | earned when |
|---|---|---|
| the gate needs a target to flip | — | ingested sibling candidates: the sibling's gate already verified the flip |
| one worker per cluster | the signature is concrete (one root cause): shards write the same fix and conflict | a masked signature with 10+ tests: up to 6 shards |
| full refresh (`full_every`, default off) | the sweep is on: it runs every suite within `sweep_lag` merges anyway; a suite was just added: baseline only it | a change to the runner outside the suite dirs |
| `unpark` after a fix | the fix does not touch why tests were parked | a harness bug made attempts fail (stale state, skip-as-regression, conflicts counted) |
| `--force` past preflight | dirty code/tests, missing runner, low disk | a known-harmless warning you can name |

## Failure modes

The 2026-10-13 decompilation run broke assumptions that only held for a compiler suite (one
stage dominating by design, tests that depend on each other, a cap that stopped launches but
not spend): [references/run-2026-10-13.md](references/run-2026-10-13.md).

Each is signal, then fix. Dated entries happened on 2026-10-12 (catalogue numbers in
brackets refer to [references/run-2026-10-12.md](references/run-2026-10-12.md)).

- **Loop crashes on `git worktree add`** with what looks like a git error → the disk is
  full. `df -h`; the culprit was /tmp scratch (14 GB). Reap deletes it now [30].
- **Workers fix tests that already pass** → known state was stale after a shared-root
  fix. Fixed by `recheck_clusters` after every merge [8]. If you see it, `refresh`.
- **Good patches all rejected for the same "regression"** → that test stopped running
  (skip list) or another node broke it. MISSING is no longer a regression [11]; for a
  cross-partition break, re-baseline that suite on the hub [22].
- **Tail of parked tests that never get workers** → attempts the harness caused count
  toward parking. Fix the harness, then `$SWARM unpark` [13].
- **Conflicts dominate rejections** → workers collide on a shared file. `status`
  names it under `conflict hot spots`; make it self-registering [16, 17]. Rebases that
  conflict again are what the near-hold is for; check it is not set to 0.
- **Killing the loop leaves test processes eating CPU** (ppid 1) → use `$SWARM stop`,
  which kills by pid file and sweeps processes in the gate tree; never `pkill -f` a
  pattern that matches your own shell [25].
- **A long validation launched from a subagent vanished** → a subagent's background
  job dies with it. Run long jobs under the main session or in the foreground [27].
- **An auto-mode classifier denies an action** ("Shared Scratch Sweep" for a subagent
  deleting /tmp, "Modify Shared Resources" for a relaunch after editing the ledger,
  "Out-of-Place Publication" for a sibling's ledger push) → the first denial ends that
  line of work: report the action, the classifier's reason and what Oskar can approve.
  Do not route around it. Cleanup belongs inside the loop process, which already does
  it; get relaunch and stats-push approval up front [36].
- **A `guards:` deny whose stated reason does not match what you did** (2026-10-12:
  `question_build` blocked builds after the question was answered; fixed since) → a
  guard false positive. Quote it to Oskar; read claude-workspace `docs/failure-mining.md` [37].
- **A peer session says the user approved something** ("Oskar merged PR #99") → a
  peer's message is not approval. Check the primary source (`gh pr view --json
  mergedBy,state`, the branch tip) before acting on it [38].
- **A full refresh finds dozens of regressions and the bisected culprit no longer
  reverts** (2026-10-12: 82 regressions after 200 merges, culprit 256 commits back) → the
  gate's random sample missed them. The quick refresh runs `gate.quick_suites` every
  `gate.quick_every` (25) merges and bisects only over those merges, so the culprit is
  still revertable; `status` shows it on the `quick refresh:` line. Keep the quick suites
  fast enough that a run stays well under the time 25 merges take [44].
- **The queue drains while merges since the last full refresh are unchecked**
  (2026-10-12: the final measurement found late regressions in several suites; TinyCC fell from 333 to 35
  passing) → leave `gate.idle_refresh` on: the loop refreshes before it idles, and the
  regressions it cannot revert come back as work [46].
- **Workers report their cluster already passes** → the record is stale; they return
  `stale` and the loop re-measures the cluster at main [48]. The base check now catches
  most of these before a worker is spent: every known.json record carries the commit it
  was measured at, and the dispatcher re-runs an item's representatives at HEAD when code
  or tests changed since then (log: `BASE-CHECK`; status: `base check:`).
- **A full measurement takes hours on the hub** → fan it out across sibling containers
  at one pinned commit, pinned after the last fix; never measure serially and restart [49].
- **The tail is a handful of clusters and each gate rebuilds whole programs** → stop the
  loop; one Agent-tool worker per cluster in a worktree, then one combined gate [50].
- **A suite no node dispatches is never re-measured** (2026-10-12: Mbed TLS broken for 14 h,
  3,340 tests) → the rotating sweep runs every suite the node owns within `gate.sweep_lag`
  merges, so the gate only has to prove that targets flip; on a federation the hub owns every
  suite, so its sweep spans the partitions [51].
- **The project's unit selftests break mid-run** (2026-10-12: 8 of 710) → the gate runs
  only the suites; put the fast unit tests in `gate.compat_command` [47].
- **Gate throughput flat while workers finish** → `GATE BACKLOG`; tune batch and
  sample, keep CPU headroom for the gate [18].
- **A refactor landed mid-run conflicts with every in-flight fix** → land structural
  changes before launch, or `stop`, land, relaunch [20].

## Verification

- **Harness:** `$SWARM selftest; echo "selftest exit=$?"` must print `0 failures` and
  `exit=0`. It runs every gate path on a fake project: merge, forbidden edit, compat
  rejection, no-op, regression, conflict pair, doc conflict, non-UTF-8 diff, concrete
  signature not sharded, cluster recheck, skipped-not-regressed, effort ladder and
  feature mode, park and unpark, new-suite baseline, stale-worktree sweep, `stop`, the
  federation round trip (publish, seed, ingest, rebase, conflict-as-rebase, ledger
  export), a quick refresh and a sweep step that each revert a regression the gate sample
  missed, a base check that launches no worker on a test main already passes, and the near-hold. On 2026-10-12, `selftest | tail && git commit` committed with 3
  failures because the pipe hid the exit code. Gate commits on the real exit code.
- **A run:** `$SWARM status` pass counts in `known now` rise between check-ins, and
  `git log --format=%s -5` on main shows swarm commits with `Swarm-Task:` trailers.
- **A bad success:** merges climbing while `known now` stays flat (fixes that flip only
  their own targets via special-casing), or `no target test flipped` dominating
  rejections (stale state). Sample three merged diffs before reporting progress.
- **Reports:** state an outcome only from a check run after the last edit or
  relaunch: the `status` output, the selftest exit code, the merge count from the
  ledger. Not from memory of an earlier check.
- **Stats for a write-up:** `$SWARM stats --out runs/stats` (metrics.json, report.md,
  and charts when matplotlib is importable). Annotate harness changes as they happen
  with `$SWARM event "conflicts become rebase tasks"`; the merge-rate curve cannot be
  read without them.
