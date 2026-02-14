# Conditional and Branching Logic

**Opus**: Handles nested if/then/else reliably. Evaluates compound
conditions. Follows complex decision trees.

**Haiku**: Reliable with simple if/then. Degrades with:
- Nested conditions (if A then if B then...)
- Compound conditions (if A AND B OR C)
- More than 3 branches

**Mitigation**: Flatten decision trees. One condition per step.

```
BAD (nested):
If the customer is premium AND the order is > $100 AND it's their
first return, waive the fee. Otherwise if they're premium but the
order is < $100, charge half fee. Otherwise charge full fee.

GOOD (flattened):
Step 1: Is customer premium? YES → go to Step 2. NO → charge full fee.
Step 2: Is order > $100? YES → go to Step 3. NO → charge half fee.
Step 3: Is this their first return? YES → waive fee. NO → charge half fee.
```

For complex branching, use a decision table:
```
| Premium? | Order > $100? | First return? | Action      |
|----------|---------------|---------------|-------------|
| YES      | YES           | YES           | Waive fee   |
| YES      | YES           | NO            | Half fee    |
| YES      | NO            | any           | Half fee    |
| NO       | any           | any           | Full fee    |

Find the first matching row. Apply that action.
```

Decision tables eliminate reasoning — Haiku just pattern-matches.
