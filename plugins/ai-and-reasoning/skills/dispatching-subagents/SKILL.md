---
name: dispatching-subagents
description: Chooses how to launch subagents from Claude Code (the Agent tool, a Workflow script, or headless claude -p children) and runs a headless fan-out from one background command. Use for "fan this out to 50 agents", "run these tasks in parallel", "launch subagents for each file", "should I spawn agents or write a workflow", "batch this through Haiku", "run claude -p in parallel", "dispatch a task list without the launches eating my context", or before any launch of more than a handful of subagents, where the launching itself is the cost. Covers the parent-turn cost of each mechanism, concurrency ceilings, what context and tools each child gets, effort control, output contracts, a cost ledger, and resume after interruption.
metadata:
  version: 0.2.2
---

# Dispatching subagents

Claude Code has three ways to start a subagent. They differ most in what the
launching costs the parent.

| | Agent tool | Workflow tool | `claude -p` children (`scripts/headless_fanout.py`) |
|---|---|---|---|
| parent cost | one parent turn per launch and one per completion | one tool call per run | one Bash call per run |
| concurrency | 20, and a 21st launch errors (it does not queue) | min(16, vCPUs − 2): **2** on a 4-vCPU CCotw container | RAM-bound, about 210 MB per child: 40 ran clean on 4 vCPU / 15 GB |
| child context | session prefix (~32–55K tokens), plus parent transcript chunks if a context hook is installed | session prefix | what you pass: about 1.2K tokens with `--system-prompt` and no tools, 39K with the default prompt |
| tools | agent type's tools, the session's MCP connectors, hooks | as Agent | built-in tools named in `--tools`, write paths allowlisted; no MCP, hooks or skills |
| effort | session's level, or the `effort:` in a named agent type's frontmatter | `agent(prompt, {effort})` | `--effort` (measured: low gave 0 thinking tokens, high gave 112–197) |
| needs user opt-in | no | **yes**: an explicit request, ultracode, or a skill that calls it | no |
| cost visibility | none per child | none per child | `total_cost_usd` and tokens per child, in a ledger |
| output check | yours | in-script | file plus JSON Schema, or CLI-validated `--json-schema` |

The headless runner is the default for volume. On 2026-10-11 a codex build
dispatched 314 Haiku children through the Agent tool. The children cost
$11.61. The 1,458 Opus parent turns the dispatching took (each re-reading a
context of about 400K tokens) cost roughly $160–170, about 14× the work. Five of
the same tasks through `headless_fanout.py` cost $0.10, $0.02 each against
$0.033 per Agent-tool child, and one parent call.

## Choosing

Answer in order. The first yes picks the mechanism.

1. **Does the child need what only the session has?** That means MCP connectors
   (Muninn, Gmail, GitHub MCP), a context hook's transcript chunks, a worktree,
   or a custom agent type with guard hooks such as `auditor`. If so, use the
   **Agent tool**. Keep the count small, or batch many items into each child,
   because every launch costs a parent turn.
2. **Do you need to read each result before deciding the next launch?** That is
   iterative work where task N+1 depends on N's answer. Use the **Agent tool**.
3. **Did the user opt in to a workflow, and does the procedure have phases a
   script should enforce** (find → verify → fix, with retries and gates)? Use
   **Workflow**, and load `workflow-authoring` first. Accept 2-way concurrency
   on a 4-vCPU container, or move the bulk phase to headless children.
4. **Are there ten or more independent tasks whose inputs fit in a prompt or in
   files, and whose output a script can check?** Use **headless children**. This
   covers judges, graders, extractors, page writers, verifiers and per-file
   reviews.
5. Fewer than ten small independent tasks: use the Agent tool in one message.
   The parent-turn cost is still small at that size.

### Earned exceptions

