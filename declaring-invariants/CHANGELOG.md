# Changelog

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
