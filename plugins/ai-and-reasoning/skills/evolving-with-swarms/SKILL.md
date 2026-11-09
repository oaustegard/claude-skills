---
name: evolving-with-swarms
description: Improves a program against an automatic scorer by running rounds of cheap Haiku 5.5 swarms, where each proposer suggests one short idea and one writer per swarm turns the ideas into a new program that is scored and kept in an archive, all metered to a dollar cap through headless claude -p. Use for "evolve this program against my evaluator", "optimize this function's score cheaply", "OpenEvolve-style search on a budget", "AlphaEvolve-style construction search with Haiku", "run a swarm to maximize this score", "search for a better heuristic or construction", or any program whose quality a script can score, when the budget is small. Ships the driver, a gateway with a dollar cap and a usage-window pause, a sandbox hook for model-written code, an example problem and an offline selftest; runs from Claude Code on the web or the desktop.
metadata:
  version: 0.1.0
---

# Evolving with swarms

Each round, `scripts/evolve.py` runs K swarms in parallel. A swarm is N proposer calls,
each reading one parent program and one focus x thinking-style prompt and replying with
an idea of at most 45 words, then one writer call that turns the ideas and the parents
into a complete program. The program is scored by your evaluator as soon as it exists
and joins the archive the next round draws parents from: refine one of the best two,
combine three of the best ten, explore two from anywhere, start fresh from the initial
program. Every model call goes through headless `claude -p`, is priced at list rates
from its `modelUsage`, and counts against a dollar cap.

The design is a text-only version of SwarmEvolve (Jiang and Karniadakis, arXiv
2611.08483), whose agents think inside an open model's activations, which an API model
does not expose.

## When it pays

Measured 2026-11-09 against stock OpenEvolve on Sonnet 5.5, three seeds per arm, three
problems ([references/evidence-2026-11.md](references/evidence-2026-11.md)):

| | swarm (defaults) | Sonnet loop, best effort per problem |
|---|---|---|
| $ to 99% of reference, circle packing | $0.013–0.019 | $0.32–0.44 |
| $ to 99%, hexagon packing | $0.035–0.060 | $0.53–0.58 |
| $ to 99%, Heilbronn triangle | $0.09–0.50 | $0.77–1.02 |
| best at $0.25 | above every paired Sonnet seed on all three | |
| final score at $3 | swarm stops at 60 min, about $1 | the same finals, in 7–42 minutes |

Use the swarm when the budget is small or the goal is "good, cheaply". When the last
0.1% matters, the money is there, and wall-clock time counts, a Sonnet loop at the
problem's best effort level gets to the same place faster.

## When NOT to use this skill

| situation | use instead |
|---|---|
| hundreds of failing tests to drive to green | `swarming-to-green` |
| choosing a model or effort for one subagent or a cascade | `agent-routing` |
| many independent tasks with checkable outputs, not one program to improve | `dispatching-subagents` (headless runner) |
| quality only a person or a judge model can rate | no scorer, no search: write the scorer first, or use a judged loop |
| claude.ai chat, where there is no `claude` binary | `orchestrating-chat-agents` |

Abandon a run mid-way when:
- `status` shows `rejected_above_max` climbing or a best score above anything the
  problem allows: the scorer has a hole and the search is now optimising the hole;
- the best score is flat for ten rounds and `rounds.jsonl` shows every refine swarm
  parenting the same program: the archive has converged, and more rounds buy nothing;
- `last_quota.seven_day` passes about 0.40: the gateway stops at 0.45 anyway.

### Earned exceptions

| rule | banned when | earned when |
|---|---|---|
| writer at effort medium | — | effort low on a problem already known to be easy (circle packing: low reached 0.999 cheaper) |
| N=8 proposers per swarm | the problem is new and N=0 has not been tried | an N=0 control on this problem lost to N=8 (on circle packing the writer alone nearly tied) |
| no sandbox prefix | the evaluator imports model-written code on a machine with secrets or network | a throwaway container with no credentials, and the user agreed |

## Setup

1. **Make a problem directory.** Copy `assets/example/` and replace its four files:
   - `problem.md`: the task in plain words, including the reference value if known;
   - `initial_program.py`: a valid, weak starting program;
   - `evaluator.py`: `evaluate(program_path) -> dict` of numbers and strings, with the
     score under `score_key` (default `combined_score`) and an `error` key on failure;
   - `config.toml`: entry function name, the interface text the models see, budgets.
2. **Score the initial program by hand** and read the dict:
   ```bash
   python3 -c "import importlib.util as u; s=u.spec_from_file_location('e','evaluator.py'); e=u.module_from_spec(s); s.loader.exec_module(e); print(e.evaluate('initial_program.py'))"
   ```
   A score of 0 with no `error`, or a missing `score_key`, means the contract is wrong;
   fix it before spending anything.
3. **Set `score_max`** from a bound you can prove (a known optimum, an area or volume
   bound), slightly above it. Scores above it count as 0 and are flagged. Leave it unset
   only when no bound exists, and then re-check the best program independently.
4. **Choose the sandbox.** The evaluator imports and runs model-written code.
   - Claude Code on the web with the claude-workspace hub: the hub jail.
     ```toml
     [sandbox]
     prefix = ["sh", "/home/user/claude-workspace/scripts/jail.sh", "-C", "{run_dir}", "--"]
     chown_uid = 65534
     ```
     and put `--run-dir` under `/tmp/jail/<name>/` (mkdir and `chmod 755` it first).
     Launch through a script file: the hub's jail_route guard refuses a Bash command
     that names `/tmp/jail/` next to `python3`.
   - Desktop with Docker: `prefix = ["docker", "run", "--rm", "--network=none", "-v", "{run_dir}:{run_dir}", "python:3.12-slim"]`
     (add numpy or what the evaluator needs to the image).
   - No sandbox only under the earned exception above.
