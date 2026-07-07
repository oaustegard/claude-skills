# Semi-Formal Code Reasoning (Full Templates)

These templates tell you exactly what to do at each step. Follow them literally. Do not skip steps. Do not summarize — write out each step's result before moving to the next.

## Template 1: Patch Verification

Use when reviewing a diff or proposed fix.

### Procedure

**Step 1: State premises.**
Write exactly three lines:
```
P1: The patch modifies [list every file and function touched].
P2: The intended fix is [one sentence: what the patch should accomplish].
P3: Must not break [one sentence: what existing behavior must be preserved].
```

**Step 2: Function resolution.**
For EACH function call that appears in the changed lines, resolve it using this exact sequence. Write out each sub-step:
1. Is there a local variable or parameter with this name in the current function? If yes → that's what's called. STOP.
2. Is there a definition with this name in the enclosing class? If yes → that's what's called. STOP.
3. Is there a definition with this name at module level (same file, top-level)? If yes → that's what's called. STOP.
4. Is this name imported? If yes → trace the import to its source. That's what's called. STOP.
5. Is this a language builtin? If yes → the builtin is what's called. STOP.
6. If none of the above: flag as UNRESOLVED.

If at any step you find a definition AND a later step would also match (e.g., a module-level function has the same name as a builtin), write: "NAME SHADOWING: [name] at [scope] shadows [what it shadows]."

**Step 3: Execution trace.**
Pick one concrete input that triggers the bug. Write:
```
Before patch: [input] → step-by-step what happens → [buggy result]
After patch:  [input] → step-by-step what happens → [correct result]
```
Keep each trace to 3-5 steps maximum.

**Step 4: Regression check.**
For each function modified by the patch, find one other place in the code that calls it. Write:
```
[caller] calls [modified function] with [typical input] → still produces [expected output]: PRESERVED
```
If you cannot find a caller, write: "No callers found in provided context."
If behavior would break, write: "REGRESSION: [caller] would now get [wrong result] because [reason]."

**Step 5: Edge cases.**
List 1-3 inputs the patch does not handle. If none exist, write: "No unhandled edge cases identified."

