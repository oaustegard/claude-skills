# Parallel Structure and Consistency

**Opus**: Maintains consistent style, format, and level of detail
across multiple similar outputs within a single response.

**Haiku**: First few items in a list are well-formed. Quality and
consistency degrade after item 4-5. Later items may be shorter,
less detailed, or structurally different from earlier ones.

**Mitigation**: Provide a template and enforce it per-item.

```
For each item, output EXACTLY this structure:
**Name**: [name]
**Category**: [one of: A, B, C]
**Summary**: [one sentence, 10-20 words]
**Score**: [integer 1-10]

Do not vary this structure between items.
```

For long lists (>5 items), consider:
- Processing in batches of 5
- Including a "format checkpoint" instruction:
  "After every 5th item, verify your format matches the template."
- Using JSON arrays (structural enforcement is stronger than prose)

If generating comparative content (pros/cons for multiple options),
provide the comparison scaffold:
```
| Criterion | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| Cost      | ...      | ...      | ...      |
| Speed     | ...      | ...      | ...      |
```
Tables enforce parallel structure mechanically.
