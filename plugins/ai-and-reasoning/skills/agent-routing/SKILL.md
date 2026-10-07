---
name: agent-routing
description: Decide which model, effort level, and cascade shape each subagent gets, and how to keep improvement loops safe (evaluator-as-selector, stop on regression). Routes on measured cost-per-completed-task rather than per-token price, because a tier's token count varies more by task shape than price varies across tiers. Covers per-model effort semantics, the concision lever, cascade preconditions, context handoff, and watching a subagent fan-out live. Use when spawning subagents via the Agent or Workflow tools, when choosing how to escalate a failed attempt, when fanning out more than a handful of agents, or when asked which model or effort a task should get. Grounded in measured calibration (references/calibration-2026-07-15.md), a 2026-08 coding-cost study, a 2026-09 agentic-repair battery that measured the cascade rungs directly, and a 2026-10 Haiku 5.5 ladder on the same battery that priced subagents per spawn; Managed Agents API specifics are operational, not calibrated.
compatibility: Designed for Claude Code / Claude Code on the Web — assumes an orchestrator with Agent/Workflow subagent tools. Only the Workflow tool sets a subagent's effort; the Agent tool sets its model. Not applicable to claude.ai chat use.
metadata:
  author: Oskar Austegard and Claude
  version: "2.4.0"
---

# Agent Routing — model, effort, and cascade selection

## Current prices, and what changed in 2026-10

| model | $/MTok in | out | cache read | one fresh Agent-tool spawn (measured) |
|---|---|---|---|---|
| Haiku 5.5 | $0.10 | $0.50 | $0.01 | **$0.005–0.011** |
| Sonnet 5.5 | $2 | $10 | $0.20 | **$0.17** |
| Opus 5.5 | $4 | $20 | $0.20 | ~$0.34 (2× Sonnet, not measured) |
| Fable 5.1 | $10 | $50 | $0.25 | — |

Haiku 5.5 is **20× under Sonnet 5.5 on every token class** (Haiku 4.5 was 2–5×), and its
prices hold for prompts up to 100K tokens ($0.50/$2.50 beyond). On the 14-repo
seeded-bug battery it solved 11/14 at rung 1, which is the pass set Sonnet 5.5 at `low` gets. With
the same-model informed retry it solved **14/14 for $0.12 in total, less than one Sonnet 5.5 spawn**
(`oaustegard/experiments` → `temporal-routing-headroom`, 2026-10-07). Where the Haiku
4.5 figures below say Haiku loses on cost, rerun the arithmetic at 5.5 prices before
trusting them.

**In Claude Code, price a subagent per spawn first.** A fresh Agent-tool subagent
writes a ~55K-token prefix (system prompt, tools, skills list) to the 5-minute cache on its
first request. On short repair tasks that prefix outweighed everything the subagent
produced: a Sonnet 5.5 spawn cost $0.17 input-side, 14× the $0.0121 output-only figure
this skill used to quote per completed task. Same-model spawns in sequence share the
cached prefix (reads cost 0.1×), so serialise spawns of one model when they can wait,
and count spawns before counting output tokens. Every table further down prices output
tokens only. That is still right for comparing tiers on long outputs, but it understates
what a spawn costs.

## The rule that decides everything

**Cost is output tokens × output price, plus the spawn's prefix.** Prices span ~5× across tiers. Token
counts span up to **7× within a single tier** depending on task shape. The shape
therefore decides more than the tier does, and *routing on the per-token discount
gets the answer backwards*.

Measured 2026-08-17, 14 spec-dense Python modules graded by hidden tests, all
tiers at equal quality where noted:

| arm | tok/task | pass | $/task | vs opus |
|---|---|---|---|---|
| haiku-solo | 20,051 | 14/14 | $0.1007 | **1.30×** |
| haiku + concision | 13,342 | 12/14 | $0.0672 | 1.01× |
| opus-solo | 3,001 | 14/14 | $0.0774 | 1.00× |
| sonnet-base | 4,687 | 14/14 | $0.0478 | 0.62× |
| sonnet + concision | 2,951 | 13/14 | $0.0305 | 0.42× |
| **sonnet cascade** (below) | — | **14/14** | **$0.0315** | **0.41×** |

