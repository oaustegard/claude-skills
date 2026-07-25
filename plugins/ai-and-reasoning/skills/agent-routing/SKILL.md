---
name: agent-routing
description: Decide which model (Haiku/Sonnet/Opus) and effort level each subagent gets, when to cascade cheap-first behind a verifier, and how to run improvement loops safely (evaluator-as-selector, stop on regression). Covers the Managed Agents effort mechanics (per-agent effort levels, cost lever) and how to watch a subagent fan-out stream live so loop and escalation gates have something to observe. Use when spawning subagents via the Agent or Workflow tools, when fanning out more than a handful of agents, or when the user asks which model or effort a task should route to. Routing heuristics grounded in measured calibration data (references/calibration-2026-07-15.md), not vibes; the Managed Agents API specifics are operational, not calibrated.
compatibility: Designed for Claude Code / Claude Code on the Web — assumes an orchestrator with Agent/Workflow subagent tools exposing per-call model and effort options. Not applicable to claude.ai chat use.
metadata:
  author: Oskar Austegard and Claude (Fable 5)
  version: "1.3.0"
---

# Agent Routing — model + effort selection for subagents

Before spawning any subagent, answer one question: **is the task mechanically
checkable, or does it require judgment?** Checkable → Haiku at `effort: 'low'`
behind a verifier. Judgment → up-tier. The routing table refines this split; the
rest of the skill governs cascades and loops.

**Do not up-tier checkable work "to be safe."** Measured Haiku 4.5 failure on
every checkable task family tested is ≈0, at `effort: 'low'`, with
chain-of-thought suppressed (evidence: references/calibration-2026-07-15.md).
The burden of proof is on routing *up*: reflexive up-tiering costs 3–5× for
safety that the data says is imaginary. Spend effort, not tier, and only where
reasoning depth demonstrably falls short.

To turn a judgment-shaped task INTO a Haiku-executable one (explicit procedures,
n-shot examples), use the sibling `down-skilling` skill. This skill decides the
routing; that one engineers the prompt.

## Context handoff — routing picks the tier; the prompt carries the context

Subagents inherit nothing: not the conversation, not loaded skills, not the
existence of artifacts already on disk. Every index, scan output, artifact
path, or tool-invocation recipe the orchestrator relies on must be serialized
into the subagent's prompt (or written to a file the prompt points at).
Otherwise the agent falls back to blind rediscovery — and the tier premium is
spent on crawling, not judgment. A Sonnet with no handoff wastes more than a
Haiku with a good procedure.

This is the context-side twin of down-skilling: that skill engineers the
*procedure* into the prompt; this rule makes the *artifacts and tools* travel
with it. Checklist per spawn: (1) artifact paths + how to query them, (2) tool
commands verbatim (interpreter path included — subagents don't know your
venv), (3) explicit anti-patterns ("no `ls`/glob discovery"), (4) an output
spec. Skills that orchestrate fan-outs should embed this (see
`exploring-codebases` for the worked exploration case).

Evidence: 2026-07-16, four Sonnet Explore agents launched onto a 2,300-file
repo without the handoff opened with `ls` crawls despite a full tree-sitter
symbol index sitting on disk; relaunched with per-agent index slices + the
verbatim tool command + anti-crawl rules, discovery cost dropped to ~zero.

## Routing table

| Task shape | Model | Effort | Verify with |
|---|---|---|---|
| Extraction, classification, format transforms, schema-bound output | `haiku` | `low` | schema / spot-check |
| Closed-form computation, state tracking, multi-hop lookup | `haiku` | `low` | deterministic check |
| Constraint-bound generation (exact counts, required tokens, lipograms) | `haiku` | `low` | mechanical checker |
| Bulk scans/greps, per-file summaries, fan-out reads | `haiku` | `low` | sample audit |
| Code edits with tests available | `haiku` first | `low`–`medium` | run the tests |
| Judging / scoring another model's output | `sonnet`+ | `medium` | — (judge ≠ worker) |
| Ambiguity resolution, novel synthesis, architecture, taste | `sonnet`/`opus` | `high` | human or panel |
| Long-horizon multi-step agentic work, cross-file reasoning | `sonnet`/`opus` | `high`/`xhigh` | milestone checks |

## Effort mechanics (Managed Agents)

Effort is set **on the agent, not per session** — an `effort` inside a
per-session `model` override is silently ignored. Levels are `low`, `medium`,
`high`, `xhigh`, `max` (bare string or `{"type": "high"}`); not every model
accepts every level, and an invalid pair is rejected at agent-create. The create
response echoes the resolved config — if `effort` comes back `None`, the org's
beta header (`managed-agents-2026-04-01`) doesn't carry the feature: the field
was dropped, not rejected, so check the echo before assuming a level took.

Effort is the per-role cost lever — higher levels let Claude spend more tokens
per inference call — so buy depth only for judgment-heavy roles and drop triage
or formatting roles to `low` without touching the expensive role's budget. This
is the same split the table encodes; effort tunes within a tier, tier is the
coarse knob. Calibration null result: effort had no measurable effect on Haiku's
checkable tasks (Exp. 2 — `low` and `high` both 20/20), which is why the rule is
spend effort only where reasoning depth *demonstrably* falls short, never
by default.

## Cascade (default composition)

When a near-free verifier exists, compose instead of choosing a tier up front:

```
result = haiku(task, effort=low)
if verify(result) fails:  result = sonnet(task)      # escalate on evidence
if verify(result) fails:  result = opus(task)         # rare
```

