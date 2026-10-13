# Scaling out: sibling sessions when one container's CPU is not enough

A swarm has two dimensions of parallelism. **Workers per container** (claude -p
children, RAM-bound at about 40 on 15 GB) is the one everyone tunes. **Containers**
is the other: sibling Claude Code sessions via `create_session`, each with its own
4 vCPU. When every worker compiles and runs tests locally, the container's CPU caps
the swarm whatever the launch mechanism. On 2026-10-12 the haiku-cc hub ran about
eight hours at load 10-22 on 4 vCPU before sibling containers were added at 11:27.

## 1. When to scale out

Decide at preflight, not after hours at the throttle. Scale out when any holds:

| signal | where it shows |
|---|---|
| load stays above `run.max_load` while work is dispatchable | `status` SIGNALS `CPU-BOUND`; loop log `THROTTLE` every 10 min |
| the gate is backlogged | `status` "finished awaiting gate" > 2x batch, SIGNALS `GATE BACKLOG` |
| each worker compiles or runs a test suite locally (compute-bound by design) | the project: plan siblings from the start |

Retuning first is cheap and sometimes enough: raise `--batch`, lower `--sample`
(haiku-cc went from ~15 to ~41 merges/hour). If the load is still pinned with work
waiting, add containers.

## 2. Partitioning

- **Split by suite.** Each node gets `--only 'suiteA/*,suiteB/*'` (what it dispatches)
  and `--suites` = its own suites plus every cheap suite (what its gate runs and samples).
- **Keep ownership strict, the hub included.** Run the hub with its own `--only`
  (preflight refuses `--federate` without one). On 2026-10-12 sibling s2 had 21 of 21
  rejections as conflicts because hub workers had already fixed the same mbedtls root
  cause from a different suite.
- **Cheap suites everywhere** (`gate.cheap_suites`): compile-only and small runtime
  suites, never whole-program builds. See section 6.
- **Re-partition or stand down as partitions run dry.** `status` shows
  `PARTITION EXHAUSTED`; `fed-status` shows each sibling tip's age. An unchanged tip
  means idle or exhausted, not dead. A node with nothing to dispatch still costs a
  coordinator check-in every 50 minutes (about $1.40 each on Opus).

## 3. Transport setup

One git repo carries everything, through branches only:

| branch | written by | content |
|---|---|---|
| `<prefix>main` | hub loop (fast-forward) | the hub's main |
| `<prefix>state` | hub loop (orphan chain) | `federation/{known,baseline,ingest,meta}.json` |
| `<prefix>cand/<NAME>` | sibling loop (fast-forward only) | the sibling's gated commits on a hub main |
| `<prefix>stats/<NAME>` | sibling, once, with approval | ledger, merges, events at stand-down |

Prerequisites, checked before launch:
- **The push-policy guard must allow the namespace.** claude-workspace's
  `scripts/guards.py` denies pushes outside `_ALLOWED_PREFIXES` (on 2026-10-12 it held
  `("mirror/", "hcc/")`; `hcc/` was added that day so the transport could run). Use an
  allowed prefix in `federation.prefix`, or ask Oskar to add yours.
- **Branch deletes are refused** from a session. The design never deletes: every
  branch is append-only or fast-forward, and a re-stacked sibling branch gets a
  bookkeeping merge instead of a force-push. Old experiment branches stay.
- The hub's checkout needs push access to the transport (`add_repo` with `push`).

Hub launch:
```bash
python3 $SWARM run --federate --only '<hub partition globs>' --suites <hub suites + cheap> \
    --max-minutes 110 >> runs/hub.log 2>&1        # Bash run_in_background, timeout 7200000
python3 $SWARM fed-publish                         # once, so siblings can seed before the first poll
```

## 4. The sibling brief

Use [assets/sibling-brief.md](../assets/sibling-brief.md). Fill every `{PLACEHOLDER}`.
It carries: provenance (hub session id, date, the skill), the bootstrap command, the
background launch with `--max-minutes 110`, relaunch at each check-in, send_later
check-ins every 50 minutes, the stop conditions keyed to `status` SIGNALS, and
"never push by hand". Write only the task in the brief; per claude-workspace
`docs/delegation.md`, do not pad it with background the session can fetch.