Haiku 4.5 was 5× cheaper per token and cost **30% more per solved task** than Opus,
because it emitted 6.7× the tokens. Prices then: Haiku 4.5 $1/$5, Sonnet 5 $2/$10,
Opus 5 $5/$25 per MTok. At Haiku 5.5's $0.50 output price the same 20,051 tokens would
cost $0.010 a task, a fifth of Sonnet's $0.048. Whether Haiku 5.5 is as verbose as 4.5
on generation is unmeasured. It would have to emit about 95K tokens a task to lose on output cost.

## Two questions before spawning

1. **Is the output short or long?** Short = a schema instance, a label, an answer,
   a small patch. Long = a module, a document, a plan, a review.
2. **Is it mechanically checkable, or does it need judgment?**

| | short output | long output |
|---|---|---|
| **checkable** | `haiku` + verifier | `haiku` + verifier, informed retry on `haiku`, then `sonnet` @ `high` |
| **judgment** | `sonnet` @ `medium` | `sonnet` @ `high`, or `opus` when the work must be discovered |

On Haiku 4.5, output length was the discriminator, because it is what the verbosity multiplier
multiplies: Haiku 4.5's premium was invisible on a 200-token JSON object and ruinous on a
700-token module that cost it 13,000 tokens of thinking. At 5.5 prices verbosity no
longer decides it, so the checkable column now starts on Haiku at any output length. The
long-output cell is projected from price and from the repair battery, and has not been
measured on generation.

The judgment row splits on whether the prompt **names its deliverable** or leaves the
work to be found. Sonnet 5.5 finishes a named deliverable well. Given an
audit-and-update goal, it listed findings, raised doubts and stopped to ask, and Oskar
moved that session to Opus 5.5 mid-task (2026-10-07; one session, an observation, not a
measurement).

## Routing table

| Task shape | Model | Effort | Verify with |
|---|---|---|---|
| Extraction, classification, format transforms, schema-bound output | `haiku` | n/a | schema / spot-check |
| Closed-form computation, state tracking, multi-hop lookup | `haiku` | n/a | deterministic check |
| Constraint-bound generation (exact counts, required tokens, lipograms) | `haiku` | n/a | mechanical checker |
| Bulk scans/greps, per-file summaries, fan-out reads | `haiku` | n/a | sample audit |
| **Code edits with tests available** | **`haiku` → `haiku` informed retry** | session | run the tests (the orchestrator's, not the worker's) |
| Code generation from a spec; any long structured artifact | `haiku` → `sonnet` @ `high` on a second failure | `medium` | run the tests (Haiku 5.5 unmeasured here) |
| Judging / scoring another model's output | `sonnet`+ | `medium` | — (judge ≠ worker) |
| Ambiguity resolution, novel synthesis, architecture, taste | `sonnet`/`opus` | `high` | human or panel |
| Long-horizon multi-step agentic work, cross-file reasoning | `sonnet`/`opus` | `high`/`xhigh` | milestone checks |

Haiku holds the top four rows on merit: 240/240 measured across nested modular
arithmetic, 30-hop chains, 25-operation state tracking, trap-laden word math, and
5-constraint generation, some with CoT suppressed
(references/calibration-2026-07-15.md). Those were Haiku 4.5 runs, which requested
`effort: low` and ignored it, so the column says n/a. Haiku 5.5 does take effort (see
below); until it is measured, leave it at its default. **Do not up-tier short checkable work "to be
safe"**; there is no measured benefit and it costs 3–5×. The burden of proof is on
routing up.

Haiku 4.5 lost the generation rows on cost alone, not capability: it scored 14/14 on
the same suite Opus swept. At 5.5 prices that cost argument is gone (see the top of this
file), so the generation rows now start on Haiku behind a test verifier, pending a
generation-suite run on 5.5.

## Effort is model-specific — verify per model before reusing a level

