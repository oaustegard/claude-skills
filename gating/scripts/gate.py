#!/usr/bin/env python3
"""A tiny harness for gates that can actually fail.

The whole point of a gate is to go red when it should.  The characteristic
failure is not a wrong check — it is a check that *cannot* fail, which reports
PASS forever and reads exactly like a working one.

So this harness refuses to let a gate pass unless it registered at least one
`known_bad` case that its own criteria rejected.  A gate with no known-bad is
reported as INCONCLUSIVE and exits non-zero, because "nothing looked wrong" is
not evidence when nothing could have looked wrong.

    from gate import Gate

    g = Gate("codebook calibration")

    g.anchor("scalar quantizer, 2 bits", measured=0.117482, published=0.1175,
             rel_tol=2e-3, source="Max (1960) table 1")

    g.bracket("trained grid sits between scalar and the Shannon bound",
              value=0.0887, lo=0.0625, hi=0.1175,
              why="must beat scalar; cannot beat the rate-distortion bound")

    g.known_bad("an under-trained grid is rejected",
                rejected=under_trained_mse > threshold,
                detail=f"{under_trained_mse:.5f} > {threshold:.5f}")

    g.coverage("Max's table stops at 5 bits — rates above that are unanchored")

    raise SystemExit(g.report())

Stdlib only.  Import it, or copy the class into your gate script; it is small
on purpose.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass
class _Check:
    ok: bool
    label: str
    detail: str
    kind: str  # "anchor" | "bracket" | "check" | "known-bad"
    covers: tuple[str, ...] = ()  # known-bad only: checks it exercises


@dataclass
class Gate:
    """Collects checks, then reports and returns a process exit code."""

    name: str = "gate"
    checks: list[_Check] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    stream = sys.stdout

    # -- primitives --------------------------------------------------------

    def check(self, ok: bool, label: str, detail: str = "", *,
              kind: str = "check", covers: tuple[str, ...] = ()) -> bool:
        """Record a plain boolean check."""
        self.checks.append(_Check(bool(ok), label, detail, kind, covers))
        return bool(ok)

    def anchor(self, label: str, *, measured: float, published: float,
               rel_tol: float, source: str) -> bool:
        """Compare a measurement against a value from outside your own code.

        `source` is required and is printed: an anchor whose provenance is not
        written down decays into a golden value, and a golden value only ever
        tells you the code still does what it did.
        """
        rel = abs(measured - published) / abs(published) if published else float("inf")
        return self.check(
            rel < rel_tol, f"{label} [anchor: {source}]",
            f"measured={measured:.6g} published={published:.6g} "
            f"rel={rel:.2e} tol={rel_tol:.0e}", kind="anchor")

    def bracket(self, label: str, *, value: float, lo: float, hi: float,
                why: str = "", lo_inclusive: bool = False,
                hi_inclusive: bool = False) -> bool:
        """Assert lo < value < hi, or <= at either edge.

        Two-sided by construction.  A one-sided check passes for a value that
        collapsed as readily as for one that is right, which is how an
        implementation that silently does nothing gets certified.

        **Use the inclusive flag when an edge is ATTAINABLE.**  A theoretical
        bound is frequently reachable, and reaching it is optimal, not a
        failure.  A strict bound then reports red on the best possible result:
        a randomized-Hadamard rotation maps a coordinate spike to exactly
        ±1/sqrt(d), the information-theoretic floor for max|coord|, so
        `lo=1/sqrt(d)` rejected a perfect rotation and blocked a run.  Ask of
        each edge: can the subject legitimately sit exactly here?  If yes, make
        it inclusive.
        """
        lo_ok = (lo <= value) if lo_inclusive else (lo < value)
        hi_ok = (value <= hi) if hi_inclusive else (value < hi)
        lo_op = "<=" if lo_inclusive else "<"
        hi_op = "<=" if hi_inclusive else "<"
        suffix = f" — {why}" if why else ""
        return self.check(lo_ok and hi_ok, label,
                          f"{lo:.6g} {lo_op} {value:.6g} {hi_op} {hi:.6g}{suffix}",
                          kind="bracket")

    def known_bad(self, label: str, *, rejected: bool, detail: str = "",
                  covers: tuple[str, ...] = ()) -> bool:
        """Register a case the gate MUST reject, and whether it did.

        Build the bad case out of the same machinery the real subject uses and
        break it the way it would plausibly break — an under-trained model, a
        dropped term, an off-by-one — not a nonsense input that anything would
        catch.  A known-bad that is too obviously bad certifies nothing.

        **Validate it at the configuration it will actually run in.**  A
        known-bad tuned on a small/fast setting can stop being bad at full
        size: an "untrained" grid built from one Lloyd iteration was genuinely
        zero-gain at m=2/K=16 and earned a real +0.10 dB at m=8/K=65536, where
        a single iteration relocates ~63,000 empty cells toward the mode.  It
        passed the fast gate and certified nothing about the real one.

        `covers` names the check labels (or substrings of them) this case
        exercises.  Supplying it turns "we have a known-bad" into "we know
        WHICH checks have been shown to fire", which is a different and much
        stronger claim — see `report()`.
        """
        return self.check(rejected, label, detail, kind="known-bad",
                          covers=tuple(covers))

    def note(self, text: str) -> None:
        """Record a number worth seeing that is not itself pass/fail."""
        self.notes.append(text)

    def coverage(self, text: str) -> None:
        """Record something this gate CANNOT catch.

        Coverage holes are invisible from inside a green run, so they have to
        be asserted by the author.  Anchors that stop short of the range you
        operate in belong here.
        """
        self.limits.append(text)

    # -- reporting ---------------------------------------------------------

    @property
    def failures(self) -> list[_Check]:
        return [c for c in self.checks if not c.ok]

    @property
    def known_bads(self) -> list[_Check]:
        return [c for c in self.checks if c.kind == "known-bad"]

    def report(self) -> int:
        """Print the result; return 0 to pass, 1 to fail, 2 if inconclusive."""
        w = self.stream
        line = "=" * 74
        print(f"{line}\nGATE — {self.name}\n{line}", file=w)
        for c in self.checks:
            tag = "PASS" if c.ok else "FAIL"
            print(f"  [{tag}] ({c.kind}) {c.label}"
                  + (f": {c.detail}" if c.detail else ""), file=w)
        for n in self.notes:
            print(f"  [note] {n}", file=w)
        for lim in self.limits:
            print(f"  [cannot catch] {lim}", file=w)

        if self.failures:
            print(f"\nFAILED — {len(self.failures)} check(s):", file=w)
            for c in self.failures:
                print(f"  * {c.label}: {c.detail}", file=w)
            return 1
        if not self.known_bads:
            print("\nINCONCLUSIVE — every check passed and no known-bad case was "
                  "registered.\nA gate that was never shown to reject anything has "
                  "not been shown to work.\nAdd g.known_bad(...) with a case its "
                  "own criteria must catch.", file=w)
            return 2
        if not self.limits:
            print("\nINCONCLUSIVE — no coverage limit recorded. State at least one "
                  "thing\nthis gate cannot catch (g.coverage(...)); if you truly "
                  "believe there is\nnothing, say that explicitly.", file=w)
            return 2
        # Known-bad REACH.  "We have a known-bad" and "we know which checks
        # have been shown to fire" are different claims, and only the second
        # is worth much.  An audit of a real gate found its single known-bad
        # exercised 1 of 8 checks -- and the check the whole result rested on
        # ACCEPTED the same bad case.  That gate reported PASS.
        substantive = [c for c in self.checks if c.kind != "known-bad"]
        if any(kb.covers for kb in self.known_bads):
            claimed = [t for kb in self.known_bads for t in kb.covers]
            reached = {c.label for c in substantive
                       if any(t in c.label for t in claimed)}
            unreached = [c.label for c in substantive if c.label not in reached]
            print(f"\n  known-bad reach: {len(reached)}/{len(substantive)} "
                  f"checks exercised by a known-bad", file=w)
            for lab in unreached[:12]:
                print(f"    [unreached] {lab}", file=w)
            if len(unreached) > 12:
                print(f"    ... and {len(unreached) - 12} more", file=w)
        else:
            print(f"\n  known-bad reach: UNDECLARED — {len(self.known_bads)} "
                  f"known-bad(s), none naming the checks they exercise.\n"
                  f"  Pass covers=(...) to known_bad() to turn 'we have one' "
                  f"into 'we know which checks fire'.", file=w)

        print(f"\nPASSED — {len(self.checks)} checks, "
              f"{len(self.known_bads)} known-bad rejected, "
              f"{len(self.limits)} coverage limit(s) stated.", file=w)
        return 0


__all__ = ["Gate"]
