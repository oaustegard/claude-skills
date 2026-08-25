---
name: gating
description: >-
  Build and audit deterministic verification gates — a check that blocks a
  pipeline and can be shown to go red. Use when writing a calibration gate,
  CI check, validation script or pre-publication check for a numeric or
  empirical result; when a plausible-but-wrong value would survive review;
  when asking whether an existing test, linter rule or check could actually
  fail; and when a suite passes first try, passes suspiciously often, or was
  written by whatever produced the thing it checks. Triggers on "can this
  check fail", "known-bad", "negative control", "calibration gate", "sanity
  check my results", "is this test actually testing anything".
metadata:
  version: 0.3.0
---

# gating

A gate is a check that blocks. Its only job is to go red when it should.

The characteristic failure is not a wrong check — a wrong check gets noticed.
It is a check that **cannot fail**, which reports PASS forever and is
indistinguishable from a working one from the outside. That is what makes this
different from ordinary testing: the object under suspicion is the check.

## When NOT to use this skill

Scope is ONE check and whether it can be made to fail.

| Situation | Use |
|---|---|
| Sequence several steps with branches and retries | flowing |
| Run the repo's existing suite | run it |
| Decide what to test at all | this skill has no opinion; that is design |

A gate is a thing that goes red. If nothing here can go red, there is no gate
to audit.

## The three obligations

Every gate owes these. A gate missing any of them is not yet a gate.

**1. An anchor outside your own code.** Something the check compares against
that your implementation did not produce: a published constant, a closed-form
answer, a conservation law, a degenerate case with a known result, an
independent implementation. A check that compares this run to the last run only
ever tells you the code still does what it did. See `references/anchors.md`.

**2. A known-bad it demonstrably rejects.** Break the subject the way it would
plausibly break, run the gate, confirm red. Until you have done this you have
not shown the gate works — you have shown it runs. This is the obligation
people skip, because a passing gate feels like evidence.

Two things about known-bads that are easy to get wrong:

- **Validate it at the configuration it will run in.** A case tuned on a small
  or fast setting can stop being bad at full size. An "untrained" grid built
  from one Lloyd iteration was genuinely zero-gain at m=2/K=16 and earned a
  real +0.10 dB at m=8/K=65536, where one iteration relocates ~63,000 empty
  cells toward the mode. It passed the fast gate and certified nothing about
  the real one. This matters more than it sounds, because `mutate.py` needs a
  fast gate variant and it is tempting to validate everything there.
- **Measure its *reach*.** One known-bad is the floor, not the goal. Name which
  checks it exercises (`known_bad(..., covers=(...))`); the harness prints the
  checks no known-bad reaches. An audited gate had a single known-bad covering
  1 of 8 checks — and the check its whole result rested on *accepted* the same
  bad case.

**3. A written statement of what it cannot catch.** Coverage holes are
invisible from inside a green run: the gate is silent about the thing it does
not look at, in exactly the same tone it uses for the thing it looked at and
approved. The author has to assert the hole; nothing else will.

`scripts/gate.py` enforces obligations 2 and 3 mechanically — it returns exit
code 2 (INCONCLUSIVE, not PASS) when a gate registers no known-bad or no
coverage limit.

## Building a gate

Work in this order. The first step is the one that determines whether the rest
is worth anything.

**Name the wrong conclusion, not the component.** Not "check the quantizer is
correct" but "prevent shipping *scalar wins at high bit rates* when that would
really be an optimizer artifact." A gate aimed at a conclusion knows what
counts as a near-miss; a gate aimed at a component just exercises the code.

**Find an anchor.** `references/anchors.md` lists the kinds, in rough order of
strength, with the questions that find each one.

**Prefer brackets to point checks.** Assert a value lies strictly between two
things it cannot legitimately pass: better than a baseline, worse than a
theoretical bound. A one-sided check passes for a result that collapsed as
readily as for one that is right — which is how an implementation that
silently does nothing gets certified.

**Derive the tolerance from measured noise.** Run the thing several times, see
how much it moves, put the threshold outside that. A tolerance picked for
comfort tends to land wider than the defect you are trying to catch, and then
it swallows it.

**Then check it is not too tight to mean anything.** The opposite failure is
real and less obvious: a margin can be statistically impeccable and practically
empty. A *paired* estimator — scoring both arms on one shared sample so the
common fluctuation cancels — is the right way to measure a difference, and its
standard error *shrinks as the two arms converge*. So "beats the baseline by
3 se" degenerates: a codebook perturbed by N(0, 1e-3) gained +0.0001 dB against
a 3-se margin of 1.2e-06 and was accepted, while real ones gained 0.35–1.41 dB.
The check certified *the effect is real*, not *the effect is worth having*.
Those are different assertions and need different thresholds — and the second
one has to come from an anchor (there, a published lattice codebook), never
from the estimator, which knows nothing about what magnitude would matter.

**Build the known-bad and confirm red.** Then run `scripts/mutate.py` for the
failures you did not think of.

**Wire it to a non-zero exit** and run it before the thing it gates, not after.
A gate that runs after the results are written is a report.

## Auditing an existing check suite

Given tests, a linter config, a CI job, or a gate someone already wrote, the
question is not "do these pass" but "can these fail". Full procedure in
`references/auditing.md`; the fast version:

- For each assertion, name a concrete input that makes it fail. If you cannot,
  it is decoration — delete it or fix it.