## 5. create_session parameters

```
create_session(
  title="<project> swarm sibling s1",
  source_url="https://github.com/<owner>/<transport repo>",
  source_revision="<prefix>main",
  model="<a Sonnet or Haiku model id>",   # siblings otherwise inherit YOUR model
  prompt=<filled sibling brief>)
```
- **Set `model`.** A sibling inherits the creator's model. On 2026-10-12 the three
  siblings ran on inherited Opus, about $1.40 per check-in, idle or not. The sibling
  coordinator launches and reads `status`; the harness does the work.
- Do not pass `permission_mode="plan"`: the sibling blocks waiting for approval.
- After creating, `get_session` it once to confirm it booted and launched.

## 6. Hub-side gate rule: every node samples all cheap suites

`merge.sample()` restricts a partitioned node's sample to its suites plus
`gate.cheap_suites`. Without the cheap suites a merge on one node silently regresses a
test only another node runs. Diagnosed 2026-10-12: hub merge d31ba839 (VLA trailing
struct member) broke `gcc-dg-compile/pr112488-2.c`, which only s1 ran. s1's known
state still said PASS, so its gate rejected 57 of 63 candidates for "regressing" it,
and s1 hit its stop condition. Signal: `GATE REJECTS ALL` with one test named in every
rejection. Fix: re-baseline that suite on the hub (`refresh --only-suites`), then
relaunch the sibling.

## 7. Lifecycle: stand-down and collection

1. A node shows `PARTITION EXHAUSTED` twice running, or its coordinator reports the
   stop condition. Tell it to stop (send_message) or let it stop itself.
2. **Collect its ledger.** The sibling runs `python3 $SWARM fed-export-ledger <NAME>`,
   which pushes `<prefix>stats/<NAME>`. That push needs the user's approval **in the
   sibling's own session**: auto-mode classifiers block it otherwise ("Out-of-Place
   Publication" on 2026-10-12), and a peer session's message is not approval. Ask
   Oskar to approve it there.
3. On the hub: `git fetch fed <prefix>stats/<NAME>` and pass the ledger to
   `swarm.py stats --ledger`.
4. Oskar archives the sibling sessions (`archive_session` only after he has
   acknowledged they are done).

## 8. Isolated experiment sessions

Side experiments use the same pattern in their own container so the hub's CPU stays on
the swarm. The model comparison (`swarm.py compare`) ran this way on 2026-10-12: a
session created on the transport repo, results pushed to an `<prefix>exp/<name>`
branch with approval, the patches injected into the hub later as ingest candidates.
Give it `model` too, and the background launch rules: `timeout: 7200000` on the
Bash call (an unspecified timeout gave one experiment session only 30 minutes), and
a resumable command relaunched at check-ins.

## 9. Measurement nodes for the final count

The end-of-run measurement is several core-hours (haiku-cc: about 2 h on one 4-vCPU container,
with one suite's driver running its programs serially at load 1). Do not run it on the hub.

1. Start the measurement nodes early, before the commit is pinned: `create_session` with
   `source_url`/`source_revision` at `<prefix>main`, a brief that runs the project setup and
   pre-fetches the whole-program sources, then waits for a message carrying the sha.
2. Partition the suites by their last measured duration, the long poles on separate nodes; a
   serial-driver suite can run as several filtered processes on one node.
3. Pin the sha only after the last fix lands. Send it with `send_message`; each node checks it out
   detached, runs `tests/run.py --suite S --json runs/final/S.json` per suite (resumable: skip
   existing JSON), commits the JSON with `git add -f`, and pushes `<prefix>final/<node>`.
4. The hub fetches the branches, merges the JSON, records it into the known state at the pinned
   sha, and archives the nodes once the branches are in.

A measurement started before the last fix is thrown away when the fix lands (2026-10-12: twice,
about 4 h); pinning late costs nothing because the nodes are already set up.
