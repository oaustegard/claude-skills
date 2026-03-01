#!/usr/bin/env python3
"""Perch time: scheduled autonomous agency via Anthropic Messages API.

Tool-use loop that gives Muninn scheduled compute windows for memory
maintenance, news awareness, and autonomous exploration.

Usage:
    python .perch/perch.py --task sleep --model claude-haiku-4-5-20251001
    python .perch/perch.py --task zeitgeist --verbose
    python .perch/perch.py --task fly --model claude-sonnet-4-5-20250929
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# Ensure repo root is on sys.path for sibling imports
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import get_tool_definitions, execute_tool

# -- Logging --

_start_time = time.monotonic()
_verbose = False
_log_file = None


def _elapsed() -> str:
    """Return elapsed time since start as MM:SS.s."""
    t = time.monotonic() - _start_time
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


def log(msg: str, *, always: bool = False) -> None:
    """Log a message with timestamp. Writes to stderr and log file."""
    line = f"[{_elapsed()}] {msg}"
    if _verbose or always:
        print(line, file=sys.stderr)
    if _log_file:
        _log_file.write(line + "\n")
        _log_file.flush()


# -- Prompt loading --

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt file by path relative to prompts/."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text().strip()


# -- Session record --

def build_session_record(
    task: str, model: str, turns: int, tool_calls: list,
    total_input_tokens: int, total_output_tokens: int,
    errors: list, summary: str, started_at: str,
) -> dict:
    """Build the session.json record."""
    ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Estimate cost (Haiku: $0.80/$4 per MTok, Sonnet: $3/$15 per MTok)
    if "haiku" in model:
        cost = (total_input_tokens * 0.80 + total_output_tokens * 4.0) / 1_000_000
    else:
        cost = (total_input_tokens * 3.0 + total_output_tokens * 15.0) / 1_000_000

    return {
        "task": task,
        "model": model,
        "started_at": started_at,
        "ended_at": ended_at,
        "turns": turns,
        "tool_calls": tool_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "estimated_cost_usd": round(cost, 4),
        "errors": errors,
        "summary": summary,
    }


# -- Session log memory --

def store_session_log(task: str, model: str, turns: int, tool_calls: list,
                      cost: float, summary: str, errors: list) -> None:
    """Store a session log memory for cross-session continuity."""
    try:
        from remembering.scripts import remember as mem_remember
        date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tool_summary = {}
        for tc in tool_calls:
            name = tc.get("name", "unknown")
            tool_summary[name] = tool_summary.get(name, 0) + 1
        tool_str = ", ".join(f"{k}={v}" for k, v in sorted(tool_summary.items()))

        mem_remember(
            f"PERCH SESSION LOG -- {task} ({date_tag})\n"
            f"Model: {model} | Turns: {turns} | Cost: ${cost:.3f}\n"
            f"Tool calls: {tool_str}\n"
            f"Outcome: {summary}\n"
            f"Errors: {', '.join(errors) if errors else 'none'}",
            "experience",
            tags=["perch-time", "session-log", task, date_tag],
            priority=0,
        )
        log("Session log stored in memory.", always=True)
    except Exception as e:
        log(f"WARNING: Failed to store session log: {e}", always=True)


# -- Core loop --

def run_perch(task: str, model: str, max_turns: int) -> dict:
    """Run a perch session with the tool-use loop."""
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Load prompts
    system_prompt = load_prompt("identity") + "\n\n" + load_prompt(f"tasks/{task}")
    tools = get_tool_definitions(task)

    log(f"SYSTEM: task={task} model={model} max_turns={max_turns} tools={len(tools)}", always=True)

    # Initialize Anthropic client
    client = anthropic.Anthropic()

    messages = [{"role": "user", "content": f"Begin {task} session."}]
    log(f"PROMPT: Begin {task} session.")

    total_input_tokens = 0
    total_output_tokens = 0
    all_tool_calls = []
    errors = []
    final_summary = ""
    turn = 0

    while turn < max_turns:
        turn += 1

        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
        except anthropic.APIError as e:
            error_msg = f"API error on turn {turn}: {e}"
            log(error_msg, always=True)
            errors.append(error_msg)
            break

        # Track token usage
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Process response content
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_uses = []
        for block in assistant_content:
            if block.type == "text":
                log(f"ASSISTANT: [text] {block.text[:100]}... ({len(block.text)} chars)")
                final_summary = block.text  # Last text block is the summary
            elif block.type == "tool_use":
                log(f"ASSISTANT: [tool_use] {block.name} {json.dumps(block.input)[:100]}")
                tool_uses.append(block)

        # If no tool calls, the session is done
        if not tool_uses:
            log(f"SESSION END: {turn} turns, {len(all_tool_calls)} tool calls", always=True)
            break

        # Execute tools and build results
        tool_results = []
        for tu in tool_uses:
            t0 = time.monotonic()
            result_text = execute_tool(tu.name, tu.input)
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            log(f"TOOL_RESULT: {tu.name} -> {len(result_text)} chars ({elapsed_ms}ms)")

            # Track for session record
            all_tool_calls.append({
                "name": tu.name,
                "input": tu.input,
                "output_chars": len(result_text),
                "elapsed_ms": elapsed_ms,
            })

            # Check for tool errors
            if result_text.startswith(f"Tool {tu.name} failed:"):
                errors.append(result_text)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})
    else:
        log(f"MAX TURNS REACHED ({max_turns})", always=True)
        errors.append(f"Max turns reached ({max_turns})")

    # Build session record
    record = build_session_record(
        task=task, model=model, turns=turn, tool_calls=all_tool_calls,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        errors=errors, summary=final_summary[:500], started_at=started_at,
    )

    cost = record["estimated_cost_usd"]
    log(
        f"SUMMARY: {turn} turns, {len(all_tool_calls)} tool calls, "
        f"{total_input_tokens}+{total_output_tokens} tokens, ${cost:.4f}",
        always=True,
    )

    # Store session log in memory
    store_session_log(task, model, turn, all_tool_calls, cost, final_summary[:300], errors)

    return record


# -- Entry point --

def main():
    parser = argparse.ArgumentParser(description="Perch time: scheduled autonomous agency")
    parser.add_argument("--task", required=True, choices=["sleep", "zeitgeist", "fly"],
                        help="Task to run")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001",
                        help="Anthropic model ID")
    parser.add_argument("--max-turns", type=int, default=50,
                        help="Max tool-call turns (safety ceiling)")
    parser.add_argument("--verbose", action="store_true", default=True,
                        help="Verbose logging (default: on)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose logging")
    args = parser.parse_args()

    global _verbose, _log_file
    _verbose = not args.quiet

    # Open log file
    _log_file = open("session.log", "w")

    try:
        record = run_perch(args.task, args.model, args.max_turns)

        # Write session.json
        with open("session.json", "w") as f:
            json.dump(record, f, indent=2)

        log(f"Session record written to session.json", always=True)

        # Exit with error code if there were errors
        if record["errors"]:
            sys.exit(1)
    finally:
        if _log_file:
            _log_file.close()


if __name__ == "__main__":
    main()
