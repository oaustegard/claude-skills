# Schema Adherence Under Pressure

**Opus**: Maintains output format even with unusual or challenging
inputs. Degrades gracefully.

**Haiku**: Schema adherence is strong for typical inputs but can break
on edge cases — missing fields, malformed data, empty inputs.

**Mitigation**: Demonstrate edge cases in examples AND specify fallback.

```
If a required field is missing, output the field with value "N/A".
Never omit fields from the schema.
If input is empty, output the complete schema with all values "N/A".
```

Critical: include at least one edge-case example in the few-shot set.
Haiku generalizes from examples better than from rules alone for
format recovery.
