# Self-Correction and Verification

**Opus**: Naturally reviews its output and catches errors. Effective
when prompted to critique and revise.

**Haiku**: Rarely self-corrects unprompted. When prompted to review,
corrections are shallow (surface-level, not logical).

**Mitigation**: Build verification INTO the process steps.

```
Step 3: Verify your answer satisfies rules 1, 2, and 3.
  If all pass, output it.
  If any fail, identify which rule is violated,
  revise the answer, then output.
```

Do NOT use: "Review your output for errors."
Do use: specific checkable criteria embedded in the workflow.
Haiku's verification is only as good as the checklist you provide.
