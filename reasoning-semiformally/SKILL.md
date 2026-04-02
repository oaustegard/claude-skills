---
name: reasoning-semiformally
description: Apply semi-formal certificate reasoning to code analysis — patch verification, fault localization, patch equivalence. Use when reviewing patches, hunting bugs across scopes, comparing fixes, or when code reasoning requires tracing execution across files/modules. Triggers on code review, bug localization, patch comparison, name shadowing, scope analysis, regression checking.
---

# Semi-Formal Code Reasoning

Structured certificate templates that force mandatory checkpoints before conclusions. Based on Ugare & Chandra (2026), validated in our replication experiments.

## Core Principle

These templates are **cognitive forcing functions**. They change what the model thinks about before concluding — not its reasoning ability. Standard chain-of-thought lets pattern-matching to plausible answers. Structured templates insert mandatory scope checks, execution traces, and sufficiency verifications.

**Value scales with reasoning distance.** Locally-obvious bugs show no improvement. Cross-scope, cross-file, and architectural bugs show dramatic gains (+11pp fault localization in our experiments).

## When to Apply

Apply semi-formal reasoning when:
- Tracing execution across module boundaries or class hierarchies
- Name shadowing or scope ambiguity is possible
- A fix might introduce regressions in untouched code paths
- Comparing two patches for behavioral equivalence
- Bug symptoms are distant from root cause (cross-file, cross-scope)

Skip when:
- Bug is locally obvious (typo, off-by-one in same function)
- Change is trivial (docs, formatting, version bumps)
- No execution paths cross scope boundaries

## Templates

Three templates for different tasks. Each follows the certificate pattern: premises → mandatory traces → formal conclusion.

### Patch Verification

For reviewing diffs. Forces function resolution, execution tracing, regression checking.

**Automated path:** `from muninn_utils.verify_patch import verify_patch` — wraps this template in a sub-agent call with outcome tracking. Use for PR workflows.

**Direct application:** When reasoning about a patch inline (no sub-agent), follow this structure:

```
PREMISES:
P1: The patch modifies [what files/functions]
P2: The intended fix is [what it should do]
P3: Must not break [existing behavior]

FUNCTION RESOLUTION:
For each function call in the patch — trace which definition is actually invoked.
Check imports, module scope, class scope, builtins. Flag any name shadowing.

EXECUTION TRACE:
Before: [input] → [buggy behavior]
After:  [input] → [expected behavior]

REGRESSION CHECK:
For each touched code path: [preserved / broken] because [evidence]

EDGE CASES:
[Any unhandled scenarios]

VERDICT: [CORRECT | LIKELY_CORRECT | CONCERNS | BUGGY]
CONFIDENCE: [high | medium | low]
SUMMARY: [one sentence]
```

The critical checkpoint: **FUNCTION RESOLUTION**. "Which function is actually being called?" catches name shadowing and import errors that narrative reasoning misses.

### Fault Localization

For finding which line(s) cause a bug. Forces divergence analysis and sufficiency verification.

```
PREMISES:
P1: The symptom is [what happens]
P2: The expected behavior is [what should happen]

CODE PATH TRACE:
For each relevant line:
  LINE [N]: [what it does] → [result for buggy input]

DIVERGENCE ANALYSIS:
For each candidate buggy line:
  CLAIM D[N]: At line [N], [code] produces [behavior]
              which contradicts P2 because [reason]
  VERIFICATION: Would fixing ONLY this line fix the symptom? [yes/no + why]

BUGGY LINES: [number(s)] — [reason]
```

The critical checkpoint: **"Would fixing ONLY this line fix the symptom?"** Forces sufficiency verification — prevents identifying a line that contributes to the bug but isn't the root cause.

### Patch Equivalence

For determining if two patches produce identical test outcomes. Forces per-test execution tracing for both patches.

```
DEFINITIONS:
D1: Two patches are EQUIVALENT MODULO TESTS iff the test suite produces
    identical pass/fail outcomes for both patches.

PREMISES:
P1: Patch 1 modifies [file(s)] by [change]
P2: Patch 2 modifies [file(s)] by [change]
P3: The tests check [behavior]

FUNCTION RESOLUTION:
For EACH function call in each patch:
- Trace Python name resolution (local → enclosing → module → builtins)
- Check for module-level definitions that might shadow builtins

ANALYSIS OF TEST BEHAVIOR:
For each test:
  Claim 1: With Patch 1, test will [PASS/FAIL] because [execution trace]
  Claim 2: With Patch 2, test will [PASS/FAIL] because [execution trace]
  Comparison: [SAME / DIFFERENT]

COUNTEREXAMPLE (if different):
  Test [name] → different outcomes because [trace]

ANSWER: [YES equivalent | NO not equivalent]
```

## Composing Templates

For complex tasks, compose templates sequentially:
1. **Fault localization** to find the bug
2. **Patch verification** to validate a proposed fix
3. **Patch equivalence** to compare alternative fixes

Each template output feeds the next as premises.

## Provenance

- Paper: Ugare & Chandra, "Agentic Code Reasoning with Semi-Formal Certificates" (arXiv:2603.01896, March 2026)
- Replication: Validated on Django name-shadowing (0%→100% fault localization) and 3 real bugs from private repos (+11pp aggregate)
- Blog: austegard.com/blog/replicating-agentic-code-reasoning/