| rule | banned when | earned when |
|---|---|---|
| Use headless for volume | the child needs an MCP connector or the parent's transcript | the inputs can be written into the prompt or a file first |
| Agent tool for small counts | the parent context is already past ~300K tokens, so each launch turn is expensive | the parent context is small, or the results feed the next launch |
| Judges in headless children | — | always: a child with no hooks cannot see the parent discussing the items it scores |

## Headless fan-out procedure

1. **Write one task per line** to `tasks.jsonl`:
   `{"id", "prompt"}` plus any of `out` (absolute path of a JSON file the child
   writes), `json_schema` (structured output, no file), `model`, `tools`,
   `allow`, `deny`, `system_prompt`, `timeout`. `{out}` in a prompt expands to the out
   path. This is the same `{id, prompt, out}` shape claude-workspace's
   `scripts/fanout.py` dispatches over the Agent tool, so one file runs on
   either engine.
2. **Put everything the child needs into the prompt or into files it can
   Read.** The child has no hooks, no CLAUDE.md, no skills, no MCP and no
   memory of this session. For no-tool tasks (judges, classifiers) inline the
   inputs and pass `"tools": ""`. Put a large prefix shared by every task in
   `system_prompt`, since that is the cacheable part.
3. **Dry-run.** This prints the first three commands:
   ```bash
   S=/mnt/skills/user/dispatching-subagents/scripts/headless_fanout.py
   python3 $S run tasks.jsonl --work RUN --schema schema.json --dry-run
   ```
   Check `--model`, `--tools` and the `Edit(//...)` rule against the out path.
4. **Launch as a background Bash command, never as a waiting loop.** Run the
   job itself in the background and end the turn. The completion notification
   brings you back.
   ```bash
   python3 $S run tasks.jsonl --work RUN --schema schema.json \
       --model haiku --concurrency 16 --max-usd 5 > RUN.log 2>&1; python3 $S status RUN
   ```
   (`Bash run_in_background: true`.) Defaults are `--tools Read,Grep,Glob,Write`,
   1 retry, 900 s per child, and concurrency 16.
5. **Read `status`.** It reports attempts, ok, failing ids with reasons, total
   cost, tokens and permission denials. Rerunning the same command skips done
   tasks and retries the rest.

What the runner enforces per child:
- a fresh `--session-id` and `--no-session-persistence`;
- the parent's session-binding variables removed, because without that a child
  reports the parent's session id;
- `--setting-sources ""` and `--strict-mcp-config`, so no hooks and no MCP;
- `--permission-mode dontAsk` with an allowlist: Read/Grep/Glob when listed,
  `Edit(//<out>)` for the out file, and any `--allow` rules; `deny` rules (task
  field or `--deny`) go to `--disallowedTools` and win over the allowlist, so a
  child can hold Bash with `Bash(curl:*)` refused;
- done means verified: the out file parses and passes the schema, or
  `structured_output` is present. The child's claim of success does not count.

### Permission rule syntax under `dontAsk`

