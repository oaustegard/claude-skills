# Example spec — all green, gateable

This document is a working example of a verso spec that is safe to put behind a
CI gate: every claim resolves to PASS. Unlike a teaching demo, it contains no
intentional drift. Run it from the skill directory:

```
VERSO_IMPORT_ALLOW=verso python3 scripts/verso.py references/example-spec.md
```

It makes claims about `verso.py` itself, so it doubles as a smoke test of the
verifier.

## Interface contracts (`signature`)

The parser takes the document text. <!-- claim: signature target=verso.parse_claims has-params=text -->

The driver takes a path and a json flag. <!-- claim: signature target=verso.verify_file has-params=path,json_out -->

The watch loop takes a path and an interval. <!-- claim: signature target=verso.watch has-params=path,interval -->

Each resolver takes the parsed claim args. <!-- claim: signature target=verso.resolve_signature has-params=args --> <!-- claim: signature target=verso.resolve_command_output has-params=args -->

## Behavior (`command-output`)

The CLI prints usage to stderr and exits 2 when given no file:
<!-- claim: command-output cmd='python3 ../scripts/verso.py' exit=2 stderr-contains=usage -->

The CLI accepts the documented flags in its usage line:
<!-- claim: command-output cmd='python3 ../scripts/verso.py' stderr-contains=--watch -->

## Why this one is gateable

A gated spec must be all-green: a CI required check fails the build on any
non-PASS verdict, so an intentional FAIL or STALE (the kind a teaching demo
uses to show what drift looks like) would wedge the gate. Keep demonstrations
in a separate, ungated document.
