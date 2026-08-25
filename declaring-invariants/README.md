# declaring-invariants

Find tests that enumerate a domain by copying it, and declare the invariants a
codebase depends on. Stdlib `ast` only — no install, no config file, no
network. Python.

```bash
python3 scripts/totality_lint.py <repo>   # tests that copy a domain
python3 scripts/claims.py <repo>          # what the repo declares, and what backs it
```

## Features

- **Copied-domain detection** — a `parametrize` or `for` over a literal whose
  members are a strict subset of a dict/set/tuple/Enum in the source, with the
  uncovered members named
- **Ratchets, the second claim form** — an enumeration loops whatever the
  domain now holds, so it cannot see the domain narrowing.
  `# totality: ratchet — <why>` marks a hand-list as a deliberate floor, and the
  linter checks the pin: `ratchet-broken` names a member that left, statically,
  before any test runs. `unratcheted` names a registry with an enumeration and
  no floor
- **Vacuity detection** — a live registry iterated with no `len(...) >= n`
  assertion, which passes over an emptied collection
- **Membership join** — `[1, 2, 3, 4, 8]` and `SUPPORTED_BITS` share no token,
  so containment is the join key; no naming convention is assumed
- **Reachability filter** — a literal matches a registry only when the test
  imports its module, shares its top-level directory, or is its paired
  `tests/test_<mod>.py`
- **First-class acknowledgement** — `# totality: partial — <why>` retires a
  finding, and an acknowledgement on a test that later covers the whole domain
  is reported as `stale-ack`
- **Claim inventory** — a claim is a test whose docstring opens `invariant:`,
  and `refuted:` records the observed negative control
- **Report by default** — `--strict` opts into a nonzero exit; `--json` for
  machine consumption; `--selftest` runs fixtures with no repo

## Why

On `oaustegard/remex`, adding a fourth member to `ROTATION_CODES` with no
construction behind it left the entire 267-test suite green. Four tests looked
total; each parametrized `["haar", "rht"]` against a three-member registry.

The other direction is worse. Substituting `"xyz"` for `"none"` in both
spellings of that domain — cardinality unchanged, both spellings agreeing — left
the domain floor, the enumeration and the parity check green, five passing tests
over a registry that had stopped supporting a rotation every index on disk was
written with. That is what the ratchet form is for.

Adapted from the meta-oracle in
[`daniloc/coherence`](https://github.com/daniloc/coherence), which classifies
an oracle's iteration root as LIVE or LITERAL by parsing the oracle's own AST.
The check needs none of that harness's spec files, claim grammar, ledger or
Node runtime.

See [SKILL.md](SKILL.md) for the full reference, including how to write a
refutation you have actually observed.
