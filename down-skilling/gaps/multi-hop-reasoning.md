# Multi-Hop Reasoning

**Opus**: Chains 5+ reasoning steps naturally. Maintains coherence
across long inference chains.

**Haiku**: Reliable for 2-3 hops. Degrades at 4+. May skip intermediate
steps or reach incorrect conclusions.

**Mitigation**: Decompose into sequential sub-tasks with explicit outputs.

```
Step 1: Extract [A] from the input.
Step 2: Using [A], determine [B] by [specific method].
Step 3: Given [B], select [C] from [enumerated options].
```

Or bound reasoning depth: "Think in exactly 3 steps, writing each step
before the next."

Never rely on Haiku to chain more than 3 inferences silently. If the
task requires 4+ hops, split into separate prompts or make intermediate
results explicit in the process steps.
