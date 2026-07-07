# Semi-Formal Checkpoints (Sonnet/Opus)

You already reason well about code. These checkpoints catch the specific failure modes where even strong reasoning misses bugs — name shadowing, scope ambiguity, and insufficiency errors.

## Before Any Conclusion

Insert these three checks before delivering a verdict on any code analysis task. Don't template your entire response around them — just verify each one is addressed.

### 1. Function Resolution
For each function or method call in the code under analysis: which definition is actually invoked? Check for name shadowing between local scope, module scope, imports, and builtins. If you can't trace a call to its exact definition, flag it.

### 2. Sufficiency
For fault localization: "Would fixing ONLY this line fix the symptom?" If no, you've found a contributor, not the root cause.
For patch verification: "Does this change fully address the stated problem, or does it fix a symptom while the root cause persists?"

### 3. Regression Paths
For each code path touched by the change: does untouched code that depends on the modified behavior still work? Trace at least one downstream caller.

## Verdict Format

End with exactly:
```
VERDICT: [CORRECT | LIKELY_CORRECT | CONCERNS | BUGGY]
CONFIDENCE: [high | medium | low]
SUMMARY: [one sentence]
```

## When to Expand

If checkpoint 1 reveals actual name shadowing or ambiguous resolution, switch to a full execution trace for the affected paths. The compact format is for verification, not for working through genuinely tangled scope chains.
