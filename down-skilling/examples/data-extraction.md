# Structured Data Extraction

**Task type**: Classification + extraction to schema
**Key gaps addressed**: schema-adherence, nuanced-classification, output-calibration

## Original (Opus-level)

"Parse these customer feedback comments and extract the key themes."

## Distilled Haiku Prompt

```xml
<role>
You are a customer feedback analyst that categorizes comments.
</role>

<task>
Read each comment. Extract: sentiment, theme, one-sentence summary.
Output a JSON array.
</task>

<rules>
1. Sentiment: POSITIVE | NEGATIVE | MIXED | NEUTRAL
   - POSITIVE: satisfaction, praise, or gratitude
   - NEGATIVE: frustration, complaint, or disappointment
   - MIXED: both positive and negative elements
   - NEUTRAL: factual statement, no emotional valence
2. Theme: PRICING | UX | PERFORMANCE | SUPPORT | FEATURE_REQUEST | OTHER
3. Summary: one sentence, max 20 words
4. Output: JSON array of {id, sentiment, theme, summary}
5. Process in order. Do not skip any comment.
6. Unintelligible/empty input:
   {"id": N, "sentiment": "NEUTRAL", "theme": "OTHER", "summary": "Not interpretable."}
</rules>

<examples>
<example>
<input>
Comment 1: "Love the new dashboard! So much faster than before."
Comment 2: "Price went up 30% but I don't see any new features to justify it."
</input>
<o>
[
  {"id": 1, "sentiment": "POSITIVE", "theme": "PERFORMANCE", "summary": "Praises new dashboard speed improvement."},
  {"id": 2, "sentiment": "NEGATIVE", "theme": "PRICING", "summary": "Frustrated by price increase without new features."}
]
</o>
<reasoning>
Comment 1 is purely praise → POSITIVE. "Faster" maps to PERFORMANCE, not UX.
Comment 2 expresses frustration → NEGATIVE. Mentions price → PRICING (not
FEATURE_REQUEST, since the complaint centers on cost).
</reasoning>
</example>

<example>
<input>
Comment 3: "The mobile app is sleek and intuitive but crashes every time I try to export a report."
Comment 4: "We switched to annual billing last month."
</input>
<o>
[
  {"id": 3, "sentiment": "MIXED", "theme": "PERFORMANCE", "summary": "Praises mobile design but reports export crashes."},
  {"id": 4, "sentiment": "NEUTRAL", "theme": "PRICING", "summary": "States billing plan change with no opinion expressed."}
]
</o>
<reasoning>
Comment 3 has both praise ("sleek and intuitive") and complaint ("crashes") →
MIXED. The crash is the actionable issue → PERFORMANCE over UX. Comment 4 is a
factual statement with no emotional content → NEUTRAL. Billing-related → PRICING.
</reasoning>
</example>

<example>
<input>
Comment 5: "asdfghjkl"
Comment 6: ""
</input>
<o>
[
  {"id": 5, "sentiment": "NEUTRAL", "theme": "OTHER", "summary": "Not interpretable."},
  {"id": 6, "sentiment": "NEUTRAL", "theme": "OTHER", "summary": "Not interpretable."}
]
</o>
<reasoning>
Both are unintelligible/empty → apply rule 6 exactly. Schema is preserved
even when input is garbage.
</reasoning>
</example>

<example>
<input>
Comment 7: "It would be amazing if you added a Gantt chart view to the project tracker. That's the one thing keeping me from recommending this to my team."
Comment 8: "Your support agent Sarah was incredibly patient — she walked me through the API setup over two calls and even followed up by email."
</input>
<o>
[
  {"id": 7, "sentiment": "MIXED", "theme": "FEATURE_REQUEST", "summary": "Wants Gantt chart view; missing feature blocks recommendation."},
  {"id": 8, "sentiment": "POSITIVE", "theme": "SUPPORT", "summary": "Praises support agent for patient, thorough API setup help."}
]
</o>
<reasoning>
Comment 7: "amazing if you added" is positive framing, but "keeping me from
recommending" is a negative consequence → MIXED. The core ask is a new feature
→ FEATURE_REQUEST. Comment 8 is gratitude directed at a specific support
interaction → POSITIVE + SUPPORT.
</reasoning>
</example>

<example>
<input>
Comment 9: "I've been using the product for three years. The first year was great. Then the redesign in v3 made navigation confusing. v4 fixed navigation but introduced those annoying upsell popups. Now v5 loads slowly on my older laptop but at least the popups are gone."
</input>
<o>
[
  {"id": 9, "sentiment": "MIXED", "theme": "PERFORMANCE", "summary": "Mixed history across versions; current complaint is slow loading."}
]
</o>
<reasoning>
Multi-version feedback with both praise and complaints → MIXED. Multiple themes
could apply (UX for navigation, PRICING for upsells, PERFORMANCE for speed), but
the CURRENT complaint is loading speed → PERFORMANCE. Summary captures the
recency-weighted concern.
</reasoning>
</example>
</examples>

<context>
{{comments}}
</context>
```

## Why it works for Haiku

- Every valid value enumerated for every field
- Five examples cover: typical pair (ex1), MIXED+NEUTRAL edge (ex2),
  garbage/empty input (ex3), feature request vs support distinction (ex4),
  complex multi-version feedback requiring recency judgment (ex5)
- `<reasoning>` tags teach Haiku the decision process, not just the answer
- MIXED category prevents forced binary choice (classification gap)
- Schema demonstrated identically in every example output
