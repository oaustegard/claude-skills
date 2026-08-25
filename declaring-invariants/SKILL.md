---
name: declaring-invariants
description: Find tests that enumerate a domain by copying it, and declare the invariants a codebase depends on. Reports where a parametrize list, for-loop, or it.each iterates a hand-written subset of a dict/set/tuple/Enum that exists in the source, and names the members nothing covers. Use when reviewing tests, when a module gains a name-to-thing table, registry, enum, or dispatch map, before trusting a green suite as evidence a domain is covered, or when asked "is this test actually total", "does anything cover X", "what does this repo guarantee", "which invariants do we declare". Also for vacuous tests that pass over an empty collection, for a domain that has silently NARROWED (an enumeration cannot see that), and for recording the refutation that proves a claim can fail.
metadata:
  version: 0.2.3
---

# declaring-invariants

Two scripts over one idea: **a test that enumerates a domain must loop the
registry rather than a copy of it.** Someone also has to say which domains
matter in the first place.

```bash
python3 scripts/totality_lint.py <repo>   # tests that copy a domain
python3 scripts/claims.py <repo>          # what the repo declares, and what backs it
```

Python only, stdlib `ast` only: no install, no config file, no network.

## The failure it catches

A test that loops a hand-written list passes its runner and proves nothing
about completeness. When the same members also exist as a registry in the
source, the list is a copy, and the copy drifts the moment someone adds a
member to the registry and not to the test. Nothing goes red.

Measured on `oaustegard/remex`, 2026-08-24: adding a fourth member to
`ROTATION_CODES` with no construction behind it left the **entire 267-test
suite green**. Four separate tests looked total; each parametrized
`["haar", "rht"]` against a three-member registry. Only a test that looped the
registry itself caught it.