Measured 2026-08-17 via per-message `output_tokens_details.thinking_tokens`,
thinking as a share of output on identical prompts:

| model | `low` | `medium` |
|---|---|---|
| Sonnet 5 | **2.9%** | 47.7% (61.7% without concision) |
| Haiku 4.5 | **88–91%** | 88–91% |

`low` was a near kill-switch on Sonnet 5: it dropped 14/14 → 10/14. **Sonnet 5.5 is
different.** On the 14-repo seeded-bug battery (2026-09-29, two replicates,
`temporal-routing-headroom`):

| arm | solved (r1, r2) | output tokens, 14 tasks | $/completed |
|---|---|---|---|
| Sonnet 5 @ `low` (2026-09-03) | 9/14 | 16,779 | — |
| Sonnet 5.5 @ `low` | 10, 11 | 11,466 | $0.0104 |
| Sonnet 5.5 @ `medium` | 11, 12 | 10,853 | $0.0090 |
| Sonnet 5.5 @ `high` | 12, 12 | 14,488 | $0.0121 |
| Opus 5.5 @ `high` | 11, 13 | 18,464 | $0.0284 |
| Opus 5 @ `high` (2026-09-03) | 10/14 | 55,674 | $0.1392 |

- `low` and `medium` cost the same on Sonnet 5.5 for this work, and `low` missed only
  trap tasks. Claude Code's `<reasoning_effort>` tag agrees: 4 at `low`, 5 at `medium`.
- `high` bought the paired traps: `lru_ttl` and `wrap_text` went from 0 of 2 at `low` to
  2 of 2 and 1 of 2.
- Sonnet 5.5 @ `high` matched Opus 5.5 @ `high` at 24 of 28 each, for **0.43×** the cost
  per completed task. Seeded repair does not separate tiers, so this says the two are
  close on this family and nothing about harder work.
- The token counts are one replicate (budget deltas from r2); thinking share could not
  be measured, because Claude Code omits thinking text.

**Effort does not reach Haiku 4.5.** The Messages API rejects `effort` on it; Claude
Code's Workflow `agent()` accepts the option and drops it (0 of 12 Haiku probes carried an
effort tag or a transcript effort field). The identical 88–91% thinking share at `low` and
`medium` above is that fact seen from the token side, and the ~26% token drop once
attributed to `low` sits inside the 23% run-to-run gap measured below. Tune Haiku with the
prompt; the routing table lists its effort as n/a.

**Haiku 5.5 takes effort.** The API accepts `low` through `max` on it, defaults to
`medium`, and thinks adaptively by default; `budget_tokens` and non-default `temperature`
are 400s. Whether Claude Code's Workflow `agent({effort})` reaches a Haiku 5.5 subagent,
and what `low` does to its pass rate, are both unmeasured. The 2026-10-07 ladder ran it at
the session's level through the Agent tool.

- **Tune Sonnet with the prompt as well as the knob.** On Sonnet 5, `medium` was the
  working floor and `low` overshot into thinking-off; on Sonnet 5.5 `low` is a usable
  rung 1 and `high` is the rung that caught the traps.
- Buy depth only for judgment-heavy roles; drop triage and formatting roles to `low`
  without touching the expensive role's budget.

### Setting effort — which channel reaches which agent

Measured in Claude Code on 2026-09-28 (muninn.austegard.com/blog/effort-levels-in-claude-code-subagents.html):

| channel | reaches | notes |
|---|---|---|
| Workflow `agent(prompt, {effort})` | one subagent | 24/24 Sonnet and Opus probes ran at the requested level while the session sat elsewhere. **The only way a parent sets a subagent's effort.** |
| Agent tool, SendMessage | nothing | No `effort` parameter. The subagent runs at the session's level when it starts or resumes. |
| Session setting (`/effort`) | main loop, and every subagent at its next turn | A resumed subagent picks up the new level. The model cannot change this itself; it recommends a level and the human sets it. |
| Managed Agents | agent config | Set on the agent, not per session: an `effort` inside a per-session `model` override is silently ignored. If the create response echoes `effort: None`, the org's beta header (`managed-agents-2026-04-01`) doesn't carry the feature and the field was dropped. |