Input-cost ratio is Haiku 1× · Sonnet 3× · Opus 5×. Expected cascade cost ≈
`c_haiku + p_fail × c_sonnet`, so the cascade beats Sonnet-direct while Haiku's
failure rate stays below ~2/3, and beats Opus-direct below ~4/5 (derivation in
the reference). Every checkable task measured has Haiku failure ≈0, so the
cascade is nearly pure savings.

**No verifier ⇒ no cascade.** Route by the table instead, because silent Haiku
errors compound downstream with nothing to catch them.

**Shared-prefix caching cuts the fan-out multiplier (unmeasured, conditional).**
When N subagents share a byte-stable prefix — the *fixed* part of the handoff
(tool commands, procedure, anti-patterns), not the per-agent index slices, which
by design differ — that prefix is reusable by prefix caching *where the
orchestration surface exposes it*, pulling the shared portion's input cost toward
a read-discount rate and strengthening the cheap-first / fan-out bias. Keep
per-agent dynamic content at the tail so it doesn't invalidate the shared lead.
This is prompt-construction economics, not from the calibration battery, and it
assumes the surface caches subagent prefixes — verify that before relying on it
(the effort/pricing numbers above are measured; this is not).

## Loop discipline

Never blind-loop. Re-applying the same prompt to a model's own output is the
identity at best (an LLM call already unrolls its reasoning depth internally) and
regression-then-freeze at worst — in calibration, a re-looped haiku broke its
own middle line on iteration 2 and froze on the broken text for every iteration
after. Loops only pay when an out-of-band evaluator scores each iteration.

1. **Loop only with an out-of-band evaluator** — ground truth, mechanical
   checker, or an up-tier judge scoring every iteration.
2. **Select, don't trust the last:** `final = argmax_r eval(answer_r)`. Never
   ship iteration N just because it's newest.
3. **Stop on first regression.** If `eval(r) < eval(r-1)`, stop — loops froze on
   degraded output rather than recovering, so early-stop risk beats drift risk.
4. **Loop for diversity, not depth.** Vary the prompt/angle per iteration to
   explore; identical re-application converges instantly.
5. **"Improve this" with no headroom is the danger zone.** It pressures the model
   to change something; without a selector, that change ships.

## Judge rules

- Judge model ≠ worker model; judge at least one tier up (Sonnet judging Haiku,
  Opus judging Sonnet). Same-model self-assessment is untested — don't assume it.
- Prefer mechanical checkers over judges wherever a spec can be executed (word
  counts, schemas, tests, regex): free, deterministic, zero judge tokens.
- Judges are for rubric quality, not arithmetic — don't ask Sonnet to verify a
  sum a Python one-liner can check.

## Escalation triggers (route up despite the table)

- The verifier fails twice at the same tier.
- The task requires weighing trade-offs with no checkable ground truth.
- Output will be shipped verbatim to a human without review.
- The subagent must plan its own multi-step tool strategy over many turns.

## Observing the fan-out — you can't govern what you can't watch

Loop discipline (stop-on-regression, select-don't-trust-last) and the escalation
triggers (verifier failed twice) all assume you can see a subagent's work *while
it runs*. By default you can't: the session-level stream previews only the
primary (coordinator) thread, and a subagent's output lands only after its whole
turn buffers — a two-minute researcher shows nothing for two minutes.

Close the gap with one stream per thread. Read the session stream for the
coordinator; on every `session.thread_created` (it carries `session_thread_id`
and `agent_name`), attach a watcher to that child's stream
(`GET /v1/sessions/{id}/threads/{thread_id}/stream`, with `event_deltas`) in a
background thread. Four rules keep it honest:

- **Preview is a scratch buffer; the buffered event is the record.** Deltas are
  best-effort and shed under load, so concatenated deltas are a *prefix* of the
  final text, not necessarily the whole. Reconcile by a single replace when the
  buffered `agent.message` arrives; the SDK's `accumulate_managed_agents_event`
  folds start / delta / record into one snapshot. One accumulator per connection.
- **No replay.** A stream opened after a request started gets no deltas for that
  in-flight request, and reconnects never replay missed deltas — attach on
  `thread_created` or miss the child's first response.
- **Coordination events live on the primary thread** — `session.thread_created`
  (spawn), `agent.thread_message_sent` (handoff), `agent.thread_message_received`
  (child reports back). Child tool calls cross-posted to the primary carry
  `session_thread_id`; skip them, the child's own watcher shows them.
- **Terminate cleanly.** Watchers exit on `session.thread_status_idle`; the main
  loop on `session.status_idle` — print the stop reason when it isn't `end_turn`,
  and break on terminated-status events, so a session stuck on a tool
  confirmation or out of retries ends the run instead of hanging it.

Operational, not calibrated (multi-turn agentic tool use is on the "not
measured" list below). Source: Anthropic Managed Agents notebook
`CMA_watch_subagents_live` (beta `managed-agents-2026-04-01`); full streaming
contract in [events and streaming](https://platform.claude.com/docs/en/managed-agents/events-and-streaming#event-deltas).

## Recalibrate when

- **The task is off the measured battery.** No deterministic task has made Haiku
  fail yet, so the cliff is past what's been probed — test harder instances
  before trusting Haiku on a genuinely novel task family.
- **The work is multi-turn agentic tool use.** That was not calibrated; treat the
  table's up-tier rows there as prior, not measurement.
- **A model rev bumps.** Re-run the battery (generators + scorer described in
  references/calibration-2026-07-15.md) before trusting the table.
