# Summarization Fidelity

**Opus**: Produces summaries that accurately reflect source material.
Naturally distinguishes between main claims and supporting detail.
Maintains appropriate level of abstraction.

**Haiku**: Summaries may:
- Overweight content from the beginning/end of the source (position bias)
- Lose nuance (turn hedged claims into definitive statements)
- Miss the central thesis while including peripheral details
- Add interpretive framing not present in the source

**Mitigation**: Constrain the summarization process.

```
Step 1: Identify the single main claim or thesis of the text.
        Write it in one sentence.
Step 2: Identify 3 supporting points. Write each in one sentence.
Step 3: Combine into a coherent paragraph of 60-80 words.

Rules:
- The main claim MUST appear in the first sentence of your summary.
- Do not add interpretation or analysis.
- Do not introduce information not in the source.
- If the source hedges a claim ("may", "suggests", "could"),
  preserve the hedging in your summary.
```

For longer documents, fight position bias:
```
Divide the text into thirds (beginning, middle, end).
Extract one key point from each third.
Your summary must include content from all three sections.
```