5. **Check the CLI**: `which claude` (desktop: the app's bundled CLI may not be on PATH;
   set `EVOLVE_CLAUDE_BIN`). Then run the offline selftest:
   ```bash
   python3 scripts/test_evolve.py      # three "ok" lines, about 3 s, no model calls
   ```

## Run

```bash
S=/mnt/skills/user/evolving-with-swarms/scripts
python3 $S/evolve.py run problem/config.toml --run-dir RUN --seed 1 --cap 1.0 --wall 60 > RUN.log 2>&1
```

Launch it with `Bash run_in_background: true` and end the turn. The completion line is
`done -> RUN/summary.json`; relaunching the same command resumes from `RUN/archive.json`
and keeps the spent dollars. Check in with `python3 $S/evolve.py status RUN`. In Claude
Code on the web a background task is stopped after two hours: keep `--wall` under 110
minutes per launch, or relaunch on the completion notice.

| knob (`[swarm]`, `[budget]`) | default | measured |
|---|---|---|
| `K`, `N` | 4, 8 | K=2,N=16 and K=8,N=4 did no better on circle packing; N=0 nearly tied |
| `proposer_effort` | low | the floor; Haiku still thinks on about a third of calls |
| `writer_effort` | medium | low helped on circle packing, hurt on hexagon and Heilbronn |
| `writer_model` | haiku | sonnet (one seed): 99% at $0.11 on circle packing, between swarm and loop |
| `cap_usd`, `wall_minutes` | 1.0, 60 | the swarm spent $0.9–1.4 an hour on 4 vCPUs |

On a new problem, run the default and an N=0 control at the same cap before a long run.

## Reading results

`RUN/summary.json`: `programs`, `best_score`, `spent`, `usd_to` (dollars when a program
first scored 0.99, 0.999, 0.9999), `calls_by_role`, `rejected_above_max`, `duplicates`,
`no_code`, `last_quota`. `RUN/best_program.py` is the top program. `events.jsonl` has one
line per evaluation with the spend at that moment, which is the curve to plot;
`rounds.jsonl` has each swarm's parents and ideas.

## Common failure modes

- **`best_score` far above the reference, or `rejected_above_max` > 0** → the scorer
  accepts something it should not. Read the offending program in `RUN/r*/s*/prog.py`,
  fix the evaluator or tighten `score_max`, and start a new run: the archive is poisoned.
- **Every refine swarm in `rounds.jsonl` parents the same broken program** → a scorer
  hole made it the leader; same remedy. Diagnosed 2026-11-09: a hexagon run spent its
  last 40 minutes refining a program the scorer had wrongly rated 3.9e9.
- **`no_code` climbing** → the writer's reply has no fenced block defining `entry`. Check
  that `entry` in the config matches the interface text and the initial program.
- **`duplicates` close to the number of writer calls** → the writer returns its parent
  unchanged; usually a writer that cannot see why the score is low. Add the useful
  metrics to `show_metrics`, or raise `writer_effort`.
- **Evaluation errors with `rc=125` or `rc=2`** → the jail could not isolate (125) or
  `nobody` cannot enter the run directory (2). Put the run dir under `/tmp/jail/<name>/`
  and set `chown_uid = 65534`.
- **Spend per program well above a cent** → the gateway's ledger shows the cost by role;
  proposers were about 60% of the spend in the live example. Each `claude -p` call
  carries about 1,370 tokens of the CLI's own, so many tiny calls cost more than their
  prompts suggest. Fewer proposers (or N=0) is the lever.
- **`pauses.jsonl` appears and the run slows** → the account's five-hour window passed
  90% (non-Haiku calls) or 97% (Haiku). The gateway waits for the reset and leaves the
  wait out of the run clock; nothing to do unless it is urgent.
- **A run stops with `stopped_by` starting `quota:`** → seven-day utilisation reached
  0.45. Stop launching runs this week, or raise `week_stop` in `gateway.py` deliberately.

## Verification

```bash
python3 $S/test_evolve.py                         # offline: run, resume, status, score bound, sandbox prefix
python3 $S/evolve.py status RUN                   # programs > 1, spent <= cap + one round, best_score <= score_max
```

Re-score `RUN/best_program.py` with the evaluator yourself (in the sandbox) and compare it
with `best_score`. Programs that optimise with randomness or a time budget re-score lower;
two of three hexagon programs did on 2026-11-09. A **bad success** is a high score the
evaluator should not have given: check the best program against an independent
condition (a stricter geometric test, a known bound) before reporting a record.

## Diagnosed failures

- **2026-11-09, hexagon packing.** OpenEvolve's stock hexagon evaluator scored an outer
  side of 1e-9 at 3.9e9: an absolute tolerance on an unnormalised cross product. Signal:
  a score nine orders above the reference. Fixed by an area bound; `score_max` exists for this.
- **2026-11-09, cost accounting.** `claude -p` wrote prompt cache at the 1-hour TTL (2x
  input) until `FORCE_PROMPT_CACHING_5M=1`; the gateway sets it. Signal:
  `cacheCreationEphemeral1hInputTokens` non-zero in the ledger.
- **2026-11-09, effort.** `MAX_THINKING_TOKENS=0` and `alwaysThinkingEnabled: false` did
  not stop Haiku 5.5 from thinking, and an output cap below its need failed the call while
  billing it. Effort low is the floor; do not set `max_tokens` tight.
- **2026-11-09, usage window.** Ten parallel runs used most of a five-hour window in about
  70 minutes and the old gateway aborted runs at 90%. It now pauses and resumes instead.