Measured 2026-10-11, Claude Code 2.1.296:
- A write is allowed by `Edit(//abs/path/**)` or `Edit(rel/**)` (relative to
  the child's cwd). `Write(path)` and a bare `Edit` are both **refused**.
- `Bash(grep:*)` style prefixes work. A prefix rule matches the start of the
  command only, so `Bash(curl -s https://api.github.com/*)` still admits
  `-X DELETE` appended after it. Never allow Bash for a child that holds a
  token or that could reach a write API. Fetch live data yourself and put it in
  the prompt instead.
- Denied calls appear in the child's `permission_denials`, and the ledger counts
  them. A child that hits a denial usually reports the step as failed and stops
  (it does not route around).

## Agent tool procedure

- Launch all children of a batch **in one message**, `run_in_background: true`,
  at most 20 in flight. A launch over 20 errors and is lost.
- **Batch items per child.** The per-spawn prefix (32–55K tokens) is paid once per
  invocation, however many items it carries.
- In claude-workspace, `scripts/fanout.py` keeps the ledger and validates outputs.
  Its `next` can report a slot free before the agent stops. Dispatch one
  replacement per completion notification instead (diagnosed 2026-10-11, the
  codex build).
- Subagents that must talk to each other use `SendMessage` / `ListAgents`; the
  measured traps (reply by agentId, never by the envelope's `from`; subagents have
  no `ListAgents`) are in [references/native-messaging.md](references/native-messaging.md).
- Put `[no-context]` in judge and eval prompts where the `delegating-with-context`
  hook is installed, or the judge sees the parent discussing what it scores.

## Workflow procedure

Load `workflow-authoring` before writing the script, and run only with the
user's explicit opt-in. Give `agent()` its `effort` where it matters. For a
bulk phase on a small container, a Workflow step can shell out to
`headless_fanout.py` instead of awaiting 100 `agent()` calls two at a time.

## When NOT to use this skill

| situation | use instead |
|---|---|
| which model or effort a child should get, cascades, escalation | `agent-routing` |
| fan-out from claude.ai chat, where no Agent tool or `claude` binary exists | `orchestrating-chat-agents` |
| per-item classification at large volume, where a cheap non-Claude model is enough | `invoking-gemini` |
| a deterministic multi-step pipeline with no model judgment between steps | `flowing` |
| work that must outlive this session or container | `create_session` (claude-workspace `docs/delegation.md`) |
| hundreds of workers fixing failing tests for hours, each fix merged behind a no-regression gate | `swarming-to-green` (it runs this skill's headless runner per worker) |
| one subagent for one question | the Agent tool directly, with no ledger |

**Abandon a headless run mid-way** when the first wave's ledger shows the same
failure reason on most tasks (a prompt or permission bug, not bad luck), or
when `denials` is non-zero on tasks meant to need no tools. Stop it, fix the
task file, and rerun; done tasks are kept.

## Common failure modes

- **A child's `session_id` equals yours.** The session variables leaked
  (`CLAUDE_CODE_SESSION_ID` and the rest). Run children only through the runner,
  or strip `SESSION_ENV` yourself.
- **The output file is missing and the ledger shows `denials` > 0.** The write rule
  did not match: the `Edit(//...)` path differs from the path in the prompt, or
  someone used `Write(...)`. Dry-run and compare.
- **`modelUsage` lists claude-haiku-5-5 on a Sonnet or Opus run.** This is Claude Code's
  own side call, about 3% of the cost. It is expected. Read the per-model split
  before attributing cost.
- **A judge or extractor reads only part of a large input file.** Inline the input,
  or split files so each fits one Read. Check what the child read before
  trusting the scores (`oaustegard/experiments` METHODS.md).
- **Spend climbs past expectation.** Every child writes its own cache, since nothing
  is shared across `--no-session-persistence` children. Move the common prefix
  into `system_prompt`, and cap the run with `--max-usd`. The runner stops
  launching once the cap is reached.
- **Many children fail with "transient" reasons at once.** The run hit a rate or
  overload limit. Lower `--concurrency`. The runner backs off and retries.

## Verification

```bash
python3 $S status RUN          # exit 0 only when every task's last attempt is ok
python3 /mnt/skills/user/dispatching-subagents/scripts/test_headless_fanout.py   # offline, fake claude binary
```
A bad success is a run where every task passes the schema check but the
outputs are copies of the example in the prompt, or are empty lists. Read three
outputs before using any aggregate.

## Diagnosed failures

- **2026-10-11, codex build.** 314 Agent-tool launches from an Opus parent cost about
  14× the children's own bill in parent turns. The fix is this skill's headless
  runner. On five of the same verifier tasks it cost $0.10 in one call.
- **2026-10-11, probe.** `claude -p` children with no flags inherited the parent's
  session id and wrote transcripts under the parent's id. Fixed by the runner's
  environment strip and `--session-id`.
- **2026-10-11, probe.** `--allowedTools "Write(/abs/out/**)"` was refused under
  `dontAsk` and the child wrote no file. `Edit(//abs/out/**)` works.
