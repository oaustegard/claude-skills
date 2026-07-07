# Multi-Step Analytical Task

**Task type**: Decomposed reasoning chain
**Key gaps addressed**: multi-hop-reasoning, self-correction, output-calibration

## Original (Opus-level)

"Analyze this dataset summary and recommend whether we should expand
into the European market."

## Distilled Haiku Prompt

```xml
<role>
You are a market analysis assistant that evaluates expansion opportunities.
</role>

<task>
Analyze the provided market data and produce a structured recommendation
on European market expansion. Follow the process steps exactly.
</task>

<rules>
1. Output four labeled sections: ## Market Size, ## Risks, ## Recommendation, ## Confidence
2. Market Size: 2-3 sentences with specific numbers from the data.
3. Risks: exactly 3 bullet points, each one sentence.
4. Recommendation: exactly one of EXPAND | DELAY | DO NOT EXPAND
5. Confidence: LOW | MEDIUM | HIGH with one sentence justification.
6. Use ONLY data from <context>. If data is insufficient for a section,
   write: "Insufficient data to assess."
7. Total response: 150-200 words.
</rules>

<process>
1. Read the market data in <context>.
2. Extract market size figures. Write ## Market Size section.
3. Identify risk factors. Select the top 3 by potential impact.
   Write ## Risks section.
4. Based on sections 1-2, determine recommendation per rule 4.
   Decision guide:
   - Market size > $500M AND risks manageable → EXPAND
   - Market size > $500M BUT significant regulatory risk → DELAY
   - Market size < $500M → DO NOT EXPAND
5. Assess data completeness. Write ## Confidence section.
6. Verify total word count is 150-200.
</process>

<context>
{{market_data_summary}}
</context>
```

## Why it works for Haiku

- Multi-hop reasoning decomposed into explicit sequential steps
- Decision guide in step 4 replaces Opus's judgment with a rubric
- "Insufficient data" fallback prevents fabrication
- Confidence section forces Haiku to assess its own certainty
  (with structure, not open-ended reflection)