A Workflow run needs the user's opt-in (ultracode, an explicit request, or a user-invoked
skill that names it). Without one, a subagent spawned through the Agent tool gets the
session's level, and the routing table's effort column is advisory.

## The concision lever, and its limit

Adding one instruction — *this is routine work; do not deliberate at length, do not
enumerate test cases or weigh alternative designs; write it directly* — cut output
**37% on Sonnet** and **27% on Haiku**, at no quality cost. It composes with effort.
Use it on every long-output generation spawn.

**It does not reach work whose output is small.** On agentic bug repair — a patch plus a
paragraph — the same instruction cut Sonnet output **2.9%**, at no quality change either
way. The lever acts on deliberation the model would have written down, so a task that
emits little has little to cut. Measure before carrying it to a new task family; "every
long-output generation spawn" is the scope, and repair work is not in it.

**Then stop.** Thinking below a model's natural level is load-bearing, and cutting
into it buys tokens with correctness:

- An engineered suppression prompt (positive framing, bounded budget, n-shot
  exemplar) cut Haiku 35% and **halved** its pass rate, 8/9 → 4/9. Within that arm,
  passing runs thought **1.9×** more than failing runs.
- Sonnet at `low` (2.9% thinking) fell 14/14 → 10/14.
- Priced per *passing* result the suppressed arms were **more** expensive: 22,143
  tokens vs 17,126 for the un-engineered prompt.

A targeted checklist ("enumerate the spec's rejection rules first") helps only when
it names the actual failure mode: it took one validation-heavy task from 15,220 to
9,634 tokens at equal quality, and took a semantics-heavy task from 3/3 to **0/3**.
Misnaming the failure mode is worse than not intervening.

## Cascade

**Precondition, checked first: is the cheap tier actually cheaper per task?** The
first rung is never free, so a cascade pays only when the cheap tier's *measured*
cost per completed task is below the destination's. Verbosity can erase a price
discount outright — Haiku 4.5 at $0.067/task against Sonnet's $0.031 made
`haiku → sonnet` worse than Sonnet alone **regardless of `p_fail`**: the attempt
cost 2× the destination's entire job. Compute this before designing the ladder.

Haiku 5.5 passes this precondition. A Haiku 5.5 rung-1 spawn cost $0.0077 against $0.17 for a Sonnet 5.5
spawn, and it solved the same 11 of 14 repairs Sonnet 5.5 solves at `low`. A Haiku first
rung now pays even when it fails often. A failed attempt is about 5% of the Sonnet job it
precedes.

**Second precondition: no verifier ⇒ no cascade.** Route by the table instead;
silent cheap-tier errors compound with nothing to catch them.

**The verifier's holder makes the escalation call. Never the worker.** A subagent asked
whether it finished says yes: across 58 graded runs carrying an explicit "did you finish"
field, 58 said yes and 44 had passed the held-out suite. Every one of the 14 failures
self-reported success. The workers were not lying — they had passed the tests they could
see, and those tests stay satisfiable while the task is unfinished. "Try it, and ask for
help if you fail" therefore fails on exactly the tasks that need escalation. Put the
decision wherever the stronger check lives; in a fan-out that is the orchestrator.

The shape that worked (measured, 14/14 at 0.41× Opus):

```
result = sonnet(task, effort=low, concise)          # rung 1: 10/14, $0.0155
if verify(result) fails:
    result = sonnet(task, effort=medium, concise,   # rung 2: fixed 12/12
                    prior=result, failure=test_output)
```

**Haiku 5.5 ladder (measured 2026-10-07, 14 seeded-bug repos, one replicate):**

```
result = haiku(task)                                   # rung 1: 11/14, $0.108 for 14 spawns
if verify(result) fails:                               # the orchestrator's hidden suite
    result = haiku(task, prior=diff, failure=output)   # rung 2: rescued 3/3, $0.015
```

