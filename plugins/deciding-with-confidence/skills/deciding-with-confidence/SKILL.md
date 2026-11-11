---
name: deciding-with-confidence
description: "Routes, triages, flags and rates a piece of text with a probability for every option: which department or queue a ticket goes to, which intent a message expresses, whether a yes/no condition holds (is this tool call grounded, should the agent ask first, is the customer angry), and how severe or urgent it is on a rubric, each with a calibrated confidence. Runs Claude Haiku in the request and response shapes of OpenAI's Decisions API, for when no purpose-built decision model is at hand. Use for \"route this ticket\", \"triage these\", \"classify with a confidence\", \"give me a probability that\", \"rate the severity\", \"score against this rubric\", guardrail checks before a tool call, or \"a Decisions API without OpenAI\"."
metadata:
  version: 0.3.0
---

# Deciding with confidence

`scripts/decide.py` takes an OpenAI Decisions API request (`input` plus
`questions` of type `predicate`, `choice` or `score`) and returns its response
shape: a probability per option, the chosen value or score, and `confidence`.
Claude Haiku 5.5 answers. Its logits are not exposed, so the distribution is
estimated: a sample states a probability per option, and the result is
temperature-scaled from a labelled eval.

The default is **one sample at low effort**: one call, the answer, and the
probability that call stated. That confidence is weaker than a pooled one,
because nothing checks it. When the confidence will gate an action, run
`--stack`: three parallel samples, each under a different angle (plain,
literal, sceptic) and option order, averaged. Their disagreement lowers
`confidence` and shows up in `diagnostics.agreement`.

Every sample answers each question with a `cue` first: the few words of the
evidence that decide it, quoted. Quoting before committing to probabilities
was worth more than any other prompt change tested.

Measured 2026-11-11 on the held-out half of three labelled sets, through the
`cli` transport at low effort. The sets are 52 short banking-intent,
guardrail and severity items; 77 whole research articles (289 labelled
questions); and 204 article sections (1,457 labelled questions):

| | short items | whole articles | sections | cost per request |
|---|---|---|---|---|
| one sample (default) | 0.827 | 0.969 | 0.870 | $0.0005–0.0024 |
| `--stack` | 0.865 | 0.962 | 0.906 | 3x |
| one sample, same prompt without the cue | 0.808 | 0.931 | 0.857 | slightly less |

