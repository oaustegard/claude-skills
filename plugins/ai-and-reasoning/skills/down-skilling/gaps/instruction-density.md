# Instruction Density and Rule Dropping

**Opus**: Tracks and satisfies 15+ simultaneous constraints reliably.
Prioritizes naturally when constraints tension.

**Haiku**: Reliable with 5-7 simultaneous constraints. At 10+,
may drop rules — particularly those in the middle of a list, those
phrased passively, or those that conflict with example patterns.

**Mitigation**: Limit rules to 7. Group and prioritize.

```
BAD: 12 flat rules in a single list

GOOD: 
CRITICAL (must never violate):
1. [rule]
2. [rule]

REQUIRED (always apply):
3. [rule]
4. [rule]
5. [rule]

PREFERRED (apply when possible):
6. [rule]
7. [rule]
```

Additional strategies:
- Cross-reference rules in process steps: "Apply rules 1-3 to each item"
- Embed the most important rules in the examples, not just the rule list
- For complex rule sets, split into multiple prompts (one pass per
  rule group) rather than asking Haiku to apply all at once
- Repeat the single most important rule at the END of the prompt

If a rule is never demonstrated in the examples, Haiku is less likely
to follow it. Every critical rule should appear in at least one example.