14/14 for $0.123. Sonnet 5.5 at rung 2 rescued the same 3/3 for $0.511, 35× the
per-spawn cost, and bought nothing more. All three rung-1 misses named the second defect
in their own summaries and left it as "outside the reported bug". The informed retry
supplies the evidence that the shortcut was wrong; the tier adds nothing to that.

**Rung 2 is the same model one effort step up. A tier jump is the exception you justify.**
Measured twice. On a second battery (14 seeded-bug repos, 2026-09-03) rung 2 ran from an
identical failed attempt at both settings: `sonnet` @ `medium` and `opus` @ `high` rescued
the same 4 of 5 tasks and both missed the same fifth, at 11,691 against 32,504 output
tokens. Composed over the same rung 1, the same-model cascade cost **0.31×** always-`opus`
and the tier jump **0.76×**. The tier jump costs 2.5× and buys nothing.

Those rungs are Sonnet 5. On Sonnet 5.5, `low` and `medium` solved the same tasks at the
same cost, so the step that changes anything is `low` → `high`: `high` is where the
paired traps started getting caught (see the effort table above). The cascade itself has
not been run on 5.5.

**A cascade can beat the frontier solo arm on correctness, not only on cost.** In that run
the `sonnet`→`sonnet` cascade solved 13/14 where always-`opus` solved 10/14. `opus`
starting from the issue text fell into the same stop-early trap as `sonnet` on three
tasks; `opus` starting from the failed patch and the failing assertions fixed all three.

**How to run rung 2 in Claude Code.** For a subagent, launch a fresh Workflow `agent()`
one effort step up and pass it the diff and the test output; Agent and SendMessage cannot
change a subagent's effort. For the main loop, recommend the next level and let the human
set `/effort`; the session keeps its cache and carries on.

**Caching pushes the same way.** Caches are model-scoped, so a tier jump discards rung 1's
prefix. An effort change does not: in Claude Code on 2026-09-28, five subagent resumes
across a level change (Low→Medium, High→Extra, Extra→Max) all read their full prefix from
cache, and the parent read 97,839 tokens from cache on its first request after a change.
On the API the per-message effort message (`{"role": "system", "content": [],
"output_config": {"effort": …}}`, beta `mid-conversation-output-config-2026-07-01`) keeps
the cache on Fable 5.1, Mythos 5.1, Opus 5, Opus 5.5 and Sonnet 5.5 with thinking on; a
change to the top-level `effort` still invalidates the messages cache.

**The TTL is what misses.** Every miss in that experiment followed a gap longer than five
minutes. Subagents write only to the 5-minute tier and the parent to the 1-hour tier, so a
subagent resumed after five idle minutes rebuilds its whole prefix (about 54k tokens for a
bare general-purpose agent). Resume a subagent for a quick retry; after a longer gap, start
a fresh one, since same-model agents share a cached prefix (32 of 36 fresh probes read from
cache on their first request).

Every figure in this skill prices output tokens only; input and cache effects sit outside
its cost model.

**Carry the prior attempt and the raw failure output into the retry.** Informed retry
fixed **12/12**; a blind re-attempt fixed **9/12** and failed one task *identically
across all three replicates* — a systematic blind spot re-rolling never escapes. The
extra input averaged 866 tokens, **5.9%** of the retry's cost. Input is 1/5 the price
of output, so context is nearly free relative to thinking.

**The artifacts, not the prior model's account of itself.** Adding rung 1's stated
diagnosis on top of the patch and the assertions did nothing: 13/15 against 12/15 over
three replicates, 1% fewer output tokens, and the whole difference was one replicate of
one unstable task. It does not help and it does not anchor — SWE-Router (arXiv
2607.00053) restarts its strong model from the task description to avoid an anchoring
effect that is not there. Pass the diff and the test output; skip the rationale.

**Don't pay a frontier model to write guidance.** An Opus diagnosis added zero over
raw test output in two independent tests, at ~$0.15/task. The failing test already
says what the orchestrator would say.