On whole articles one sample is as good as the stack. On sections the stack
adds 0.036, and it also beat three cue-less samples at the CLI's default
effort (0.893 against 0.885 on the 591 answers both runs covered). The
stack's main value is its agreement signal: answers its three samples agreed
on were 90% to 98% right, split ones 63% to 73%. For comparison, Jev, a
purpose-built decision model from TypeSafe, scored 0.894 on all 104 short
items. `references/method.md` has the full tables.

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
   first. When the evidence is a file on disk (a paper, a log, a transcript),
   give `"input_file": "path"` in place of `"input"`: the script or the
   subagent reads it, and you do not write the document out again. When the
   evidence is this conversation, give `"input_transcript": true` (or
   `{"last_turns": 20, "max_chars": 60000}`): the script reads the transcript
   Claude Code keeps on disk for the session, renders the last turns with
   tool calls clipped, and redacts secrets. The file can trail the turn in
   progress, so do not ask it about a tool result from this same turn.

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
   python3 $S/decide.py run request.json            # one low-effort sample
   python3 $S/decide.py run request.json --stack    # three angles, pooled: use when confidence gates an action
   echo '{...}' | python3 $S/decide.py run -
   python3 $S/decide.py batch requests.jsonl --out responses.jsonl   # one request per line, resumable
   ```
   From Python: `sys.path.insert(0, S); import decide; decide.decide(req)` returns
   the response dict, or None when no sample was usable; pass
   `k=3, angles=decide.STACK` for the stack. `--angles` takes any comma-separated
   list, and a request's `"angles"` may hold instruction text of your own.

   b. In a Claude Code session, the plugin's `decider` subagent is the
   cheaper path: it is pinned to `claude-haiku-5-5` (the model the calibration
   was fitted on) and carries its instructions inline, so it answers without a
   tool call. Install the `deciding-with-confidence` plugin, or copy
   `agents/decider.md` to `.claude/agents/`; agent definitions load at session
   start. Then:
   ```bash
   python3 $S/decide.py emit request.json --stack --agent deciding-with-confidence:decider > batch.json
   ```
   Use the name the Agent tool lists: `deciding-with-confidence:decider` from
   the plugin, `decider` from `.claude/agents/`. Send each `samples[i].prompt`
   verbatim as an Agent call with that `subagent_type`, all in one message.
   Collect the reply texts into a JSON list in `replies.json`, then
   `python3 $S/decide.py aggregate batch.json replies.json`. A single reply
   carries no agreement signal and no calibration until `aggregate` has run.
   With `input_file` the emitted prompt names the file and the subagent reads
   it, so you send a short prompt however long the document is.

   Without the agent installed, omit `--agent`: the system prompt then rides
   inside each prompt for a stock general-purpose subagent with
   `model: haiku`. That works and costs about 58K tokens a sample against 9K.

4. **Read the answer.** Predicates give `probability` (P true). Choices give
   `choice`, `probabilities` and `confidence`. Scores give `score` (the
   probability-weighted level index, so 1.4 sits between levels 1 and 2),
   `probabilities` and `confidence`. Every answer carries `diagnostics`:
   `agreement`, `spread`, the pre-calibration `raw` pool and `per_sample`.
   The samples' cues are not returned.

5. **Act on it with thresholds, never on the top answer alone.**
   - With one sample there is no `agreement`; use the top-probability rule
     alone, or rerun the doubtful ones with `--stack`.
   - `agreement < 1` (the samples' top answers differ): escalate. With
     `--stack`, unanimous answers were 90% to 98% right across the three sets
     and split ones 63% to 73%.
   - Top probability under 0.7 (after calibration): escalate. On article
     sections that sent 17% of one-sample answers onward and left 5.6% of
     all answers wrong; with the stack, adding the split rule sent 19% and
     left 3.0% wrong. Both assume the escalation target gets every escalated
     answer right. Treat 0.7 as a starting point.
   - Set the final thresholds from labelled examples of your own traffic,
     weighing the cost of a false positive against a false negative.

6. **Calibrate on your own labels** when you have 50 or more per question type:
   ```bash
   python3 $S/decide.py eval my_labelled.jsonl --out results.jsonl   # {id, input, questions, labels}
   python3 $S/decide.py calibrate results.jsonl --out my-cal.json
   export DECIDER_CALIBRATION=$PWD/my-cal.json
   ```
   Run `eval` with `--stack` so the file holds both temperature sets. One sample
   and a pool of three need different temperatures, because averaging three
   samples flattens the distribution. `calibrate` fits single-sample
   temperatures from each request's first sample and pooled ones from the
   pools, and a type with fewer than 50 labels keeps T = 1. The bundled
   `assets/calibration.json` was fitted through the `cli` transport on the
   1,798 labelled answers above. Every temperature is below 1, so Haiku's
   stated probabilities are underconfident and the calibration sharpens
   them. Single-sample T is 0.74 for predicates, 0.60 for choices and 0.81
   for scores; the pooled T values are 0.44, 0.52 and 0.50.

## Earned exceptions

| Rule | Banned when | Earned when |
|---|---|---|
| One sample | the confidence decides whether something is escalated, blocked or sent on | you need the answer, and a wrong one is cheap or gets reviewed anyway |
| `--stack` | cost is the constraint and nothing reads the confidence | the confidence gates an action: parallel samples cost no wall time and 3x the tokens |
| Bundled calibration | your transport or domain differs from the eval's (`cli`; banking, support and life-science text) | you have not yet labelled 50 items of your own |
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
- **`decide: input_transcript: no session id` or `no transcript for session`**
  → the script is not running inside a Claude Code session, or the transcript
  lives elsewhere. Pass `{"path": "/path/to/session.jsonl"}`.
- **A subagent reply with prose around the JSON** → `aggregate` takes the
  outermost `{...}` and copes. A reply with no JSON at all counts as a failed
  sample.
- **Transcript text showing up as evidence in the subagent path** → the
  `[no-context]` line was dropped from the prompt. Send the emitted prompt
  verbatim.

## Verification

Run the tests, then one live request:

```bash
python3 -m pytest /mnt/skills/user/deciding-with-confidence/tests -q    # 50 collected, no network
echo '{"input":"Nobody can log in since the 2pm deploy.","questions":[{"type":"predicate","name":"outage","instructions":"Is a service down for users?"}]}' \
  | python3 $S/decide.py run -
```

The live answer should have `probability` above 0.9 and `diagnostics.samples`
equal to 1 (3 with `--stack`). A **bad success** is an answer with `samples: 1`
from a `--stack` run: it looks normal but has lost the agreement signal. Check
`samples` when a batch runs under load.

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
- **2026-11-10:** the `cli` transport passed the sample prompt as a command-line
  argument, which caps a single argument at about 128 KB and so cannot carry a
  long document. The prompt now goes in on stdin.
- **2026-11-10:** a session that pasted a document into each subagent prompt
  paid for the document in its own output tokens, once per sample. A request
  with `input_file` is emitted as a path for the subagent to read.
- **2026-11-10:** a decision about the conversation itself meant restating the
  conversation in the request. `input_transcript` reads it from the session's
  transcript file; on a long session one call over the last six turns read
  38,580 characters and cost $0.0036.
- **2026-11-11:** one temperature per question type, fitted on pools,
  applied to single samples and pools alike. With the cue prompt the stack's
  pools were further from calibrated (ECE 0.10 to 0.15) than single samples
  were, because averaging flattens them. Pools now have their own
  temperatures, and cross-validated ECE is 0.01 to 0.05 for both.