Adapted from the meta-oracle in [`daniloc/coherence`](https://github.com/daniloc/coherence)
(`src/oracle-domain.ts`), which classifies an oracle's iteration root as LIVE
or LITERAL by parsing the oracle's own AST. That harness needs spec files, a
claim grammar, a ledger and Node; the check does not.

## `totality_lint.py` — tests that copy a domain

| finding | meaning |
|---|---|
| `sampled-domain` | a `parametrize` or `for` over a literal whose members are a strict subset of a source registry. The uncovered members are named. |
| `ratchet-broken` | a hand-list marked `ratchet` names a member the registry no longer contains. Detected statically, without running anything. |
| `unratcheted` | a registry enumerated live with nothing pinning its membership. Suppressed when `no-floor` already claimed the same line. |
| `no-floor` | a test iterates a live registry with no `len(...) >= n` assertion in the file, so an emptied registry passes vacuously. |
| `stale-ack` | an acknowledgement on a test that now covers the whole domain. |

```bash
python3 scripts/totality_lint.py <repo>            # the report
python3 scripts/totality_lint.py <repo> --json
python3 scripts/totality_lint.py <repo> --strict   # exit 1 if any finding
python3 scripts/totality_lint.py --selftest        # fixtures, no repo
```

A partial domain is often correct. Say so on the test and it stops being a
finding:

```python
# totality: partial — mojo has no construction for "none"
@pytest.mark.parametrize("rotation", ["haar", "rht"])
def test_save_params_accepts_every_mojo_rotation(rotation): ...
```

The marker also works as `totality: partial — <why>` inside the docstring. An
acknowledgement on a test that later covers the whole domain is reported as
`stale-ack`, so a suppression cannot become a silence.

## Why a hand-list is the second form

An enumeration loops **whatever the domain currently holds**, so it is
structurally blind to the domain narrowing. Remove a member and the loop simply
ranges over fewer of them, green. Raised by Yep, 2026-08-24; reproduced on
`oaustegard/remex` before being believed:

| perturbation of `ROTATION_CODES` | domain floor | enumeration | parity | hand-list |
|---|---|---|---|---|
| grow — add `"hadamard2"` | pass | **RED** | **RED** | pass |
| shrink — drop `"none"` | **RED** | pass | RED\* | pass |
| substitute — `"none"` → `"xyz"` in both spellings | pass | pass | pass | pass |

\* only because the *other* spelling of the domain did not shrink, which is
incidental to that repository.

In the substitution row cardinality holds, both spellings agree, and five green
tests cover a registry that quietly stopped supporting a rotation every index on
disk was written with. The floor is a **cardinality**
check; it cannot see a member swapped for another.

The second form is a **ratchet**: a hand-list asserting the domain keeps
containing it. Mark it and the linter checks the pin rather than taking the
marker's word for it.

```python
# totality: ratchet — these three shipped; one leaving is a compatibility break
def test_no_shipped_rotation_is_ever_removed():
    for shipped in ("haar", "rht", "none"):
        assert shipped in ROTATION_CODES
```

Under that same substitution the linter reports `ratchet-broken` naming
`'none'` **statically, before any test runs**, and the test itself goes red
while the other five pass.

So: an enumeration proves every current member is handled, and a ratchet proves
no member left without a decision. `unratcheted` names a registry that has the
first and not the second. Neither half alone is the answer.

**A ratchet covers shrink only.** Over a strict subset it still reports
`sampled-domain` for the members it never listed, because pinning two of three
says nothing about the third. Suppressing that would make the marker a
laundering channel — the escape hatch these notes criticise `via guard` for
being in coherence. It was one: until 2026-08-25, `# totality: ratchet` over
two of three members silenced the report entirely and checked nothing about the
third. Caught by an adversarial pass on this skill, not by its own tests.

## `claims.py` — what the repo declares

`totality_lint` asks whether a test's domain is complete. It presumes a test
exists. This asks the prior question, the one coherence's own Known Limits
concedes it does not answer: nothing enforces `exists ⇒ declared`.

A claim is a test whose docstring **opens** with `invariant:`. No new file
format, and the claim inherits its test's pass/fail:

```python
def test_every_skipped_directory_is_actually_skipped(self):
    """invariant: every name in SKIP_DIRS is excluded from the walk.

    refuted: replaced the walk's `part in SKIP_DIRS` check with
    `part in {"node_modules"}` -> this test went red naming `.coherence`,
    while the other 25 tests in this file stayed green.
    """
```

| finding | meaning |
|---|---|
| `unrefuted` | a claim nobody has watched fail |
| `literal` | the claiming test iterates a copy of the registry, so the claim cannot see a new member |
| `unanchored` | a registry no invariant names — a question, not a verdict |

A claim whose test carries a `ratchet` marker is reported as *pinning* its
registries rather than copying them, and a ratcheted registry is not
`unanchored`.

```bash
python3 scripts/claims.py <repo> [--json] [--strict] [--selftest]
```

## Write the refutation from what you observed

`refuted:` is the half that costs something. Break the chokepoint, watch the
claim go red **by name**, restore, and record what you saw. A green test and an
unfalsifiable one look identical from outside; the refutation is what separates
them.

**Never write a refutation you have not run.** The first refutation authored
for the `SKIP_DIRS` invariant above asserted a failure that did not occur — the
fixture placed the registry outside the test's reachability, so the test passed
under perturbation for an unrelated reason. A vacuous claim, written while
building the tool that catches vacuous claims, and caught only by running the
perturbation instead of trusting the sentence.

Procedure, in order:

1. Break the chokepoint the claim names, with one edit in the source rather
   than in the test.
2. Run the claiming test. Read the failure text. Note the member it named.
3. Run the rest of the file. Confirm the others stay green — if everything goes
   red, the claim is not localised and the refutation says nothing.
4. Restore the source.
5. Write `refuted: <the edit> -> <what went red, by name>`.

## Wiring it into a commit gate

The reference wiring lives in `oaustegard/claude-workspace`
(`scripts/tdd_hook.py`): a commit where a registry gained a member and no
`invariant:` test iterates it live is denied, naming the registry and what it
gained. Override with `no-invariant: <why>` in the commit body.

Registry **shrink** is gated the same way, and needs a ratchet rather than an
enumeration to clear it. A new function or a new branch is behavioural growth
too, but neither is diffable without guessing, and a gate that guesses stops
being consulted. A brand-new registry is not gated. Declaring one is a
judgement call; growing one has already made it.

## Where the two filters came from

Both filters exist because the unfiltered version was noise. Reproduce either
by removing the filter and re-running against a real repo.

- **`no-floor` fires only on a name independently recognised as a registry.**
  Firing on every `for x in <local>` produced 27 findings on `remex`, all
  noise: numpy arrays, query matrices, loop counters.
- **A literal matches a registry only when reachable** — the test imports its
  module or package, shares its top-level directory, or is its paired
  `tests/test_<mod>.py`. Matching against any registry in the tree joined a
  test in `discrepancy/` to registries in `kb-k-sweep/` and
  `remex-vs-higgs-ablation/` on a monorepo, because small integer sets collide
  by chance. Four findings became one, and the survivor was real.

The join key is **membership, not names**: `[1, 2, 3, 4, 8]` and
`SUPPORTED_BITS` share no token, so containment is what ties them together. No
naming convention is assumed, and none is required.

## Limits

- **Python only.** The extractors are `_registries_py` and `_domains_py`; a
  tree-sitter pair for another language slots in beside them. The join, the
  acknowledgements and the reports are all language-independent.
- **Report, not gate, by default.** `--strict` opts into a nonzero exit. The
  tool this was adapted from gates by default, and its parity arm false-fails a
  correct oracle that binds its domain to a local name first. A gate that
  false-fails stops being consulted.
- **A registry is a collection of constants.** A dict/set/tuple/list of
  literals, or an Enum body, with at least three members. A domain assembled at
  runtime is invisible here.
- **Multi-parameter tables are out of scope.** Only single-name
  `parametrize` is read.
- **`unanchored` is a question.** Most registries need no invariant. Treat the
  list as candidates for declaration, never as a backlog to clear.
- **A registry is modelled as a SET OF KEYS, so a value swap is invisible.**
  This is the largest hole in the design, and it undercuts the motivating
  example. `ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}` exists to pin
  bytes on disk; permuting it to `{"haar": 0, "rht": 2, "none": 1}` keeps every
  key, every count and every ratchet intact, and every index already written
  decodes under the wrong rotation. Verified 2026-08-25 on a fixture: the
  linter reports nothing and the gate's registry half reports nothing. (The
  gate denied that fixture, but on the unrelated TDD rule — checked, because
  claiming otherwise would have been the overclaim this skill exists to catch.)
  Nothing here checks a name-to-code mapping. Extracting `(key, value)` pairs
  as the member set would, at the cost of breaking the subset join against a
  `parametrize` list of keys.
