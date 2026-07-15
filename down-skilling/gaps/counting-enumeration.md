# Counting and Enumeration

**Opus**: Counts items accurately. Generates exactly N items when asked.
Tracks quantities across sections.

**Haiku**: Stronger than model-card priors suggested. Calibration
(2026-07-15, Haiku 4.5): exact-word-count sentence generation hit the
target 13/13 times at N = 10–14 — under up to four *additional*
simultaneous constraints — while Sonnet at low effort missed twice on
the same battery. The decisive factor was **definitional precision**:
each prompt stated the counting rule explicitly ("a word = any run of
letters or apostrophes"). Residual risk concentrates in large N (>15,
unmeasured), counting inside long free-form outputs, and prompts that
leave the unit of counting ambiguous.

**Mitigation**: Define the unit of counting exactly, in the prompt.
Then, for larger N or count-inside-long-output tasks, structure output
so counting is mechanical, not cognitive — and prefer a deterministic
post-hoc checker (word counts are free to verify) over prompt
scaffolding alone.

For "generate exactly 5 items":
```
Output format:
1. [item]
2. [item]
3. [item]
4. [item]
5. [item]

Number each item. After writing item 5, stop. Do not continue.
```

For verification tasks ("how many X in the input"):
```
Step 1: List each X found, one per line.
Step 2: Count the lines from Step 1.
Step 3: Report the count.
```

Avoid asking Haiku to count-and-generate simultaneously. Decompose:
first decide WHAT, then ensure the right NUMBER.

For large N (>10), provide the numbered scaffold in the prompt itself
and have Haiku fill it in.
