---
name: agent-routing
description: Decide which model, effort level, and cascade shape each subagent gets, and how to keep improvement loops safe (evaluator-as-selector, stop on regression). Routes on measured cost-per-completed-task rather than per-token price, because a tier's token count varies more by task shape than price varies across tiers. Covers per-model effort semantics, the concision lever, cascade preconditions, context handoff, and watching a subagent fan-out live. Use when spawning subagents via the Agent or Workflow tools, when fanning out more than a handful of agents, or when asked which model or effort a task should get. Grounded in measured calibration (references/calibration-2026-07-15.md), a 2026-08 coding-cost study, and a 2026-09 agentic-repair battery that measured the cascade rungs directly; Managed Agents API specifics are operational, not calibrated.
compatibility: Designed for Claude Code / Claude Code on the Web — assumes an orchestrator with Agent/Workflow subagent tools exposing per-call model and effort options. Not applicable to claude.ai chat use.
metadata:
  author: Oskar Austegard and Claude
  version: "2.1.0"
---

# Agent Routing — model, effort, and cascade selection

## The rule that decides everything

**Cost is output tokens × output price.** Prices span ~5× across tiers. Token
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

Haiku is 5× cheaper per token and cost **30% more per solved task** than Opus,
because it emitted 6.7× the tokens. Prices: Haiku 4.5 $1/$5, Sonnet 5 $2/$10,
Opus 5 $5/$25 per MTok.

## Two questions before spawning

1. **Is the output short or long?** Short = a schema instance, a label, an answer,
   a small patch. Long = a module, a document, a plan, a review.
2. **Is it mechanically checkable, or does it need judgment?**

| | short output | long output |
|---|---|---|
| **checkable** | `haiku` @ `low` + verifier | `sonnet` @ `medium` + concision + verifier |
| **judgment** | `sonnet` @ `medium` | `sonnet`/`opus` @ `high` |

Output length is the discriminator because it is what the verbosity multiplier
multiplies. Haiku's premium is invisible on a 200-token JSON object and ruinous on
a 700-token module that costs it 13,000 tokens of thinking to produce.

## Routing table

| Task shape | Model | Effort | Verify with |
|---|---|---|---|
| Extraction, classification, format transforms, schema-bound output | `haiku` | `low` | schema / spot-check |
| Closed-form computation, state tracking, multi-hop lookup | `haiku` | `low` | deterministic check |
| Constraint-bound generation (exact counts, required tokens, lipograms) | `haiku` | `low` | mechanical checker |
| Bulk scans/greps, per-file summaries, fan-out reads | `haiku` | `low` | sample audit |
| **Code generation from a spec; any long structured artifact** | **`sonnet`** | **`medium`** | run the tests |
| Code edits with tests available | `sonnet` | `medium` | run the tests |
| Judging / scoring another model's output | `sonnet`+ | `medium` | — (judge ≠ worker) |
| Ambiguity resolution, novel synthesis, architecture, taste | `sonnet`/`opus` | `high` | human or panel |
| Long-horizon multi-step agentic work, cross-file reasoning | `sonnet`/`opus` | `high`/`xhigh` | milestone checks |

Haiku holds the top four rows on merit: 240/240 measured across nested modular
arithmetic, 30-hop chains, 25-operation state tracking, trap-laden word math, and
5-constraint generation — at `effort: low`, some with CoT suppressed
(references/calibration-2026-07-15.md). **Do not up-tier short checkable work "to be
safe"**; there is no measured benefit and it costs 3–5×. The burden of proof is on
routing up.

Haiku loses the generation rows on cost alone, not capability — it scored 14/14 on
the same suite Opus swept.

## Effort is model-specific — verify per model before reusing a level

Measured 2026-08-17 via per-message `output_tokens_details.thinking_tokens`,
thinking as a share of output on identical prompts:

| model | `low` | `medium` |
|---|---|---|
| Sonnet 5 | **2.9%** | 47.7% (61.7% without concision) |
| Haiku 4.5 | **88–91%** | 88–91% |

`low` is a near kill-switch on Sonnet and a mild trim on Haiku. Sonnet at `low`
dropped 14/14 → 10/14; Haiku at `low` shed only ~26% of its tokens. So:

- **Tune Sonnet with the prompt, not the effort knob.** `medium` is the working
  floor; `low` overshoots into thinking-off.
- **Tune Haiku with the prompt too**, because the knob barely moves it.
- Effort is set **on the agent, not per session** — an `effort` inside a per-session
  `model` override is silently ignored. Levels: `low`, `medium`, `high`, `xhigh`,
  `max`. Not every model accepts every level; an invalid pair is rejected at
  agent-create. The create response echoes the resolved config — if `effort` returns
  `None`, the org's beta header (`managed-agents-2026-04-01`) doesn't carry the
  feature and the field was dropped, not rejected.
- Buy depth only for judgment-heavy roles; drop triage and formatting roles to `low`
  without touching the expensive role's budget.

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
discount outright — Haiku at $0.067/task against Sonnet's $0.031 made
`haiku → sonnet` worse than Sonnet alone **regardless of `p_fail`**: the attempt
cost 2× the destination's entire job. Compute this before designing the ladder.

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

**Rung 2 is the same model one effort step up. A tier jump is the exception you justify.**
Measured twice. On a second battery (14 seeded-bug repos, 2026-09-03) rung 2 ran from an
identical failed attempt at both settings: `sonnet` @ `medium` and `opus` @ `high` rescued
the same 4 of 5 tasks and both missed the same fifth, at 11,691 against 32,504 output
tokens. Composed over the same rung 1, the same-model cascade cost **0.31×** always-`opus`
and the tier jump **0.76×**. The tier jump costs 2.5× and buys nothing.

**A cascade can beat the frontier solo arm on correctness, not only on cost.** In that run
the `sonnet`→`sonnet` cascade solved 13/14 where always-`opus` solved 10/14. `opus`
starting from the issue text fell into the same stop-early trap as `sonnet` on three
tasks; `opus` starting from the failed patch and the failing assertions fixed all three.

**Caching pushes the same way.** Caches are model-scoped with no escape hatch, so a tier
jump discards rung 1's prefix while a same-model rung keeps at least the tools and system
tiers. An `effort` change still invalidates the messages cache on every model, and the
per-message effort escape hatch (`{"role": "system", "content": [], "output_config":
{"effort": …}}`, beta `mid-conversation-output-config-2026-07-01`) is
Opus 5 / Fable 5.1 / Mythos 5.1 only — not Sonnet 5. The real bill gap is therefore wider
than the output-token ratio above. Every figure in this skill prices output tokens only;
input and cache effects sit outside its cost model.

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
rungs, the escalation signal, and the tier gap against each other. Re-measure when:

- **A model or price revision lands.** Both the verbosity multipliers and the
  cost table above invert on either.
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
