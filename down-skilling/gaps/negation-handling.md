# Negation and Negative Instructions

**Opus**: Processes negative instructions ("don't include X") reliably.
Understands complex negations and double negatives.

**Haiku**: Negative instructions are less reliably followed than positive
ones. "Don't use bullet points" may still produce bullets. Complex
negations ("never fail to include") can be misinterpreted.

**Mitigation**: Reframe every negative as a positive directive.

```
BAD:  Don't use jargon.
GOOD: Use plain language that a high school student would understand.

BAD:  Never include personal opinions.
GOOD: State only facts supported by the provided data.

BAD:  Don't forget to include the date.
GOOD: Include the date in YYYY-MM-DD format on the first line.
```

When a negative constraint is unavoidable, pair it with the positive
alternative:
```
Do not use bullet points. Instead, write in flowing prose paragraphs.
```

For critical prohibitions, combine rule + example:
```
Rule: Do not include prices.
Example output shows: "Contact sales for pricing." (not "$99/month")
```
