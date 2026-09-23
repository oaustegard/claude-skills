---
name: delegating-with-context
description: Delegates work to a subagent or spawned session by writing only the task, while a PreToolUse hook pages the parent transcript through Jev and appends the chunks that task needs. Use before writing any Agent tool prompt, and when asked to delegate this, hand this off, use a subagent, spawn an agent, run agents in parallel, or brief a subagent on what we have done so far.
metadata:
  version: 0.1.0
---

# Delegating with context

Writing a background brief for a subagent costs output tokens, generation
time, and fidelity: exact paths, error strings and numbers get paraphrased or
dropped, and the brief omits what the orchestrator did not know mattered. The
`context_hook.py` PreToolUse hook removes the need. It reads the session
transcript, asks Jev which chunks the task needs, and appends those chunks to
the subagent's prompt verbatim. The hook fires after the prompt is written, so
it cannot save a brief you already wrote. The saving happens here, before the
tool input exists.

## Procedure

1. **Check the hook is live.** `test -s ~/.claude/context-filter-log.jsonl && tail -1 ~/.claude/context-filter-log.jsonl`
   shows the last filtered delegation. No file on a first delegation is normal;
   the hook's reply after your first Agent call confirms it (step 5). Where the
   hook is not wired (claude.ai, a machine without the settings entry), stop
   here and write a normal brief.

2. **Preview what the filter would pass.** One call, all tasks at once:

   ```bash
   python3 /mnt/skills/user/delegating-with-context/scripts/preview.py \
     --task "Write the xr latency note for the follow-up memory" \
     --task "Draft the closing status for both PRs"
   ```

   Each task prints the kept chunk ids with a one-line gist. This is the
   check: find the chunk that holds the fact the subagent must not miss. It
   takes one to two seconds and costs a fraction of a cent.

3. **Write only the task.** What to do, the deliverable, its format, and any
   constraint that was never written down in the session. Name things the way
   the transcript names them ("the Sniff Test benchmark table", "PR #812"):
   Jev reads literally, and a named thing matches its chunk while "that thing
   we discussed" matches nothing.

4. **Add only what the preview missed.** If a needed fact is in no kept chunk,
   state that one fact in the prompt, or raise the budget with
   `[context-budget: 40000]` in the prompt text. Do not restate facts the
   preview already showed.

5. **Spawn, then read the hook's reply.** The hook answers with
   `context-filter: appended N of M parent-session chunks (...)` and the kept
   ids. `context-filter FAILED (...)` means the subagent got your prompt alone:
   send it the missing facts with SendMessage or re-delegate with them stated.

`create_session` is not covered: whether `updatedInput` applies to MCP tools
is untested, so a spawned session still needs its brief written out.

## Markers the hook reads

| In the prompt | Effect |
|---|---|
| `[no-context]` | Hook skips; the prompt goes as written |
| `[context-budget: N]` | Token budget for appended context (default 20000) |
| `subagent_type: "fork"` | Hook skips; a fork already inherits the parent context |

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| The subagent needs nothing from this session (fresh research, a standalone lookup) | Add `[no-context]` and write the prompt normally |
| The subagent must reason over the whole session (review everything we did) | `subagent_type: "fork"`; it inherits the full context |
| Many small per-item judgments (label 400 rows) | Jev or Gemini directly, per `docs/delegation.md` in claude-workspace; a subagent costs ~32k tokens before it reads its prompt |
| Choosing which model or agent type should run the work | `agent-routing` |
| Parallel API fan-out from claude.ai, where hooks do not run | `orchestrating-agents` |

## Earned exceptions to "write only the task"

| Restating background is | when |
|---|---|
| banned | the fact appears in the transcript as a tool result, a user message or your own reply |
| earned | the fact exists only in your reasoning (thinking is not in the transcript), a decision you made silently, or a constraint nobody wrote down |
| earned | the preview shows the chunk holding it was not kept |

## Abandon the procedure when

- The hook reports FAILED twice in a row: the transport or key is broken, and
  every further delegation silently runs without context. Write briefs and fix
  the transport (Failure modes below).
