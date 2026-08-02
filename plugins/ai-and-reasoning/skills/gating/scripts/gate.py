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


@dataclass
class Gate:
    """Collects checks, then reports and returns a process exit code."""

    name: str = "gate"
    checks: list[_Check] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    stream = sys.stdout

    # -- primitives --------------------------------------------------------

    def check(self, ok: bool, label: str, detail: str = "", *, kind: str = "check") -> bool:
        """Record a plain boolean check."""
        self.checks.append(_Check(bool(ok), label, detail, kind))
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
                why: str = "") -> bool:
        """Assert lo < value < hi.

        Two-sided by construction.  A one-sided check passes for a value that
        collapsed as readily as for one that is right, which is how an
        implementation that silently does nothing gets certified.
        """
        ok = lo < value < hi
        suffix = f" — {why}" if why else ""
        return self.check(ok, label,
                          f"{lo:.6g} < {value:.6g} < {hi:.6g}{suffix}",
                          kind="bracket")

    def known_bad(self, label: str, *, rejected: bool, detail: str = "") -> bool:
        """Register a case the gate MUST reject, and whether it did.

        Build the bad case out of the same machinery the real subject uses and
        break it the way it would plausibly break — an under-trained model, a
        dropped term, an off-by-one — not a nonsense input that anything would
        catch.  A known-bad that is too obviously bad certifies nothing.
        """
        return self.check(rejected, label, detail, kind="known-bad")

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
        print(f"\nPASSED — {len(self.checks)} checks, "
              f"{len(self.known_bads)} known-bad rejected, "
              f"{len(self.limits)} coverage limit(s) stated.", file=w)
        return 0


__all__ = ["Gate"]
