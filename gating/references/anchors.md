# Anchors — where a gate gets its authority

An anchor is the part of a check your implementation did not produce. It is
what separates a gate from a changelog.

Without one, the strongest thing a check can say is "this run agrees with the
last run," which is true of a codebase that has been quietly wrong since the
first commit.

Ordered strongest first. Take the highest one available; they compose, and a
gate with two anchors of different kinds is much harder to fool than one with
two of the same kind.

---

## 1. A published constant

Someone measured or proved it, in a paper or a standard, and printed the
digits.

**Questions that find one.** What field has been studying this for decades?
What is the textbook version of my quantity? Does my problem have a named
constant attached to it?

**Watch the range.** Published tables stop somewhere. Max's 1960 quantizer
table stops at 5 bits; a check built on it is structurally incapable of
noticing an error at 8 bits, and will report PASS in exactly the tone it uses
for the rates it covers. Record the covered range as a coverage limit.

**Watch the precision.** A hand-computed 1960 table has a last digit that may
be worse than your float64 fixed point. When your converged value disagrees
with a published one by a fraction of a percent, the table is sometimes the
one that is wrong — but say so with evidence (convergence residual, stability
across iteration counts, a uniqueness argument), not by widening the tolerance
until the test goes green.

---

## 2. A closed form

An exact expression you can evaluate independently of the machinery under
test — an integral, a recurrence, a combinatorial count.

This is the strongest anchor available for anything with a tractable special
case, because it does not merely constrain the answer, it *is* the answer.

**Pattern that works well:** find a degenerate configuration where a complex
implementation must reduce to a simple formula. Lift a scalar quantizer's
levels into an m-dimensional product grid, and nearest-neighbour assignment
decomposes per coordinate — so a KD-tree measurement and a closed-form
integral must agree to sampling error. That agreement exonerates the
*instrument*, which converts "one of these two things is broken" into "this
one thing is broken."

Always exonerate the instrument before blaming the subject.

---

## 3. A conservation law or invariant

Something that must hold regardless of the answer: a total that is preserved,
a norm left unchanged by an orthogonal map, a round-trip that must return the
input, an operation applied twice returning to the byte-identical original.

Cheap, and unusually good at catching the class of bug that produces
plausible-looking output. An inverse-transform round-trip that agrees to 1e-7
rules out a large family of indexing and sign errors in one line.

**Also invariant-shaped:** monotonicity that theory requires (quality improves
with more bits, error shrinks with more samples), and orderings that must hold
between arms.

---

## 4. A theoretical bound

A quantity that cannot be exceeded — an information-theoretic limit, a
complexity lower bound, a physical constraint.

Bounds are one-sided, so they are best used as the far side of a bracket:
better than the baseline, *and* not better than the bound. A result that beats
its own theoretical limit is not a triumph, it is a bug, and this is the check
that catches it.

Bonus signal: watch the ratio-to-bound as a parameter sweeps. If theory says
it should approach a constant, a smooth monotone approach is corroboration
that many independent parts are right at once.

---

## 5. An independent implementation

A second implementation of the same computation — a reference library, a slow
brute-force version, a different language.

**Weaker than it looks.** Two implementations agree on a false result whenever
they share a modelling assumption, and if the same author or the same model
wrote both, they share more than they appear to. Vary the assumption and the
author, not just the code. A deliberately naive O(n²) brute force is usually a
better second implementation than a clever one, because it shares less.

---

## 6. A known-answer fixture

An input whose output you know for reasons outside the code: a worked example
from a textbook, a case computed by hand, a case with an answer fixed by
symmetry.

Small ones are fine. The value is that the answer's provenance is external.

---

## When nothing published exists

Some quantities have no literature. Options, in order:

**Construct a degenerate case.** Set a parameter to a value where the answer
becomes obvious — zero noise, one dimension, an identity transform, a
single-element input. Assert the obvious answer.

**Use a differential.** Absolute correctness may be unavailable while a
*difference* is provable: this input must score higher than that one; adding
data must not make the fit worse; the treated arm must beat the control.
Differential anchors survive a great deal of implementation drift.

**Manufacture a ground truth.** Generate synthetic data with a known answer
baked in, then check the pipeline recovers it. Guard against the pipeline
recovering it *by construction* — plant a case where the answer is deliberately
not what the pipeline would assume.

**Bound it from both sides with two crude methods** that are wrong in opposite
directions. Neither is the answer; together they are a bracket.

---

## An anchor is also where a *magnitude* comes from

Anchors are usually discussed as sources of correctness — is this value right?
They are equally the only source of **practical significance**: is a difference
big enough to care about?

A threshold derived from measurement noise answers "is this effect real". It
cannot answer "is this effect worth having", and the two diverge badly when the
things being compared are similar: a paired estimator's standard error shrinks
as the arms converge, so a 3-sigma margin can approach zero and admit an effect
three orders of magnitude below anything that matters.

So when a check exists to certify that something *helps*, it needs two floors:

- a **statistical** floor from measured noise — the effect is not sampling luck;
- a **practical** floor from an anchor — the effect is at least as large as
  <published method / theoretical gain / the smallest difference that would
  change a decision>.

State which anchor supplies the second one. If none does, say so as a coverage
limit: "this check certifies the effect is real, not that it is useful."

## Anchor hygiene

- **Write the source next to the number.** `0.0716821  # Conway & Sloane,
  normalised second moment of E8`. An unattributed constant becomes a golden
  value within a release, and nobody can tell whether it is authority or
  history.
- **Never derive an anchor from the code under test**, including "I ran it
  once and it looked right."
- **Version-stamp cached artifacts.** If an anchor or a fitted object is
  cached, key the cache on the *method* as well as the problem, and delete on
  mismatch. A cache keyed only on the problem silently serves values produced
  by code you have since changed.
- **State the covered range** every time. It is the single most common way an
  anchored gate turns out to have been blind.
