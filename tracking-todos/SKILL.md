---
name: tracking-todos
description: Maintain a structured task list for the current session. Use proactively when a request requires 3+ distinct steps, the user provides multiple items, or complex work benefits from explicit progress tracking. Storage persists via Muninn config across container death. Adapted from Claude Code's TodoWrite tool.
---

# Tracking Todos

Maintain a structured, persistent task list while working through multi-step requests. Track progress explicitly, mark completion honestly, and make the plan visible to Oskar.

## When to Use

Use proactively when:
- Request requires 3+ distinct steps or actions
- User provides multiple tasks (numbered, comma-separated, or a list)
- Work spans multiple tool calls, file edits, or research phases
- Non-trivial planning would otherwise happen implicitly in your head
- User explicitly asks for a todo list

Skip when:
- Single, straightforward task
- Purely conversational or informational exchange
- Task completes in <3 trivial steps
- Quick fact lookup or recall

When in doubt, use it. Being explicit about multi-step plans makes failure modes visible.

## Schema

Each todo has exactly three string fields:

- `content` — imperative form ("Run tests", "Fix auth bug")
- `status` — one of: `pending`, `in_progress`, `completed`
- `activeForm` — present continuous ("Running tests", "Fixing auth bug")

Both `content` and `activeForm` are required for every todo. The activeForm is what gets shown while a task is executing.

## API

```python
from todos import get_todos, write_todos, abandon, render

# Read current list
todos = get_todos()

# Replace entire list (Claude Code semantics — one call, whole list)
write_todos([
    {"content": "Fetch issue body", "status": "in_progress", "activeForm": "Fetching issue body"},
    {"content": "Draft fix plan", "status": "pending", "activeForm": "Drafting fix plan"},
    {"content": "Implement and test", "status": "pending", "activeForm": "Implementing and testing"},
])

# Display to Oskar
print(render())

# Discard remaining todos when starting fresh unrelated work
abandon()
```

`write_todos()` validates schema and that at most one item is `in_progress`. When every item is `completed`, it auto-clears the list (matches Claude Code behavior — done-state is empty-state).

## Behavioral Rules

**One in_progress at a time, strictly.** Before starting work on a task, set it to `in_progress`. Never have two `in_progress` items simultaneously. The validator enforces this.

**Mark complete IMMEDIATELY.** Update to `completed` the moment the work is actually done. Don't batch completions at the end — that defeats the tracking purpose and erases information about when things were finished.

**Only mark complete if FULLY done.** If tests fail, if the implementation is partial, if you hit an unresolved error — keep the task `in_progress` and add a new task describing the blocker. Lying about completion status is the failure mode this tool exists to prevent.

**Remove irrelevant tasks.** If a task becomes obsolete (scope change, wrong approach), remove it entirely from the list rather than marking it done. The list should reflect actual remaining work.

**Break complex tasks down.** Vague items like "implement the feature" defeat the point. Prefer specific actions: "Add validator to route handler", "Write 3 test cases for edge inputs", "Run existing test suite".

## Storage Model

Todos live in Muninn's config store under key `active-todos` (category=`ops`). This means:
- Survives container death within the same conversation
- Persists across conversations until explicitly cleared or auto-cleared when all done
- Cross-conversation persistence is a feature: unfinished work shows up next session as a nudge

If you start a conversation and find stale todos that don't apply, call `abandon()` to clear them.

## Known Limitations

**Single writer assumed.** The storage uses read-modify-write without locking. If a scheduled CCotw task and a live conversation both call `write_todos()` concurrently, the second write wins. Muninn runs single-threaded within a conversation, and scheduled tasks (perch, zeitgeist) don't use this skill, so the assumption holds in practice. Don't use this skill from concurrent agents without adding a lock.

**Global scope is intentional, not per-conversation.** Unfinished work leaks into the next conversation by design — it's a nudge that something was left open. If stale todos from prior work become noise, call `abandon()` to clear.

**Replace-whole-list API vs delta updates.** Matches Claude Code's TodoWrite exactly. The LLM failure mode (forgetting items when rewriting the full list) is mitigated by the prompt, not by the API shape. If omissions become a pattern, re-render the current list before composing the new one.

## Display Pattern

When the plan is substantive, show it to Oskar once after creating it, then rely on inline mentions rather than re-rendering the full list on every update. Noise defeats the signal.

```
▶ Fetching issue body
☐ Drafting fix plan
☐ Implementing and testing
```

## Examples

**Good use case — multi-file refactor:**
```python
write_todos([
    {"content": "Find all call sites of getCwd", "status": "in_progress", "activeForm": "Finding all call sites of getCwd"},
    {"content": "Rename occurrences in src/utils/", "status": "pending", "activeForm": "Renaming occurrences in src/utils/"},
    {"content": "Rename occurrences in src/agents/", "status": "pending", "activeForm": "Renaming occurrences in src/agents/"},
    {"content": "Run test suite", "status": "pending", "activeForm": "Running test suite"},
])
```

**Bad use case — should not use:**
```
User: "What's the current time in Tokyo?"
→ Single fact lookup. Skip todos.
```

**Mid-work update (after finishing step 1, hitting a blocker in step 2):**
```python
write_todos([
    {"content": "Find all call sites of getCwd", "status": "completed", "activeForm": "Finding all call sites of getCwd"},
    {"content": "Rename occurrences in src/utils/", "status": "completed", "activeForm": "Renaming occurrences in src/utils/"},
    {"content": "Resolve type error in AgentContext after rename", "status": "in_progress", "activeForm": "Resolving type error in AgentContext after rename"},
    {"content": "Rename occurrences in src/agents/", "status": "pending", "activeForm": "Renaming occurrences in src/agents/"},
    {"content": "Run test suite", "status": "pending", "activeForm": "Running test suite"},
])
```

Note: the blocker became a new task rather than marking step 3 complete.