- Check each oracle's range against the range you actually operate in. A
  published table that stops short of your regime is a hole with a green light
  on it.
- Run `scripts/mutate.py` against the code the suite covers. Every survivor is
  a behaviour nothing checks.
- Look for assertions whose truth does not depend on the subject at all.
- Look for tolerances wider than the effect being measured.

## Scripts

```bash
# harness: refuses to report PASS without a known-bad and a coverage limit
python3 scripts/gate.py           # importable; see the module docstring

# mutation pass: which single-token changes does the gate NOT notice?
python3 scripts/mutate.py --target src/codec.py -- python3 calibrate.py
python3 scripts/mutate.py --target grids.py --max 40 -- pytest -q
```

`mutate.py` requires the gate to pass on unmutated code first and refuses to
run otherwise, because survivor counts against an already-red gate mean
nothing. It restores the file even on interrupt, and uses `tokenize` so string
literals and comments are never corrupted. It is the zero-dependency pass that
works against *any* gate command; once it stops finding survivors, `mutmut` or
`cosmic-ray` go deeper on Python test suites specifically.

## Anti-patterns

Each of these has shipped a wrong result somewhere. They are ordered by how
convincingly they impersonate a working gate.

| Anti-pattern | Why it survives review |
|---|---|
| **Slack wider than the defect** | A tolerance chosen for comfort. The gate passes the real thing *and* the broken thing, and reports PASS for both. Derive the threshold from noise, then confirm the known-bad falls outside it. |
| **An oracle with a coverage hole** | Published anchors end somewhere. If the defect is past the end of the table, the check is structurally incapable of catching it and looks fine. State the range the anchor covers. |
| **An assertion whose truth doesn't depend on the subject** | "The output has at least N distinct colours" is equally true of an unchanged frame. Prefer differential checks: the state must *change* when it should, and a toggle applied twice must return to the byte-identical original. |
| **Confirming the check ran, not that it can fail** | "Invoke it and confirm the step appears in the output" catches a check that was never wired up. It says nothing about a check that is wired up and toothless. |
| **Comparing against your own previous output** | Regenerated goldens ratify drift. If the golden came from the code under test, it is a changelog, not an oracle. |
| **A cache keyed on the problem rather than the method** | `cache[(m, K)]` cannot notice that the code producing the value changed. Version-stamp the artifact and delete on mismatch instead of trusting. |
| **A self-matching predicate** | `until ! pgrep -f trainer` never exits, because the watching shell's own argv contains `trainer`. Worse, a malformed variant exits immediately and reports the job finished while it runs. Wait on a PID. |
| **A margin that is significant but not meaningful** | A threshold derived purely from estimator noise certifies that an effect is *real*, not that it is *worth having* — and a paired estimator's noise shrinks as the arms converge, so the margin can approach zero. Pair every noise-derived floor with a magnitude an anchor says would matter. |
| **A strict bracket at an attainable optimum** | A theoretical bound is often reachable, and reaching it is the best possible outcome. A strict edge then goes red on a perfect result and blocks real work. Ask of each edge whether the subject can legitimately sit exactly there. |
| **A gate written by whatever produced the artifact** | Shared assumptions produce shared blind spots, and the convention both inherited is the one neither questions. Anchors are the defence, because an anchor is the one input the producer did not choose. |

## Division of labour

This skill is for results and pipelines where the failure mode is a
**plausible wrong number** that would survive a careful read.

| Use | When the risk is |
|---|---|
| **`gating`** (this) | A number or empirical result is about to be published or acted on, and a wrong-but-reasonable value would pass unnoticed. Output: a gate that blocks. |
| **`challenging`** | An artifact would draw a specific objection from a skeptical reader — prose, analysis, a recommendation, a diff. LLM judgement against a persona. Output: findings and a SHIP/REVISE/RETHINK verdict. |
| **`verifying-claims`** | Documentation says something about code that is no longer true. Output: prose-vs-code disagreements. |
| **A test suite / TDD** | Code you wrote does not behave as specified. Output: red tests. |

`challenging` asks *would a careful reader object?* `gating` asks *can this
check go red?* They are complements and they miss different things: an
adversarial reviewer will not recompute your constants, and a gate will not
notice that your framing is wrong.

**A gate checks correctness, and cannot check comparability.** If two arms of a
comparison are each individually correct but not *comparably implemented*, no
anchor and no mutant will see it: nothing is broken, so nothing goes red. A
published ablation reported one transform 11–24× slower than another and
carried a caveat saying the number was implementation-bound; both arms passed
every correctness check, and the real finding — one arm was a tuned BLAS call
and the other an interpreted loop — was found by a human reviewer months of
gate-work later. Related: **performance claims have no anchor in this
framework at all.** There is no published constant for how fast your code
should be. Wall-clock belongs to benchmarking discipline (matched
implementation effort, min-of-trials, stated hardware), not to gating.

One caution about pairing them. A same-model reviewer is an independent
*context*, not an independent *reviewer* — it shares your priors, so the
convention you did not question is the one it will not question either. Where
that matters, an anchor beats a reviewer, because an anchor is not
negotiable.

## References

- `references/anchors.md` — kinds of oracle, strongest first, and how to find
  one when nothing published exists.
- `references/auditing.md` — the full "can this fail?" pass over an existing
  suite, including how to read a mutation report.