- **A co-ordinated rename defeats the ratchet.** A global find/replace that
  renames a member in the registry AND in the hand-list leaves the pin intact,
  and this reports nothing. Verified 2026-08-25 on a fixture: renaming `"none"`
  to `"identity"` in both files was silent, while every index already on disk
  still decodes byte 2 as the old name. Both sides of a co-located hand-list
  move together, so no static check over one working tree can see it. The
  commit gate can, because it diffs against git history — and only if the
  ratchet itself is untouched in that commit, which it now requires.
- **A brand-new registry is neither gated nor pinned.** Create one with five
  members and never grow it and no gate ever fires. `unanchored` and
  `unratcheted` surface it in the report; the gate deliberately does not, on
  the grounds that gating every new module is how a gate stops being consulted.
  That is a judgement, not a proof, and it is the largest hole a cross-model
  review found.
- **A decorator-built registry is invisible.** `@register("name")` populating a
  dict at import time is the common Python registry idiom and is not a literal,
  so nothing here sees it. Named because it is the shape most likely to be
  mistaken for coverage.
- **Reachability is path-based, so a disconnected integration test is missed.**
  A test that neither imports the module, shares its top-level directory, nor
  pairs with it by filename will not be joined to the registry it samples. The
  filter trades that recall for the cross-project precision it was measured to
  buy.
- **The precision numbers come from three repositories, and the filters were
  fitted to two of them.** 27 noise findings on one, 3-of-4 cross-project joins
  on another. Those are the measurements that justified each filter; they are
  not a false-positive rate on a corpus, and should not be read as one.
- **Split and merge are invisible.** The diff is keyed on registry NAME, so
  renaming a registry, splitting one in two, or merging two into one falls
  through both the gained and lost paths.
- **A claim that passes is not a claim that is right.** This checks that a
  declared invariant loops the domain it names. Whether it is the *right*
  invariant is human judgement, and it is not automatable.

## Related

- `verifying-claims` covers the prose layer: does the documentation match
  reality? Agent-judged, non-deterministic, run as a triggered review. This
  skill is the deterministic half, over code and tests rather than prose.
- `tree-sitting` locates the registry or the test before you edit it.