**Verify content, not envelope.** Strip fences, preambles, and trailing commentary
before checking; hard-fail only on semantic content and log envelope deviations as
soft. Two Haiku runs returned 7/7 and 6/6 correct fields while both wrapping output
in a markdown fence the prompt forbade — a verifier keying on `raw.startswith('{')`
would have escalated both for zero content error. Spurious escalation is a cascade
failure mode, not a safety margin.

**Judgment tasks fail in a shape checkers miss.** Asked to rebut a stakeholder's
"spend is down 66%" off a partial-month extract, Haiku killed the bad conclusion but
normalized per calendar day across a 40%-weekend window and missed a model-mix
confound — while passing every mechanical check available (word count, prose form,
internal arithmetic consistency). The cheap tier fails as *right headline, missed
confound*. This is why judgment rows route up rather than cascade.

## Context handoff — routing picks the tier; the prompt carries the context

Subagents inherit nothing: not the conversation, not loaded skills, not the existence
of artifacts already on disk. Every index, scan output, artifact path, or tool recipe
must be serialized into the prompt (or a file the prompt points at). Otherwise the
agent falls back to blind rediscovery and the tier premium is spent on crawling. **A
Sonnet with no handoff wastes more than a Haiku with a good procedure.**

Per spawn: (1) artifact paths + how to query them, (2) tool commands verbatim,
interpreter path included — subagents don't know your venv, (3) explicit
anti-patterns ("no `ls`/glob discovery"), (4) an output spec.

Evidence: 2026-07-16, four Sonnet Explore agents launched onto a 2,300-file repo
without the handoff opened with `ls` crawls despite a full tree-sitter symbol index
sitting on disk; relaunched with per-agent index slices, the verbatim command, and
anti-crawl rules, discovery cost dropped to ~zero.

To convert a judgment-shaped task into a cheap-tier-executable one (explicit
procedures, n-shot examples), use the sibling `down-skilling` skill. This skill
decides the routing; that one engineers the prompt.

**Shared-prefix caching cuts the fan-out multiplier** (unmeasured, conditional). When
N subagents share a byte-stable prefix — the *fixed* handoff, not the per-agent
slices — prefix caching can pull that portion toward a read-discount rate *where the
orchestration surface exposes it*. Keep per-agent content at the tail. Verify your
surface caches subagent prefixes before relying on it.

## Loop discipline

Never blind-loop. Re-applying a prompt to a model's own output is the identity at
best — an LLM call already unrolls its reasoning internally — and
regression-then-freeze at worst: a re-looped haiku broke its own middle line on
iteration 2 and froze on the broken text for every iteration after.

1. **Loop only with an out-of-band evaluator** — ground truth, mechanical checker, or
   an up-tier judge scoring every iteration.
2. **Select, don't trust the last:** `final = argmax_r eval(answer_r)`.
3. **Stop on first regression.** If `eval(r) < eval(r-1)`, stop; loops froze on
   degraded output rather than recovering.
4. **Loop for diversity, not depth.** Vary the angle per iteration; identical
   re-application converges instantly.
5. **"Improve this" with no headroom is the danger zone.** It pressures the model to
   change something; without a selector, that change ships.

## Judge rules

- Judge model ≠ worker model; judge at least one tier up. Same-model self-assessment
  is untested.
- Prefer mechanical checkers wherever a spec can be executed (counts, schemas, tests,
  regex): free, deterministic, zero judge tokens.
- Judges are for rubric quality, not arithmetic — don't ask a model to verify a sum a
  Python one-liner can check.

## Escalation triggers (route up despite the table)

- The prompt names a goal rather than a deliverable (audit-and-update, follow-through
  across repos, "find what's outdated and fix it"). Sonnet 5.5 tends to stop and ask
  where Opus 5.5 carries on (observed 2026-10-07).

- The verifier fails twice at the same tier. **Route up for capability, not for
  thoroughness** — `opus` @ `high` fell into the same stop-early trap as `sonnet` @ `low`
  on three of four tasks built to reward a second look. A verifier catches that; a bigger
  model does not.
