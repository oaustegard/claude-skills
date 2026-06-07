# verso

A claim verifier for documentation. Prose embeds typed claims as HTML
comments; `verso.py` resolves each against live state and reports
PASS / FAIL / STALE / ERROR. Documentation that breaks loudly when it drifts,
instead of going silently stale.

See `SKILL.md` for the full protocol: claim types, the invariant-vs-mutable
rule, the literate-TDD loop, and the forcing functions that make the check
unskippable.

## Quick start

```
python3 scripts/verso.py references/example-spec.md     # verify (exit 0/1)
python3 scripts/verso.py --watch path/to/spec.md        # re-verify on save
```

## Claim types

- `signature` — a Python callable has the expected named parameters.
- `command-output` — a subprocess exits as expected / prints expected output
  (the bridge to a real test suite: point it at a named pytest).

Both encode invariants. Mutable state that is *expected* to change (PR/issue
state, current versions) is deliberately out of scope — see SKILL.md.

## Integration (forcing functions)

- `assets/verso-claims.yml` — GitHub Action; make it a required check so drift
  cannot merge.
- `assets/test_verso_claims.py` — pytest that runs verso on gated specs; rides
  the existing green-bar gate.
- `references/example-spec.md` — a working all-green spec to gate on.
