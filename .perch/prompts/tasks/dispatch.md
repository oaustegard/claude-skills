## Task: Dispatch (Route Decision)

You are deciding what task to run this session. The runner will execute your choice — you only need to decide.

### Steps

1. `recall(tags=["session-log", "perch-time"], n=5)` — check recent session history
2. Note when each task last ran and what it found
3. Check your boot context for incomplete tasks or pending items
4. Decide what's most needed right now

### Decision criteria

- **sleep**: Memory maintenance. Run if >24h since last sleep, or if prior sessions noted issues.
- **zeitgeist**: News awareness. Run if >24h since last scan, or if something notable is happening.
- **fly**: Autonomous exploration. Run when maintenance and awareness are current.

If nothing is pressing, default to **sleep**.

### Output format

After gathering context, end with your decision as JSON on its own line:

```json
{"task": "sleep", "reason": "Last sleep was 2 days ago, zeitgeist ran this morning"}
```

The runner will parse this and execute the chosen task with its own turn budget. Do not attempt to execute the task yourself.