**Step 6: Verdict.**
Use this decision rubric:
- BUGGY: Step 2 found unresolved shadowing that changes behavior, OR Step 4 found a regression, OR Step 3 shows the fix doesn't work.
- CONCERNS: Step 5 found edge cases that could fail, OR Step 2 found shadowing that might not affect behavior but is risky.
- LIKELY_CORRECT: All steps passed but the provided context is incomplete (you couldn't trace all callers).
- CORRECT: All steps passed and the context is sufficient to verify fully.

Write exactly:
```
VERDICT: [CORRECT | LIKELY_CORRECT | CONCERNS | BUGGY]
CONFIDENCE: [high | medium | low]
SUMMARY: [one sentence explaining the verdict]
```

### Worked Example: Patch Verification

**Input:** A Django patch that changes `django/utils/text.py` line 42 from `return format(value, spec)` to `return builtins.format(value, spec)`.

**Correct output:**

```
P1: The patch modifies django/utils/text.py, function format_lazy(), line 42.
P2: The intended fix is to call Python's builtin format() instead of the module-level format() function.
P3: Must not break existing callers of format_lazy() who expect standard string formatting.

FUNCTION RESOLUTION:
- format() on line 42 (before patch):
  1. Local variable? No.
  2. Enclosing class? No (this is a module-level function).
  3. Module-level definition? YES — django/utils/text.py defines format() at line 12.
  → NAME SHADOWING: module-level format() at line 12 shadows builtin format().
  → Before patch: line 42 calls the module-level format(), not the builtin.

- builtins.format() on line 42 (after patch):
  1-4. Explicit builtins reference bypasses all scopes.
  5. builtins.format is the Python builtin.
  → After patch: line 42 calls the builtin format(). Shadowing is bypassed.

EXECUTION TRACE:
Before patch: format_lazy("hello {}", "world") → calls module-level format()
  → module-level format() does lazy evaluation wrapping → returns LazyString, not "hello world"
After patch: format_lazy("hello {}", "world") → calls builtins.format("hello {}", "world")
  → builtin format() does string formatting → returns "hello world"

REGRESSION CHECK:
- Other callers of format_lazy(): template rendering in django/template/base.py
  → calls format_lazy() expecting a formatted string → now gets correct string: PRESERVED
- Direct callers of module-level format(): unchanged, not touched by this patch: PRESERVED

EDGE CASES:
- format_lazy() called with no arguments: builtins.format() would raise TypeError. Same behavior as before (module format() also requires arguments). Not a new issue.

VERDICT: CORRECT
CONFIDENCE: high
SUMMARY: Patch correctly bypasses name shadowing by explicitly calling builtins.format().
```

---

## Template 2: Fault Localization

Use when finding which line(s) cause a bug.

### Procedure

**Step 1: State premises.**
Write exactly two lines:
```
P1: The symptom is [what actually happens — the observable bug].
P2: The expected behavior is [what should happen instead].
```

**Step 2: Code path trace.**
Starting from the entry point, trace execution for an input that triggers the bug. For each line that matters, write:
```
LINE [N]: [what the code does] → [result for the buggy input]
```
Maximum 10 lines. Focus on lines where the result is surprising or where behavior diverges from P2.

**Step 3: Divergence analysis.**
For each line that looks suspicious (where the result contradicts P2), write:
```
CANDIDATE LINE [N]: [the code]
  CLAIM: This produces [behavior] which contradicts P2 because [reason].
  SUFFICIENCY TEST: If I fix ONLY this line, does the symptom go away?
    - Yes, because [explanation] → ROOT CAUSE
    - No, because [what else would still be wrong] → CONTRIBUTOR ONLY
```

**Step 4: Output.**
```
BUGGY LINES: [line number(s)]
REASON: [one sentence per line explaining why]
```

### Worked Example: Fault Localization

**Input:** JwtAuthenticator.java (383 lines). Symptom: "Users can gain admin access without proper JWT credentials."

**Correct output:**

```
P1: The symptom is that users with unsigned or plaintext JWTs can bypass authentication and gain admin access.
P2: The expected behavior is that only users with properly signed and verified JWTs can authenticate.

CODE PATH TRACE (for a PlainJWT input — an unsigned token):
LINE 195: jwt = JWTParser.parse(tokenString) → parses successfully, returns PlainJWT object
LINE 198: signedJWT = jwt.toSignedJWT() → PlainJWT has no signature, returns null
LINE 199: if (signedJWT != null) { verifySignature(signedJWT) } → signedJWT is null, skips entire signature verification block
LINE 215: claims = jwt.getJWTClaimsSet() → extracts claims from the unverified PlainJWT
LINE 220: return buildProfile(claims) → builds authenticated profile from unverified claims

DIVERGENCE ANALYSIS:
CANDIDATE LINE 198: jwt.toSignedJWT() returns null for PlainJWT
  CLAIM: Returning null instead of throwing an exception means unsigned tokens silently pass through.
  SUFFICIENCY TEST: If I fix ONLY this line (e.g., throw if null), does the symptom go away?
    - Yes, because unsigned tokens would be rejected here before reaching claims extraction → ROOT CAUSE

CANDIDATE LINE 199: if (signedJWT != null) { verifySignature(signedJWT) }
  CLAIM: The null check skips verification entirely when toSignedJWT returns null.
  SUFFICIENCY TEST: If I fix ONLY this line (e.g., add else { throw }), does the symptom go away?
    - Yes, because the else branch would reject unsigned tokens → ROOT CAUSE

CANDIDATE LINE 215: claims = jwt.getJWTClaimsSet()
  CLAIM: Extracts claims from an unverified token.
  SUFFICIENCY TEST: If I fix ONLY this line, does the symptom go away?
    - No, because the unsigned token was already accepted at line 199. Moving claims extraction wouldn't prevent authentication → CONTRIBUTOR ONLY

BUGGY LINES: 198, 199, 215
REASON: Line 198 returns null for unsigned tokens instead of failing. Line 199 treats null as "skip verification" instead of "reject." Line 215 processes claims from tokens that were never verified.
```

---

## Template 3: Patch Equivalence

Use when determining if two patches produce the same test outcomes.

### Procedure

**Step 1: State premises.**
```
P1: Patch 1 modifies [file(s)] by [what it changes].
P2: Patch 2 modifies [file(s)] by [what it changes].
P3: The tests check [what behavior the tests verify].
```

**Step 2: Function resolution.**
For EACH function call in EACH patch, follow the 5-step resolution procedure from Template 1, Step 2. Write results for both patches.

**Step 3: Per-test analysis.**
For each relevant test, write:
```
TEST: [test name or description]
  Patch 1: [execution trace, 2-3 steps] → [PASS or FAIL]
  Patch 2: [execution trace, 2-3 steps] → [PASS or FAIL]
  Comparison: [SAME or DIFFERENT]
```

**Step 4: Verdict.**
- If ALL tests show SAME → "YES, patches are equivalent modulo tests."
- If ANY test shows DIFFERENT → "NO, patches are not equivalent." Then write:
```
COUNTEREXAMPLE: Test [name] → Patch 1 [PASS/FAIL], Patch 2 [PASS/FAIL] because [trace showing divergence].
```

---

## Common Mistakes to Avoid

1. **Skipping function resolution.** Do not assume a function call refers to the obvious definition. Trace it through the 5-step sequence every time.
2. **Stopping at "contributor."** The sufficiency test ("fix ONLY this line") is mandatory. Finding a suspicious line is not the same as finding the root cause.
3. **Empty regression checks.** "No regressions" is acceptable only after checking at least one downstream caller. If no callers are visible, say so explicitly.
4. **Vague execution traces.** Each step must show a concrete value or state change, not "processes the input" or "handles the request."
