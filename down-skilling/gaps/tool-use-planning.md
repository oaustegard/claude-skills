# Tool Use Planning

**Opus**: Plans tool call sequences strategically. Assesses information
needs before acting. Batches efficiently.

**Haiku**: May call tools eagerly without planning. Can make redundant
calls or miss dependencies between calls.

**Mitigation**: Provide an explicit tool-use plan.

```
Before calling any tool:
1. List what information you need.
2. Identify which tool provides each piece.
3. Determine the correct call order (dependencies first).
4. Execute in that order.
Do NOT call a tool until you have completed steps 1-3.
```

For multi-tool tasks, enumerate the exact sequence in the process
section rather than letting Haiku decide the order.
