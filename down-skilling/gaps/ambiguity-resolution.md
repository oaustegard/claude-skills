# Ambiguity Resolution

**Opus**: Selects the most contextually appropriate interpretation of
ambiguous input. Weighs multiple factors silently.

**Haiku**: May pick any valid interpretation, often the most literal one.
Inconsistent across runs.

**Mitigation**: Provide explicit disambiguation rules.

```
If the input could mean X or Y, default to X unless the input
explicitly contains [specific signal for Y].
```

Always enumerate interpretations and assign a default. Haiku will not
weigh contextual clues to choose — it needs a decision rule.
