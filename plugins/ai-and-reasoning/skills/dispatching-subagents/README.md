# dispatching-subagents

Chooses how to launch subagents from Claude Code, and runs the bulk case from one command.

Claude Code has three ways to start a subagent: the Agent tool, a Workflow script, and a headless
`claude -p` child process. They differ most in what the *launching* costs the session that does it.
Every Agent-tool launch, and every completion notice, is a turn in which the parent re-reads its
whole context. On 2026-10-11 a 314-agent build spent about $160–170 of Opus parent turns to
dispatch $11.61 of Haiku work. The same tasks through this skill's runner cost one parent call.

## Which of these skills do I want?

Several skills in this repo sit close together. Their names alone mislead: given only the names,
Haiku, Sonnet and Opus picked the right one for 55–85% of 58 test requests, and the commonest
mistake was sending a "run these in parallel" request to `orchestrating-agents`, since renamed
`orchestrating-chat-agents` for that reason. Given the
descriptions, all three picked correctly 173 times out of 174
([`experiments/subagent-skill-choice`](https://github.com/oaustegard/experiments/tree/main/subagent-skill-choice)).
So Claude routes well; this table is for people.

| you want to… | skill |
|---|---|
| run 10+ independent tasks in parallel, decide Agent tool vs Workflow vs `claude -p`, or stop launches eating your context | **dispatching-subagents** |
| pick the model or effort level for a subagent, or decide whether to retry or escalate | `agent-routing` |
| write an Agent or `create_session` prompt that carries the right part of this conversation | `delegating-with-context` |
| fan out over the Anthropic API from claude.ai chat, where there is no Agent tool | `orchestrating-chat-agents` |
| write the script for a workflow you have already opted into | `workflow-authoring` (built in) |
| run a fixed sequence of steps with retries, gates and resume, with no model judgment between steps | `flowing` |
| classify or extract per item at volume, with a cheap non-Claude model | `invoking-gemini` |
| route, triage or rate text with a calibrated probability | `deciding-with-confidence` |

They compose. A large fan-out typically uses three: `dispatching-subagents` to pick the mechanism
and run it, `agent-routing` to pick the model, and `delegating-with-context` when the children need
what this session knows.

## The three mechanisms

| | Agent tool | Workflow | headless `claude -p` |
|---|---|---|---|
| parent cost | a turn per launch and per completion | one call per run | one Bash call per run |
| concurrency | 20; a 21st launch errors | 2 on a 4-vCPU container | RAM-bound, ~210 MB per child; 40 ran clean |
| child sees | the session's tools, MCP connectors, hooks | as Agent | only what you pass |
| effort | session's level | per `agent()` | `--effort` |
| needs your opt-in | no | yes | no |
| cost per child | not reported | not reported | in a ledger |

Use the Agent tool when a child needs an MCP connector or this session's context, or when each result
decides the next launch. Use Workflow when you have opted in and want a script to enforce phases.
Use headless children for everything else at volume: graders, judges, extractors, per-file reviews.

## Quick start

```bash
S=/mnt/skills/user/dispatching-subagents/scripts/headless_fanout.py
# tasks.jsonl: one {"id", "prompt", "out"} per line; "out" is the JSON file the child writes
python3 $S run tasks.jsonl --work RUN --schema schema.json --dry-run    # check the commands
python3 $S run tasks.jsonl --work RUN --schema schema.json --model haiku --max-usd 5
python3 $S status RUN
```

Run the second command in the background and end the turn; the completion notice brings you back.
A rerun skips finished tasks. Tasks with no tools can return structured output instead of a file:
`{"id", "prompt", "tools": "", "json_schema": {...}}`.

Each child gets a fresh session id, no hooks, no MCP servers, no secret-named environment variables,
and `--permission-mode dontAsk` with an allowlist. A task counts as done only when its output parses
and matches the schema. Write permission is spelled `Edit(//absolute/path)`; `Write(path)` is refused.

## Measured

- 40 concurrent Haiku children: 40/40 ok, 25 s wall clock, 8.7 GB peak RSS.
- A lean child (custom system prompt, no tools) carries ~1.2K tokens of overhead; the default prompt
  carries 39K.
- `--effort low` gave 0 thinking tokens on a reasoning prompt, `--effort high` 112–197.
- In one session the runner drove 747 children (A/B answerers and judges, contradiction checks with
  web search and repo snapshots) from about a dozen parent calls.

## Files

- `SKILL.md`: the decision rule, procedures, failure modes and verification, for Claude.
- `scripts/headless_fanout.py`: the runner.
- `scripts/test_headless_fanout.py`: offline tests against a fake `claude` binary.
- `references/native-messaging.md`: `SendMessage` and `ListAgents` between native subagents, moved here from `orchestrating-agents`.
