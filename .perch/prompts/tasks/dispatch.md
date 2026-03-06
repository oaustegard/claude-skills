## Task: Dispatch (Route Decision)

You are deciding what task to run this session. The runner will execute your choice — you only need to decide.

### Steps

1. `recall(tags=["perch-homework", "pending"], tag_mode="all", n=5)` — check for queued homework from Muninn
2. `recall(tags=["session-log", "perch-time"], n=5)` — check recent session history
3. Note when each task last ran and what it found
4. Check your boot context for incomplete tasks or pending items
5. Decide what's most needed right now

### Homework override

If step 1 returns pending homework, **execute the homework instructions** instead of routing to a standard task. Homework memories contain specific instructions from Muninn (the planning wing) for work to do during perch time.

After completing homework, mark it done: `supersede(homework_id, "Completed: [brief summary]", "experience", tags=["perch-homework", "completed"])`

When homework is present, output your decision as:

```json
{"task": "homework", "homework_id": "mem_xxx", "reason": "Pending homework: [description]"}
```

The runner does not have a "homework" task type — this signals you to execute the homework within the dispatch turn budget. Use your available tools to carry out the instructions.

### Standard decision criteria (when no homework)

- **sleep**: Memory maintenance. Run if >24h since last sleep, or if prior sessions noted issues.
- **zeitgeist**: News awareness. Run if >24h since last scan, or if something notable is happening.
- **fly**: Autonomous exploration. Run when maintenance and awareness are current.

If nothing is pressing, default to **sleep**.

### Output format

After gathering context, end with your decision as JSON on its own line:

```json
{"task": "sleep", "reason": "Last sleep was 2 days ago, zeitgeist ran this morning"}
```

The runner will parse this and execute the chosen task with its own turn budget. Do not attempt to execute the task yourself (unless homework — see above).