- The subagent's reply says a fact was missing that the preview showed as
  kept: the chunk was clipped (a kept chunk is capped at ~6k tokens). Send the
  fact directly.

## Common failure modes

- **No `context-filter:` line after an Agent call** → the hook is not wired or
  crashed before printing. Check `.claude/settings.json` for the PreToolUse
  entry and run `echo '{}' | python3 .../context_hook.py`; it must exit 0 silently.
- **`no Jev transport`** → neither `CF_ACCOUNT_ID` + `CF_API_TOKEN` (the
  TypeSafe key is stored in the Cloudflare AI Gateway, `CF_GATEWAY_ID` routes
  to it) nor `TYPESAFE_API_KEY` is set in the hook's environment.
- **Preview keeps many chunks that all mention the session's main topic** →
  the scores are compressed because everything looks related. Rename the task
  with the distinctive nouns of the thing you want; rank, not threshold, is
  what selects.
- **HTTP 429 `Rate limited`, code 2003** → the AI Gateway's own limit. The
  filter runs 2 calls at a time and honours Retry-After; parallel delegations
  each run their own filter, so stagger a fan-out of more than ~4 spawns.
- **`blocked_chunks` above 0 in the log, or HTTP 402 "Payment error from model
  using BYOK"** → not billing. TypeSafe's edge WAF rejected the request bytes
  (shell commands and curl lines in a transcript read as attack payloads). The
  filter bisects the window and scores each blocked chunk 0.5, so it can still
  be kept on rank. If a chunk you need is blocked, state its fact in the prompt.
- **A kept chunk states something a later chunk corrected** → each chunk is
  scored on its own merits. User messages are force-kept (clipped) because
  they carry corrections; if a correction lives in a tool result, state it.

## Verification

After the subagent returns: its reply must not say a needed fact was missing,
and `tail -1 ~/.claude/context-filter-log.jsonl` must show the delegation with
`kept_ids` and no `error` key. A bad success looks like a fluent deliverable
with a plausible but wrong number: compare one specific figure against the
chunk it came from before relaying it.

## Diagnosed failures

- 2026-09-22: the first selection rule force-kept every user-role message.
  Skill bodies and stop-hook feedback are user-role (`isMeta`) turns, and on a
  181-chunk session they filled the whole 20k budget before any tool result
  was considered; the chunk holding the answer was dropped. Fixed: `isMeta`
  turns are scored like tool results, and real user messages are clipped and
  capped at a quarter of the budget.
- 2026-09-22: a single condensed window (every chunk clipped to ~1k chars)
  ranked the key chunk 6th because the fact sat mid-result, outside the clip.
  Paging at 4x view (five ~27k windows, 1.6 s) ranked it 1st. The filter
  defaults to the paged view.
- 2026-09-23, eval over 32 delegations from 8 archived sessions: written
  briefs lost every fact on 5 tasks by telling the subagent to look the fact up
  ("check the pr-workflow config entry") instead of stating it; neither the
  filter nor the full transcript ever did. That is what step 3 prevents.

## Scripts

- `scripts/chunking.py`: transcript JSONL to chunks (user, assistant, harness,
  tool call + result), with secret values and token patterns redacted before
  anything leaves the machine.
- `scripts/jevfilter.py`: windows under Jev's limits (32k state plus longest
  question, 64k state plus all questions), one Noul per chunk, rank into the
  budget.
- `scripts/context_hook.py`: the PreToolUse hook. Fails open and says so.
- `scripts/preview.py`: step 2.

Hook entry for `.claude/settings.json`:

```json
{"matcher": "Agent|Task", "hooks": [{"type": "command", "timeout": 120,
  "command": "python3 /mnt/skills/user/delegating-with-context/scripts/context_hook.py"}]}
```

Evidence: with ~20k tokens of selected chunks a fresh subagent found 99/105
required facts, against 102/105 with the whole ~81k-token transcript and 82/105
with a written brief; method and caveats in
`oaustegard/experiments/subagent-context-filter/RESULTS.md`.
