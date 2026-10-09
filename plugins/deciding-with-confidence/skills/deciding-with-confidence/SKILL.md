---
name: deciding-with-confidence
description: "Routes, triages, flags and rates a piece of text with a probability for every option: which department or queue a ticket goes to, which intent a message expresses, whether a yes/no condition holds (is this tool call grounded, should the agent ask first, is the customer angry), and how severe or urgent it is on a rubric, each with a calibrated confidence. Runs Claude Haiku in the request and response shapes of OpenAI's Decisions API, for when no purpose-built decision model is at hand. Use for \"route this ticket\", \"triage these\", \"classify with a confidence\", \"give me a probability that\", \"rate the severity\", \"score against this rubric\", guardrail checks before a tool call, or \"a Decisions API without OpenAI\"."
metadata:
  version: 0.1.0
---

# Deciding with confidence

`scripts/decide.py` takes an OpenAI Decisions API request (`input` plus
`questions` of type `predicate`, `choice` or `score`) and returns its response
shape: a probability per option, the chosen value or score, and `confidence`.
Claude Haiku 5.5 answers. Its logits are not exposed, so the distribution is
estimated: each of k parallel samples states a probability per option with the
options in a different order, the samples are averaged, and the average is
temperature-scaled from a labelled eval. Disagreement between samples lowers
`confidence` and shows up in `diagnostics.agreement`.

Expect about 85% of what a purpose-built decision model gets: on the bundled
104-item eval, accuracy 0.846 against Jev's 0.894, with a calibration error
(ECE 0.041) that matches it. Haiku's wrong answers come at low confidence, so a
threshold sends them on. `references/method.md` has the comparison and numbers.

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| The label set is too large to list in a prompt (a taxonomy, hundreds of tags) | `hallucinating-labels` |
| The answer needs reasoning, multi-step work or a written explanation | a normal Claude call; this skill forbids explanation |
| You need extracted fields or free-form JSON | structured outputs on the Messages API |
| A real decision model is reachable (OpenAI `/v1/decisions`, Strands Decider, Jev) and latency matters | that model: 0.1–0.3 s against ~0.7–4 s here |
| Picking which Claude tier runs a subagent | `agent-routing` |
| The evidence is an image | not supported; the transports send text only |

Abandon a run when `diagnostics.agreement` is below 1 on most of a batch: the
questions or option descriptions are ambiguous, and more samples will not fix
them. Rewrite the options (distinct, observable criteria) before sampling more.

## Procedure

1. **Write the request** as JSON in the OpenAI shape. Give every question a
   unique `name`. Options need `description`s that say when each applies; add
   an `other` choice when the set is not exhaustive. Score `levels` go lowest
   first.

   ```json
   {"input": "I was charged twice for my order.",
    "questions": [
      {"type": "choice", "name": "department", "instructions": "Which department should handle this?",
       "choices": [{"value": "billing", "description": "Payments, invoices, refunds."},
                   {"value": "shipping", "description": "Delivery and tracking."},
                   {"value": "other", "description": "Anything else."}]},
      {"type": "predicate", "name": "angry", "instructions": "Is the customer expressing anger?"},
      {"type": "score", "name": "severity", "instructions": "How severe is this?",
       "levels": [{"label": "Cosmetic", "description": "No lost functionality."},
                  {"label": "Workaround", "description": "Fails, another way works."},
                  {"label": "Blocked", "description": "Fails with no workaround."}]}]}
   ```

2. **Pick the transport.** `--transport auto` (the default) takes the first that works:

   | Transport | Needs | Wall time per request |
   |---|---|---|
   | `api` | `pip install anthropic` and `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` | ~0.7 s expected (the API time measured inside `claude -p`) |
   | `cli` | the `claude` CLI, logged in | ~4 s, measured |
   | `bedrock` | `pip install anthropic`, `AWS_REGION`, AWS credentials; explicit only | as `api` |

   With none of them, use the subagent path in step 3b.

3. **Run it.**

   a. With a transport:
   ```bash
   S=/mnt/skills/user/deciding-with-confidence/scripts   # or wherever the skill lives
   python3 $S/decide.py run request.json            # k=3 by default
   echo '{...}' | python3 $S/decide.py run -
   ```
   From Python: `sys.path.insert(0, S); import decide; decide.decide(req)` returns
   the response dict, or None when no sample was usable.

   b. In a Claude Code session, the plugin's `decider` subagent is the
   cheaper path: it is pinned to `claude-haiku-5-5` (the model the calibration
   was fitted on) and carries its instructions inline, so it answers without a
   tool call. Install the `deciding-with-confidence` plugin, or copy
   `agents/decider.md` to `.claude/agents/`; agent definitions load at session
   start. Then:
   ```bash
   python3 $S/decide.py emit request.json -k 3 --agent deciding-with-confidence:decider > batch.json
   ```
   Use the name the Agent tool lists: `deciding-with-confidence:decider` from
   the plugin, `decider` from `.claude/agents/`. Send each `samples[i].prompt`
   verbatim as an Agent call with that `subagent_type`, all in one message.
   Collect the reply texts into a JSON list in `replies.json`, then
   `python3 $S/decide.py aggregate batch.json replies.json`. Pool before acting:
   a single reply carries no agreement signal and no calibration.

   Without the agent installed, omit `--agent`: the system prompt then rides
   inside each prompt for a stock general-purpose subagent with
   `model: haiku`. That works and costs about 58K tokens a sample against 9K.

