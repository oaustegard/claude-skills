# Counting and Enumeration

**Opus**: Counts items accurately. Generates exactly N items when asked.
Tracks quantities across sections.

**Haiku**: May produce N-1 or N+1 items when asked for exactly N.
Counting errors increase with N > 5. May lose count in longer outputs.

**Mitigation**: Structure output so counting is mechanical, not cognitive.

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
