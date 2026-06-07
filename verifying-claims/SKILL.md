---
name: verifying-claims
description: Check that a document's claims about code are actually true by reading the prose, the code, and the tests and reporting (or fixing) where they disagree. Use whenever the user wants to verify a README, guide, spec, or docstring still matches the code; whenever they mention documentation drift, doc-code sync, "is this still accurate", stale docs, or keeping docs/tests/code consistent; before publishing or merging a docs change; or as a periodic doc-accuracy sweep. The agent reads the prose's meaning directly — there is no claim-comment DSL to maintain. Pairs with TDD: the test suite is the deterministic behavioral gate, this skill is the semantic prose-vs-reality review.
metadata:
  version: 0.2.0
---

# verifying-claims

Check that what a document *says* about code is true, by reading the document,
the code, and the tests together and reporting where they disagree.

## What changed (v0.1 → v0.2)

v0.1 was a comment-DSL: you hand-wrote `<!-- claim: ... -->` next to prose and
a script checked the *comment* against the code. That had a fatal gap — the
comment and the prose were two artifacts stapled together, and only the comment
was checked, while humans read the prose. The prose could lie with a green run.

v0.2 drops the DSL. The reviewer is the agent: it reads the prose's *meaning*
directly and compares it to what the code does and what the tests assert. No
shadow copy, because the thing being checked is the thing the human reads.
(Existing tools already own the alternatives — Gherkin binds executable
scenarios, Lean's Verso transcludes facts into prose, TDD couples code to
tests. This fills the remaining slot: free-prose documentation, judged.)

## Division of labor — read this first

This skill does NOT gate merges and is NOT a test framework.

- **The test suite (TDD/CI)** owns the behavioral contract: deterministic,
  cheap, auditable, gated. A green check is something you can hold CI to.
- **This skill** owns the prose layer: does the documentation match reality?
  That needs semantic judgment across artifacts, which is non-deterministic and
  fallible — so it runs as a *triggered review* (before docs ship, on request,
  as a sweep), not as a per-commit gate. "The agent said the docs match" is not
  a guarantee you gate a merge on; it's a review you act on.

Tests are the anchor. The docs are correct when they agree with what the tests
assert about the code. So write/keep good tests first; this skill keeps the
prose pinned to them.

## Procedure

1. **Identify** the document(s) to check and the code + tests they describe.
2. **Gather** consistent input: run `scripts/gather_context.py --doc DOC --src
   SRC --tests TESTS`. It ast-parses source (no imports, no execution) and
   bundles the document text, the public API surface, and the test inventory.
3. **Extract the claims** the prose makes — every checkable assertion about the
   code (signatures, behavior, return shapes, defaults, guarantees, examples).
   Do this by reading; there are no claim markers.
4. **Judge each claim** against the API surface and the tests:
   - Does the code actually do what the prose says?
   - Is the claim backed by a test, or merely asserted?
   - Does it reference something that no longer exists?
5. **Report** drift, ranked by severity, each finding citing the prose claim and
   the contradicting reality (file/function). Use the verdicts below.
6. **Optionally fix**: rewrite the prose to match reality, and/or flag claims
   that need a test (an UNSUPPORTED claim is a missing test, not just a doc bug).

## Verdicts

- **PASS** — the prose claim matches the code and is exercised by a test.
- **FAIL** — the code contradicts the claim (the doc is wrong, or the code
  regressed and the doc caught it).
- **UNSUPPORTED** — the claim matches the current code but no test backs it, so
  nothing protects it from future drift. Surface as a missing test.
- **STALE** — the claim refers to something removed or renamed.

## Invoking

- "Check the README against the code before I publish it."
- "Does `docs/api.md` still match `pkg/`?"
- "Sweep the docs for drift after this refactor."

Run it at moments that matter — pre-publish, post-refactor, on a docs PR — not
on every commit. The deterministic gate is the test suite; this is the layer
tests can't reach.

## Honest limits

- Non-deterministic and fallible: a review can miss drift or misjudge. Treat
  output as a careful review, not a proof.
- Cost/latency: reading three artifacts and reasoning is expensive next to a
  test run. Don't wire it where a cheap deterministic check belongs.
- It checks prose against code+tests; it does not verify the tests themselves
  are correct. Garbage tests → confident-but-wrong PASS. TDD discipline upstream
  still matters.

## When NOT to use

- As a CI merge gate (use the test suite).
- To verify behavior (write a test).
- On prose with no factual claims about code (nothing to check).

## Files

- `scripts/gather_context.py` — deterministic input bundler (doc + API surface +
  test inventory), ast-only, no imports.
- `references/drift-report-example.md` — what a review report looks like.
