# gating

Build and audit verification gates — deterministic checks that block a
pipeline and can be **shown** to go red.

The characteristic failure of a gate is not a wrong check. A wrong check gets
noticed. It is a check that *cannot* fail, which reports PASS forever and is
indistinguishable from a working one from the outside.

So the object under suspicion here is the check itself.

## The three obligations

| | | |
|---|---|---|
| **Anchor** | something your own code did not produce | published constant, closed form, invariant, theoretical bound |
| **Known-bad** | a case the gate demonstrably rejects | break the subject plausibly, run the gate, confirm red |
| **Coverage limit** | what it cannot catch, in writing | holes are invisible from inside a green run |

`scripts/gate.py` enforces the last two: a gate that registers no known-bad or
no coverage limit reports **INCONCLUSIVE** and exits 2, not PASS.

## Scripts

```bash
# mutation pass — which single-token changes does the gate NOT notice?
python3 scripts/mutate.py --target src/codec.py -- python3 calibrate.py
```

`mutate.py` is stdlib-only, uses `tokenize` (so it never corrupts strings or
comments), restores the file even on interrupt, and refuses to run when the
gate is already red. It works against *any* gate command; `mutmut` and
`cosmic-ray` go deeper once it stops finding survivors.

`gate.py` is a ~150-line harness: `anchor()`, `bracket()`, `known_bad()`,
`coverage()`, `note()`, and a `report()` that returns a process exit code.

## Relationship to `challenging`

`challenging` asks *would a careful reader object?* — LLM judgement against a
persona, verdicts of SHIP/REVISE/RETHINK. `gating` asks *can this check go
red?* — deterministic, anchored, exit-coded.

Complements with different blind spots: an adversarial reviewer will not
recompute your constants, and a gate will not notice that your framing is
wrong. Note also that a same-model reviewer is an independent *context*, not
an independent *reviewer*; where shared priors are the risk, an anchor beats a
reviewer because an anchor is not negotiable.

See [`SKILL.md`](SKILL.md) for the build and audit procedures and the
anti-pattern table, [`references/anchors.md`](references/anchors.md) for
choosing an oracle, and [`references/auditing.md`](references/auditing.md) for
the six-pass "can this fail?" sweep over an existing suite.
