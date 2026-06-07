---
name: verifying-claims
description: Verify typed claims embedded in markdown/docs against live state, and run the literate-TDD loop (write spec with claims → red/green → gate in CI). Use this whenever the user wants to check that a README, spec, ops note, or design doc still matches the code it describes; whenever they mention claim verification, documentation drift, spec drift, executable documentation, literate testing, doc-code sync, or "docs that fail when they're wrong"; whenever turning a spec into a test that fails on drift; or when wiring doc-verification into TDD, CI, pre-commit, or a publish gate. Covers the `signature` and `command-output` claim types, the invariant-vs-mutable-state rule (never verify state that is expected to change), and the GitHub Action + pytest forcing functions that make the check unskippable.
metadata:
  version: 0.1.0
---

# verifying-claims

A claim verifier for documentation. Prose makes typed claims as HTML comments;
`verify_claims.py` resolves each against live state and reports PASS / FAIL / STALE /
ERROR. The point: documentation that **breaks loudly when it drifts**, instead
of going silently stale.

Named after [Verso](https://github.com/leanprover/verso), Lean's literate
framework, where the documentation and the formal proof share one elaboration
context so they cannot drift. This is the lightweight, language-agnostic
cousin: claims live next to prose and are checked against the live system.

## Claim syntax

A claim is an HTML comment sitting next to the prose it backs:

```
parse_claims takes a `text` argument.
<!-- claim: signature target=mymod.parse_claims has-params=text -->
```

The prose stays human-readable; the claim is invisible in rendered markdown.

## Claim types

Both encode **invariants** — things that should stay true. A FAIL means a real
defect to fix, not the passage of time.

### `signature`
Does a Python callable accept the listed named parameters? An interface
contract — like a checked header file.
```
<!-- claim: signature target=pkg.module.func has-params=a,b,c -->
```
Imports are restricted to an allowlist of module prefixes for safety
(`VERIFY_CLAIMS_IMPORT_ALLOW`, default `muninn_utils,scripts,verify_claims`).

### `command-output`
Run a command (subprocess, no shell, no eval) and assert its exit code and/or
output substrings. This is the behavioral / acceptance claim, and the bridge
to a real test suite — point it at a named test:
```
<!-- claim: command-output cmd='pytest tests/test_parse.py::test_quoted' exit=0 -->
<!-- claim: command-output cmd='mytool --help' exit=0 stdout-contains=usage -->
```
Args: `cmd` (required), `exit`, `stdout-contains`, `stderr-contains`, `timeout`.

## The one rule that matters: verify invariants, not mutable state

Only encode claims about things that **should stay true**. Do NOT verify state
that is *expected* to change — a PR's open/merged status, an issue's state, a
"current version" number. A PR going open→merged is the PR doing its job, not
drift.

The diagnostic: **which artifact do you edit to make a failing check pass?**
- Signature mismatch → you fix the code. Correct: there's a defect.
- "PR #687 is open" gone red → you can only edit the *claim* to say "merged,"
  chasing reality instead of constraining it.

When the document is the thing that must change, the check is just confirming a
stale cache. Mutable state wants **transclusion** (render the current value at
read time), not a frozen assertion + diff — a different mechanism, out of scope
here. (Earlier versions had `pr-state`/`issue-state`; they were removed for
exactly this reason.)

## Verdicts, and how they map to TDD states

- **PASS** — claim matches reality → green
- **FAIL** — the referenced thing exists but the assertion fails → classic red
- **STALE** — the referenced thing doesn't exist yet (function/test missing) →
  you're ahead of the code; pre-red
- **ERROR** — the resolver couldn't run (bad syntax, blocked import, timeout)

Exit 0 if all PASS, 1 otherwise. `--json` for machine output.

## Literate TDD: the spec doc IS the test suite

verifying-claims is the **outer** loop around a normal TDD inner loop. The inner loop
stays pure pytest (red→green→refactor, fast, behavioral). verifying-claims binds the prose
spec to those tests and to the code's interface, so the doc cannot claim a
behavior whose test was deleted.

The loop, test-first:
1. Write the spec doc describing what you want, with claims pointing at
   not-yet-written tests and signatures.
2. Run `verifying-claims spec.md` → all STALE/FAIL → **red**.
3. Write the test, then the implementation.
4. `verifying-claims spec.md` all PASS → **green**.
5. Refactor with verifying-claims as the regression net.

`signature` claims give the contract-first variant: write the API in the doc,
run verifying-claims (STALE), stub the function (PASS) — you've locked the interface in
prose before writing behavior.

Honest limit: verifying-claims does not assert `f(x) == y` itself (the unsafe `eval`
claim type was removed). Behavioral truth lives in pytest; `command-output`
claims check that the named test *passed*. verifying-claims is a binding/acceptance layer,
not a replacement for your assertions.

## What forces a run (the part that actually matters)

A verifier only helps if it runs — otherwise the drift moves from "doc vs code"
to "the verify-run vs reality." Unlike real Verso, where the check *is*
compilation, markdown renders fine whether or not its claims pass. So nothing
intrinsic forces a run. Bind verifying-claims to an event with its own enforcement, ranked
by how hard it is to skip:

1. **Required CI check on PRs** — strongest. Branch protection makes the verifying-claims
   job a required status; you cannot merge red. Structural, not disciplinary.
   Template: `assets/verify-claims.yml`.
2. **Claims as part of the pytest suite** — `test_verify_claims` runs verifying-claims and
   asserts exit 0, so verifying-claims runs whenever tests run and inherits the green-bar
   gate. Best fit when verifying-claims wraps a TDD loop. Template:
   `assets/test_verify_claims.py`.
3. **Publish-time gate** — the publish flow runs verifying-claims and refuses to ship a
   doc with failing claims. Binds verify to the irreversible action.
4. **Pre-commit hook / `--watch` / boot-surfacing** — raise the probability,
   don't force. Bypassable, local, or merely informational.

General rule: only gating the **irreversible action** (merge, publish, deploy)
on a **required** check actually forces a run, because it removes the choice.

## Running it

```
python3 scripts/verify_claims.py spec.md            # verify once; exit 0/1
python3 scripts/verify_claims.py --json spec.md     # machine-readable output
python3 scripts/verify_claims.py --watch spec.md    # re-verify on save (inner-loop aid)
```

`--watch` re-runs in a fresh subprocess on every save, so `signature` claims
pick up edited code. It forces nothing — it's category 4 above.

## Setting up the gate in a repo (the integration)

1. Copy `assets/test_verify_claims.py` into the repo's `tests/`, and point the
   `SPECS` list at the docs you want gated. Keep gated specs **all-green** —
   don't put teaching/demo claims that intentionally FAIL into a gated file.
2. Copy `assets/verify-claims.yml` into `.github/workflows/`. It runs verifying-claims on
   the gated specs and the pytest suite on every PR.
3. In repo settings → branches, add the workflow's job as a **required status
   check**. Now drift cannot merge.

See `references/example-spec.md` for a working all-green spec.

## Files

- `scripts/verify_claims.py` — the verifier (signature + command-output, --watch).
- `assets/verify-claims.yml` — GitHub Action template (forcing function #1).
- `assets/test_verify_claims.py` — pytest template (forcing function #2).
- `references/example-spec.md` — an all-green spec suitable for gating.