4. **Read the answer.** Predicates give `probability` (P true). Choices give
   `choice`, `probabilities` and `confidence`. Scores give `score` (the
   probability-weighted level index, so 1.4 sits between levels 1 and 2),
   `probabilities` and `confidence`. Every answer carries `diagnostics`:
   `agreement`, `spread`, the pre-calibration `raw` pool and `per_sample`.

5. **Act on it with thresholds, never on the top answer alone.**
   - `agreement < 1` (the samples' top answers differ): escalate. On the bundled
     eval, unanimous answers were 92% right and split ones 44%.
   - Top probability under 0.7: escalate. That sent 28% of items onward and
     left 4 wrong in 104.
   - Set the final thresholds from labelled examples of your own traffic,
     weighing the cost of a false positive against a false negative.

6. **Calibrate on your own labels** when you have 50 or more per question type:
   ```bash
   python3 $S/decide.py eval my_labelled.jsonl --out results.jsonl   # {id, input, questions, labels}
   python3 $S/decide.py calibrate results.jsonl --out my-cal.json
   export DECIDER_CALIBRATION=$PWD/my-cal.json
   ```
   The bundled `assets/calibration.json` fits only `choice` (T = 0.62, fitted
   through the `cli` transport). Predicate and score keep T = 1 until a type
   has 50 labels, because smaller sets swung between folds.

## Earned exceptions

| Rule | Banned when | Earned when |
|---|---|---|
| k=3 samples | latency or cost is the constraint | always the default: parallel samples cost no wall time, and k=1 loses the agreement signal |
| Bundled calibration | your transport or domain differs from the eval's (`cli`, banking and support text) | you have not yet labelled 50 items of your own |
| Escalate on `agreement < 1` | nothing stronger sits behind it | a stronger model or a human can take the split items |

## Common failure modes

- **`decide: no usable sample; first error: TypeError: "Could not resolve
  authentication method..."`** → the `api` transport found no key. Set
  `ANTHROPIC_API_KEY`, or pass `--transport cli`.
- **`decide: no transport`** → no key and no `claude` on PATH. Use step 3b.
- **`diagnostics.samples` below k** → some replies did not parse. Usually a
  transport timeout under heavy concurrency; lower `DECIDER_WORKERS` (default 8)
  or raise `DECIDER_TIMEOUT` (default 60 s).
- **Every answer near uniform** (confidence around 0.1–0.2 throughout) →
  options without descriptions, or descriptions that overlap. Rewrite them so
  each has distinct, observable criteria; more samples will not help.
- **A subagent reply with prose around the JSON** → `aggregate` takes the
  outermost `{...}` and copes. A reply with no JSON at all counts as a failed
  sample.
- **Transcript text showing up as evidence in the subagent path** → the
  `[no-context]` line was dropped from the prompt. Send the emitted prompt
  verbatim.

## Verification

Run the tests, then one live request:

```bash
python3 -m pytest /mnt/skills/user/deciding-with-confidence/tests -q    # 39 pass, no network
echo '{"input":"Nobody can log in since the 2pm deploy.","questions":[{"type":"predicate","name":"outage","instructions":"Is a service down for users?"}]}' \
  | python3 $S/decide.py run -
```

The live answer should have `probability` above 0.9 and `diagnostics.samples`
equal to 3. A **bad success** is an answer with `samples: 1` from a k=3 run:
it looks normal but has lost the agreement signal. Check `samples` when a
batch runs under load.

## Diagnosed failures

- **2026-10-09, first eval:** 14 of 520 samples were discarded because Haiku
  left the options it ruled out of 8-way choices. Missing keys now share the
  probability mass the sample left unassigned, and the re-run lost none. The
  prompt also asks for ruled-out options at 0.001.
- **2026-10-09:** `claude -p --json-schema` doubled API time (2.2 s against
  0.8 s) with a second turn and three times the output tokens. The `cli`
  transport sends the JSON contract in the system prompt instead.
- **2026-10-09:** the claude-workspace PreToolUse hook that appends
  parent-transcript chunks to Agent prompts would have put them in the
  evidence. `emit` appends `[no-context]`, which that hook honours.
