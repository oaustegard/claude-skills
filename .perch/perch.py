#!/usr/bin/env python3
"""Perch time: scheduled autonomous agency via Anthropic Messages API.

Tool-use loop that gives Muninn scheduled compute windows for memory
maintenance, news awareness, and autonomous exploration.

Usage:
    python .perch/perch.py --task sleep --model claude-haiku-4-5-20251001
    python .perch/perch.py --task zeitgeist --verbose
    python .perch/perch.py --task fly --model claude-sonnet-4-5-20250929
    python .perch/perch.py --task dispatch  # decides, then routes
"""

import argparse
import json
import os
import re
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

# -- Per-task turn budgets --
# These are defaults; --max-turns CLI arg overrides if lower.
# Each turn is ~30s of LLM inference, so 20 turns ≈ 10 min.

TURN_BUDGETS = {
    "sleep": 25,
    "zeitgeist": 15,
    "fly": 15,
    "dispatch": 5,  # decision phase only — routes to real task
}

ROUTABLE_TASKS = ("sleep", "zeitgeist", "fly")
HOMEWORK_TASK = "homework"  # pseudo-task: execute inline during dispatch

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
    routed_from: str = None, routed_task: str = None,
) -> dict:
    """Build the session.json record."""
    ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Estimate cost (Haiku: $0.80/$4 per MTok, Sonnet: $3/$15 per MTok)
    if "haiku" in model:
        cost = (total_input_tokens * 0.80 + total_output_tokens * 4.0) / 1_000_000
    else:
        cost = (total_input_tokens * 3.0 + total_output_tokens * 15.0) / 1_000_000

    record = {
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
    if routed_from:
        record["routed_from"] = routed_from
    if routed_task:
        record["routed_task"] = routed_task
    return record


# -- Session log memory --

def store_session_log(task: str, model: str, turns: int, tool_calls: list,
                      cost: float, summary: str, errors: list,
                      routed_task: str = None) -> None:
    """Store a session log memory for cross-session continuity."""
    try:
        from remembering.scripts import remember as mem_remember
        date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tool_summary = {}
        for tc in tool_calls:
            name = tc.get("name", "unknown")
            tool_summary[name] = tool_summary.get(name, 0) + 1
        tool_str = ", ".join(f"{k}={v}" for k, v in sorted(tool_summary.items()))

        route_note = f"\nRouted to: {routed_task}" if routed_task else ""
        mem_remember(
            f"PERCH SESSION LOG -- {task} ({date_tag})\n"
            f"Model: {model} | Turns: {turns} | Cost: ${cost:.3f}\n"
            f"Tool calls: {tool_str}{route_note}\n"
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

def run_loop(client: anthropic.Anthropic, model: str, system_prompt: str,
             tools: list, initial_message: str, max_turns: int) -> dict:
    """Run the tool-use loop. Returns aggregated stats.

    This is the inner loop, separated from session management so dispatch
    can chain two loops (decide → execute) within one session.
    """
    messages = [{"role": "user", "content": initial_message}]
    log(f"PROMPT: {initial_message[:80]}")

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
            log(f"LOOP END: {turn} turns, {len(all_tool_calls)} tool calls", always=True)
            break

        # Execute tools and build results
        tool_results = []
        for tu in tool_uses:
            t0 = time.monotonic()
            result_text = execute_tool(tu.name, tu.input)
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            log(f"TOOL_RESULT: {tu.name} -> {len(result_text)} chars ({elapsed_ms}ms)")

            all_tool_calls.append({
                "name": tu.name,
                "input": tu.input,
                "output_chars": len(result_text),
                "elapsed_ms": elapsed_ms,
            })

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

    return {
        "turns": turn,
        "tool_calls": all_tool_calls,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "errors": errors,
        "summary": final_summary,
    }


def _parse_dispatch_decision(summary: str) -> str | None:
    """Extract task choice from dispatch LLM output.

    Looks for JSON like {"task": "sleep"} or plain mentions of task names.
    Returns task name (including "homework") or None if unparseable.
    """
    valid_tasks = ROUTABLE_TASKS + (HOMEWORK_TASK,)

    # Try JSON extraction first
    json_match = re.search(r'\{[^}]*"task"\s*:\s*"(\w+)"[^}]*\}', summary)
    if json_match:
        task = json_match.group(1)
        if task in valid_tasks:
            return task

    # Fallback: look for task names in the text
    text_lower = summary.lower()
    for task in valid_tasks:
        if re.search(rf'\b{task}\b', text_lower):
            return task

    return None


def run_perch(task: str, model: str, max_turns: int) -> dict:
    """Run a perch session. Dispatch routes to a concrete task."""
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Build system prompt: boot() output (dynamic identity)
    try:
        from remembering.scripts.boot import boot
        boot_output = boot(mode="perch")
        log(f"boot(mode='perch') loaded ({len(boot_output)} chars)", always=True)
    except Exception as e:
        log(f"WARNING: boot() failed ({e}), falling back to static identity.md", always=True)
        boot_output = load_prompt("identity")

    # Validate API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        log("FATAL: ANTHROPIC_API_KEY is not set or empty.", always=True)
        return build_session_record(
            task=task, model=model, turns=0, tool_calls=[],
            total_input_tokens=0, total_output_tokens=0,
            errors=["ANTHROPIC_API_KEY not set"], summary="",
            started_at=started_at,
        )

    client = anthropic.Anthropic(api_key=api_key)
    tools = get_tool_definitions(task)

    # Effective turn budget: min of per-task default and CLI override
    budget = min(max_turns, TURN_BUDGETS.get(task, max_turns))

    if task == "dispatch":
        return _run_dispatch(client, model, boot_output, tools, budget, max_turns, started_at)

    # Direct task execution
    system_prompt = boot_output + "\n\n" + load_prompt(f"tasks/{task}")
    log(f"TASK: {task} model={model} budget={budget} tools={len(tools)}", always=True)

    result = run_loop(client, model, system_prompt, tools,
                      f"Begin {task} session.", budget)

    record = build_session_record(
        task=task, model=model, turns=result["turns"],
        tool_calls=result["tool_calls"],
        total_input_tokens=result["input_tokens"],
        total_output_tokens=result["output_tokens"],
        errors=result["errors"], summary=result["summary"][:500],
        started_at=started_at,
    )

    cost = record["estimated_cost_usd"]
    log(f"SUMMARY: {result['turns']} turns, {len(result['tool_calls'])} tool calls, "
        f"{result['input_tokens']}+{result['output_tokens']} tokens, ${cost:.4f}",
        always=True)

    store_session_log(task, model, result["turns"], result["tool_calls"],
                      cost, result["summary"][:300], result["errors"])
    return record


def _run_dispatch(client, model, boot_output, tools, decision_budget,
                  max_turns, started_at) -> dict:
    """Two-phase dispatch: decide what to do, then do it.

    If the decision phase chooses "homework", the homework is executed
    inline during the decision loop (no phase 2 routing). The dispatch
    prompt instructs the LLM to carry out homework using available tools
    and then emit the decision JSON at the end.

    For homework, we give the decision phase a larger turn budget so the
    LLM has room to both decide and execute.
    """

    # Phase 1: Decision (with expanded budget for homework)
    homework_budget = min(max_turns, TURN_BUDGETS.get("sleep", 25))  # generous
    dispatch_prompt = boot_output + "\n\n" + load_prompt("tasks/dispatch")
    log(f"DISPATCH PHASE 1: deciding (budget={homework_budget})", always=True)

    decision_result = run_loop(
        client, model, dispatch_prompt, tools,
        "Begin dispatch session.", homework_budget,
    )

    # Parse the decision
    chosen_task = _parse_dispatch_decision(decision_result["summary"])

    if not chosen_task:
        log(f"DISPATCH: Could not parse task from: {decision_result['summary'][:200]}", always=True)
        chosen_task = "sleep"
        log(f"DISPATCH: Defaulting to {chosen_task}", always=True)

    # Homework is executed inline during the decision loop — no phase 2
    if chosen_task == HOMEWORK_TASK:
        log(f"DISPATCH: homework executed inline ({decision_result['turns']} turns)", always=True)

        record = build_session_record(
            task="dispatch", model=model, turns=decision_result["turns"],
            tool_calls=decision_result["tool_calls"],
            total_input_tokens=decision_result["input_tokens"],
            total_output_tokens=decision_result["output_tokens"],
            errors=decision_result["errors"],
            summary=decision_result["summary"][:500],
            started_at=started_at,
            routed_from="dispatch", routed_task="homework",
        )

        cost = record["estimated_cost_usd"]
        log(f"DISPATCH COMPLETE: homework in {decision_result['turns']} turns, "
            f"${cost:.4f}", always=True)

        store_session_log("dispatch", model, decision_result["turns"],
                          decision_result["tool_calls"], cost,
                          decision_result["summary"][:300],
                          decision_result["errors"], routed_task="homework")
        return record

    log(f"DISPATCH PHASE 2: routing to {chosen_task}", always=True)

    # Phase 2: Execute chosen task with its own budget
    task_budget = min(max_turns, TURN_BUDGETS.get(chosen_task, 20))
    task_prompt = boot_output + "\n\n" + load_prompt(f"tasks/{chosen_task}")
    task_tools = get_tool_definitions(chosen_task)

    log(f"TASK: {chosen_task} budget={task_budget} tools={len(task_tools)}", always=True)

    task_result = run_loop(
        client, model, task_prompt, task_tools,
        f"Begin {chosen_task} session.", task_budget,
    )

    # Merge stats from both phases
    total_turns = decision_result["turns"] + task_result["turns"]
    total_tool_calls = decision_result["tool_calls"] + task_result["tool_calls"]
    total_input = decision_result["input_tokens"] + task_result["input_tokens"]
    total_output = decision_result["output_tokens"] + task_result["output_tokens"]
    all_errors = decision_result["errors"] + task_result["errors"]

    record = build_session_record(
        task="dispatch", model=model, turns=total_turns,
        tool_calls=total_tool_calls,
        total_input_tokens=total_input, total_output_tokens=total_output,
        errors=all_errors, summary=task_result["summary"][:500],
        started_at=started_at,
        routed_from="dispatch", routed_task=chosen_task,
    )

    cost = record["estimated_cost_usd"]
    log(f"DISPATCH COMPLETE: {chosen_task} in {total_turns} turns "
        f"({decision_result['turns']}+{task_result['turns']}), "
        f"${cost:.4f}", always=True)

    store_session_log("dispatch", model, total_turns, total_tool_calls,
                      cost, task_result["summary"][:300], all_errors,
                      routed_task=chosen_task)
    return record


# -- Entry point --

def main():
    parser = argparse.ArgumentParser(description="Perch time: scheduled autonomous agency")
    parser.add_argument("--task", required=True, choices=["dispatch", "sleep", "zeitgeist", "fly"],
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

        # Exit with error code only for structural failures (no API key, boot crash).
        # Tool-level errors are normal operational noise — log them but don't fail.
        structural_errors = [e for e in record["errors"]
                             if "ANTHROPIC_API_KEY" in e
                             or "API error on turn 1:" in e]
        if structural_errors:
            sys.exit(1)
    finally:
        if _log_file:
            _log_file.close()


if __name__ == "__main__":
    main()
