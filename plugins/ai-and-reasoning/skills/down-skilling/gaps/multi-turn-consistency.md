# Multi-Turn Consistency

**Opus**: Maintains context, commitments, and style across long
conversations. Self-consistent even when revisiting earlier topics.

**Haiku**: Context retention degrades over turns. May:
- Contradict earlier statements
- Lose track of established facts or agreements
- Reset persona or tone mid-conversation
- Forget constraints established in early turns

**Mitigation**: Re-inject critical state at each turn.

For API-based multi-turn:
```
<state>
Established facts:
- User's name: Alice
- Project: Q4 dashboard redesign
- Constraint: Budget is $50K
- Previous decisions: Chose React over Vue (turn 3)

Active rules:
- Respond in 2-3 sentences per turn
- Do not suggest solutions over budget
</state>

[New user message here]
```

For single-prompt tasks that simulate multi-turn reasoning:
- Do not rely on Haiku maintaining context beyond 3-4 exchanges
- Build each step's output as input to the next step explicitly
- For chatbot applications, implement a state summary that gets
  prepended to each turn

For persona consistency: re-state the role in the system prompt
AND reference it in the first user turn.
