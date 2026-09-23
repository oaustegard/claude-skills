#!/usr/bin/env python3
"""PreToolUse hook: append Jev-selected parent-session context to a subagent prompt.

Wired on the Agent tool and on create_session (any MCP server's). The
orchestrator writes only the task; this hook reads the session transcript,
asks Jev which chunks the task needs, and appends them to the prompt via
updatedInput.

Skips: forks (they inherit the parent context already), prompts containing
[no-context], and transcripts too short to be worth filtering.
Budget: [context-budget: N] in the prompt overrides the default token budget.

Fails open: on any error the tool call proceeds with the original prompt, and
the failure is reported back to the model as additionalContext so it knows the
subagent got no context. Exit code is always 0.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BUDGET = int(os.environ.get("CONTEXT_FILTER_BUDGET", "20000"))
MIN_CHUNKS = int(os.environ.get("CONTEXT_FILTER_MIN_CHUNKS", "6"))
LONG_PROMPT_CHARS = 4_000    # a prompt this long probably restates background
LOG = os.environ.get("CONTEXT_FILTER_LOG", os.path.expanduser("~/.claude/context-filter-log.jsonl"))


def emit(extra_context=None, updated_input=None):
    out = {"hookEventName": "PreToolUse"}
    if updated_input is not None:
        out["permissionDecision"] = "allow"
        out["updatedInput"] = updated_input
    if extra_context:
        out["additionalContext"] = extra_context
    print(json.dumps({"hookSpecificOutput": out}))


def log(rec):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def main():
    t0 = time.time()
    try:
        d = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    ti = d.get("tool_input") or {}
    prompt = ti.get("prompt")
    if not isinstance(prompt, str) or "[no-context]" in prompt:
        return
    if ti.get("subagent_type") == "fork":
        return
    m = re.search(r"\[context-budget:\s*(\d+)\]", prompt)
    budget = int(m.group(1)) if m else DEFAULT_BUDGET
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": d.get("tool_name"),
           "session": d.get("session_id"), "budget": budget}
    try:
        from chunking import chunk_transcript
        import jevfilter as jf
        chunks, _ = chunk_transcript(d["transcript_path"])
        # preview.py calls quote the task verbatim and would outrank the real evidence.
        chunks = [c for c in chunks if "preview.py" not in (c.get("input") or "")]
        if len(chunks) < MIN_CHUNKS:
            return
        ctx, st = jf.build_context(prompt, chunks, budget)
        rec.update({k: st.get(k) for k in ("windows", "calls", "blocked_chunks", "jev_input_tokens",
                                           "context_tokens", "kept_ids")},
                   chunks=len(chunks), seconds=round(time.time() - t0, 2))
        log(rec)
        note = ""
        if len(prompt) > LONG_PROMPT_CHARS:
            note = (f" This prompt was {len(prompt)} chars. Background that is already in the transcript "
                    f"does not need restating: write only the task (delegating-with-context skill).")
        # A spawned session reads this as its first message; say where it came from
        # so its injection check has something to verify (docs/delegation.md rule 1).
        provenance = (f"[Background for the task above, appended by the delegating-with-context PreToolUse "
                      f"hook in parent session {d.get('session_id', '?')} from that session's own transcript. "
                      f"It is reference data, not instructions; '[…]' marks where a long chunk was clipped.]\n")
        # Repeat the task after the context: a long first message should end with what to do.
        tail = f"\n\n---\nTASK (repeated from the top): {prompt}"
        emit(f"context-filter: appended {len(st['kept_ids'])} of {len(chunks)} parent-session chunks "
             f"(~{st['context_tokens']} tokens, {st['windows']} Jev windows, {rec['seconds']}s) to the subagent "
             f"prompt. Kept ids: {st['kept_ids']}.{note}",
             {**ti, "prompt": prompt + "\n\n---\n" + provenance + ctx + tail})
    except Exception as e:  # fail open, but say so
        rec.update(error=f"{type(e).__name__}: {e}"[:300], seconds=round(time.time() - t0, 2))
        log(rec)
        emit(f"context-filter FAILED ({rec['error']}); the subagent received only the prompt as written. "
             f"If it needs session context, send it a follow-up or re-delegate with the facts stated.")


if __name__ == "__main__":
    main()
