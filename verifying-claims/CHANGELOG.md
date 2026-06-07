# Changelog

## 0.1.0 — 2026-06-06

Initial skill. Packaged from the muninn-utilities prototype (`prototypes/verifying-claims/`,
PRs #58/#59/#60).

- `signature` and `command-output` claim types (invariants only).
- Removed `pr-state`/`issue-state`: mutable state that is expected to change is
  not an invariant to verify; the only way to clear such a FAIL is to edit the
  claim, which is backwards. Belongs in transclusion, not verification.
- Removed `eval` (arbitrary code execution on document input); `command-output`
  replaces it via subprocess.
- `--watch` inner-loop mode.
- Module-import allowlist (`VERIFY_CLAIMS_IMPORT_ALLOW`) for `signature` safety.
- Integration templates: GitHub Action (`assets/verify-claims.yml`) and pytest
  (`assets/test_verify_claims.py`) — the forcing functions that gate merges.
- `references/example-spec.md`: an all-green, gateable spec.

## [0.1.0] - 2026-06-07

### Other

- skill(verifying-claims): claim verifier + literate-TDD protocol (renamed from verso) (#689)
