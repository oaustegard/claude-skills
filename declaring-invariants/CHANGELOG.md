# Changelog

## 0.2.0 — 2026-08-24

A second claim form, because an enumeration is structurally blind to its own
domain narrowing. It loops whatever the registry currently holds, so removing a
member leaves it green over the ones that remain. Raised by Yep; reproduced on
`oaustegard/remex` before being believed, and the reproduction is worse than the
report. Substituting `"xyz"` for `"none"` in both spellings of the rotation
domain — keeping cardinality, keeping the two spellings in agreement — left the
domain floor, the enumeration and the parity check all green. Five passing tests
over a registry that had quietly stopped supporting a rotation every index on
disk was written with. The floor is a cardinality check and cannot see a member
swapped for another.

`# totality: ratchet — <why>` marks a hand-list as a deliberate floor. Unlike
`partial`, which excuses a hand-list, `ratchet` asserts one, and the linter
checks the pin rather than taking the marker's word for it. Two new findings:
`ratchet-broken` names a pinned member the registry no longer contains, detected
statically before any test runs, and `unratcheted` names a registry enumerated
live with nothing pinning its membership. `sampled-domain` no longer fires on a
marked ratchet — a hand list is sometimes the right answer, on purpose.

A ratchet pins every registry it is a floor for, not just the nearest one, since
a domain is often spelled twice. `claims.py` reports a ratchet claim as pinning
its registries rather than copying them, and a ratcheted registry is no longer
`unanchored`.

Verified on remex under the same substitution: `ratchet-broken` naming `'none'`
statically, and the ratchet test red while the other five pass.

55 tests, up from 45.

## 0.1.0 — 2026-08-24

First release. Two scripts, one idea: a test that enumerates a domain must loop
the registry rather than a copy of it.

`totality_lint.py` reports `sampled-domain` (a `parametrize` or `for` over a
literal whose members are a strict subset of a dict/set/tuple/Enum in the
source, naming the members nothing covers), `no-floor` (a live registry
iterated with no length assertion, so an emptied registry passes vacuously),
and `stale-ack`. `claims.py` reports what the repository declares: a claim is a
test whose docstring opens `invariant:`, and `refuted:` records the observed
negative control. Findings are `unrefuted`, `literal`, `unanchored`.

Adapted from the meta-oracle in `daniloc/coherence` (`src/oracle-domain.ts`),
which classifies an oracle's iteration root as LIVE or LITERAL by parsing the
oracle's own AST. Three deliberate differences. The join is on membership
rather than on names, because `[1, 2, 3, 4, 8]` and `SUPPORTED_BITS` share no
token and containment is what ties them together. Reporting is the default and
`--strict` opts into a nonzero exit, because the original's parity arm
false-fails a correct oracle that binds its domain to a local name first. And
there are no spec files: these take a path.

Both precision filters came from a measured false positive rather than from
taste. `no-floor` firing on every `for x in <local>` produced 27 findings on
`oaustegard/remex`, all noise — numpy arrays, query matrices, loop counters —
so it now fires only on a name independently recognised as a registry. Matching
a literal against any registry in the tree joined a test in `discrepancy/` to
registries in `kb-k-sweep/` and `remex-vs-higgs-ablation/` on a monorepo,
because small integer sets collide by chance; requiring reachability took four
findings to one, and the survivor was real.

Two extractor fixes came from the first real use. Tests that load their subject
through `importlib` reach registries as `tl.SKIP_DIRS`; peeling that attribute
to its object lands on the module handle, and following the handle through the
file's own constants lands on `_SPEC`, which shadowed the name that mattered
and made every claim read as unanchored. Candidates now carry the attribute
name and win over the resolved root, `_reachable` accepts the
`tests/test_<mod>.py` to `<mod>.py` pairing, and the `no-floor` message names
the matched registry rather than whatever the chain rooted in.

Measured at release: on `remex` at main, exactly the four rotation tests that
parametrize `["haar", "rht"]` against a three-member `ROTATION_CODES`, each
naming `'none'`. 45 tests, plus a `--selftest` in each script.
