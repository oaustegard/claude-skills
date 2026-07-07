# Context Window Utilization

**Opus**: Attends well to information regardless of position in long
context. Can synthesize across distant sections.

**Haiku**: Strong primacy and recency bias. Information in the middle
of long contexts may be underweighted.

**Mitigation**: Position-aware prompt design.

- Place critical instructions at the START and END of the prompt
- Keep context passages short and clearly labeled
- Repeat key constraints AFTER the context block
- For long documents, extract relevant snippets rather than full text
- Use explicit section labels: [Context], [Policy], [Instructions]

Rule of thumb: if the prompt exceeds 2,000 tokens, repeat the most
important constraint immediately before the output instruction.
