# verifying-claims

Check that what a document *says* about code is true — by reading the document,
the code, and the tests together and reporting where they disagree.

The reviewer is the agent, not a parser. There is no claim-comment DSL: the
prose's meaning is read directly and compared to what the code does and what the
tests assert. No shadow copy, because the thing checked is the thing the human
reads.

See `SKILL.md` for the procedure, the verdicts (PASS / FAIL / UNSUPPORTED /
STALE), and the division of labor with TDD.

## Quick start

```
python3 scripts/gather_context.py --doc README.md --src pkg/ --tests tests/
```

That bundles the document text, the public API surface (ast-parsed, never
imported), and the test inventory into one report. The agent then reads the
bundle and judges each prose claim against it.

## What this is and isn't

- **Is:** a triggered, semantic review of whether documentation matches reality
  — run before docs ship, after a refactor, or as a sweep.
- **Isn't:** a CI merge gate or a test framework. The deterministic behavioral
  gate is your test suite (TDD). This is the prose layer tests can't reach.

## Files

- `scripts/gather_context.py` — deterministic input bundler.
- `references/drift-report-example.md` — what a review report looks like.
