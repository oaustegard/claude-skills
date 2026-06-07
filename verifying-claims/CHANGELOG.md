# Changelog

## 0.2.0 — 2026-06-07

Pivot: from a claim-comment DSL to an agent-driven review.

The v0.1 model stapled a `<!-- claim: ... -->` comment beside prose and checked
the comment against the code. That left the prose — the half humans actually
read — unverified, and was out-engineered on both flanks (Gherkin binds
executable scenarios; Lean's Verso transcludes facts; TDD couples code to
tests). v0.2 fills the remaining slot — free-prose documentation — by having the
agent read the prose's meaning and compare it to the code and the tests
directly. No DSL, no shadow copy.

- Removed: `scripts/verify_claims.py` (the comment parser + signature/
  command-output resolvers), `assets/verify-claims.yml`, `assets/
  test_verify_claims.py`, `references/example-spec.md`. The CI/pytest forcing
  functions belonged to the DSL approach; the deterministic gate now lives where
  it should — the project's own test suite (TDD).
- Added: `scripts/gather_context.py` — deterministic input bundler (document +
  ast-parsed API surface + test inventory), no imports, no execution.
- Added verdict `UNSUPPORTED` — claim matches code but no test backs it (a
  missing test, surfaced as such).
- Reframed as a triggered review, not a merge gate; the division of labor with
  TDD is now explicit in SKILL.md.

## 0.1.0 — 2026-06-06

Initial skill (working title "verso"). Claim-comment DSL with `signature` and
`command-output` resolvers, `--watch`, import allowlist, and CI/pytest
integration templates. Superseded by 0.2.0.