- The task requires weighing trade-offs with no checkable ground truth.
- Output ships verbatim to a human without review.
- The subagent must plan its own multi-step tool strategy over many turns.
- The task spans multiple sources that may disagree and must be reconciled.

## Observing the fan-out — you can't govern what you can't watch

Stop-on-regression and "verifier failed twice" assume you can see a subagent's work
*while it runs*. By default you can't: the session stream previews only the primary
thread, and a subagent's output lands only after its whole turn buffers.

Attach one stream per thread. Read the session stream for the coordinator; on every
`session.thread_created` (carrying `session_thread_id` and `agent_name`), attach a
watcher to `GET /v1/sessions/{id}/threads/{thread_id}/stream` with `event_deltas`.

- **Preview is a scratch buffer; the buffered event is the record.** Deltas are
  best-effort and shed under load, so concatenated deltas are a *prefix* of the final
  text. Reconcile by a single replace when the buffered `agent.message` arrives; the
  SDK's `accumulate_managed_agents_event` folds start/delta/record into one snapshot.
  One accumulator per connection. (The same trap appears offline: per-message usage
  records in transcripts include streaming partials — take the **max** per message
  id, or you undercount tokens ~2×.)
- **No replay.** A stream opened after a request started gets no deltas for it, and
  reconnects never replay — attach on `thread_created` or miss the first response.
- **Coordination events live on the primary thread** — `session.thread_created`,
  `agent.thread_message_sent`, `agent.thread_message_received`. Child tool calls
  cross-posted to the primary carry `session_thread_id`; skip them.
- **Terminate cleanly.** Watchers exit on `session.thread_status_idle`; the main loop
  on `session.status_idle` — print the stop reason when it isn't `end_turn`, and
  break on terminated-status events.

Operational, not calibrated. Source: Anthropic Managed Agents notebook
`CMA_watch_subagents_live` (beta `managed-agents-2026-04-01`); contract in
[events and streaming](https://platform.claude.com/docs/en/managed-agents/events-and-streaming#event-deltas).

## Measure before trusting this

Everything above is measured on three batteries: a 300-call deterministic calibration
(references/calibration-2026-07-15.md), a 14-task hidden-test coding suite (2026-08-17,
~190 subagent runs), and a 14-repo seeded-bug agentic battery (2026-09-03, ~120 subagent
runs, `oaustegard/experiments` → `temporal-routing-headroom`) that measured the cascade
rungs, the escalation signal, and the tier gap against each other, rerun on 2026-10-07
with Haiku 5.5 at both rungs and priced per spawn from the subagent transcripts
(`harness/subagent_cost.py` there). Re-measure when:

- **A model or price revision lands.** Both the verbosity multipliers and the
  cost table above invert on either. Sonnet 5.5 (2026-09-29) and Haiku 5.5 (2026-10, 10×
  cheaper than Haiku 4.5) are such revisions. Haiku 5.5 is measured on the seeded-bug battery only;
  its verbosity on the generation suite, and what `effort` does to it, are not. Sonnet
  5.5's effort levels are measured above on the seeded-bug battery only; the other Sonnet
  figures in this skill are Sonnet 5 data, and the verbosity multipliers and the
  generation-suite costs have not been re-run on the 5.5 generation.
- **The task family is off all three batteries.** No deterministic task has made Haiku
  fail on correctness yet, so the capability cliff is past what's been probed. Seeded-bug
  repair in a small module is now measured as *not* tier-separating: three probe shapes
  aimed at thoroughness, at ambiguity the tests underdetermine, and at a repo with no test
  suite at all, and `sonnet` @ `low` solved all six cells against `opus` @ `high`.
- **Output length differs materially** from what was measured. The whole cost model
  keys on token volume; a 10× longer artifact re-opens the tier question.
- **You need pass-rate differences of 1–2 tasks.** Run-to-run variance swamps them:
  two runs of the same model on the same 14 tasks produced disjoint failure sets and
  a 23% token gap. Token deltas are trustworthy; small pass-rate deltas are not.
