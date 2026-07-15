# Multi-Hop Reasoning

**Opus**: Chains 5+ reasoning steps naturally. Maintains coherence
across long inference chains.

**Haiku**: Split by hop type. **Explicit chains** — where each hop is a
stated lookup or state update — measured far stronger than model-card
priors: calibration (2026-07-15, Haiku 4.5) scored 100% on 30-hop
function iteration, 25-operation box/state tracking, and 16-leaf nested
arithmetic, even at low effort and in one control with written
chain-of-thought suppressed. The 2-3-hop caution applies to **latent
inference chains** — hops the model must construct itself from implicit
relationships (cause→effect→consequence, unstated intermediate
conclusions), which remain unmeasured and should be treated per the
original prior.

**Mitigation** (for latent chains): Decompose into sequential sub-tasks
with explicit outputs — this converts a latent chain into the explicit
kind Haiku is measured-good at.

```
Step 1: Extract [A] from the input.
Step 2: Using [A], determine [B] by [specific method].
Step 3: Given [B], select [C] from [enumerated options].
```

Or bound reasoning depth: "Think in exactly 3 steps, writing each step
before the next."

Never rely on Haiku to chain more than 3 *latent* inferences silently.
If the task requires 4+ such hops, split into separate prompts or make
intermediate results explicit in the process steps. Explicitly-stated
chains (lookups, state updates) need no such split — measured reliable
to 30 hops.
