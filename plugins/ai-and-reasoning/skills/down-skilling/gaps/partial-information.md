# Handling Partial or Missing Information

**Opus**: Recognizes when input is incomplete. Gracefully distinguishes
between "not mentioned" and "doesn't exist." Asks for clarification
or flags gaps appropriately.

**Haiku**: Tends to either fabricate missing information or silently
skip it. May not distinguish between "unknown" and "not applicable."

**Mitigation**: Define explicit handling for every expected gap.

```
REQUIRED fields: name, email, date
OPTIONAL fields: phone, notes

For REQUIRED fields:
- If missing, output the field with value "MISSING — [field name] required"
- Do not skip the field. Do not guess.

For OPTIONAL fields:
- If missing, output the field with value "N/A"
- Do not skip the field.
```

When input quality varies:
```
If the input text is:
- Empty → output: {"status": "error", "message": "No input provided."}
- Under 10 words → output: {"status": "warning", "message": "Input too short for reliable analysis."}
- Otherwise → proceed with analysis.
```

Always provide the full output schema even for error/edge cases.
Haiku follows "fill in this template" more reliably than "decide
what to output based on input quality."
