# Nuanced Classification

**Opus**: Handles borderline cases with appropriate hedging or
multi-label assignment. Understands that categories can overlap.

**Haiku**: Tends toward single-label, definitive classification. May
force ambiguous cases into the nearest category.

**Mitigation**: Provide a decision rubric with explicit boundary rules.

```
Categories: [A, B, C, AMBIGUOUS]
If input matches criteria for exactly one category, assign it.
If input matches 2+ categories, assign "AMBIGUOUS" and list them.
If input matches no category, assign "OTHER".
```

Always include an escape-hatch category (AMBIGUOUS, OTHER, MIXED).
Without it, Haiku will force borderline cases into arbitrary buckets.
