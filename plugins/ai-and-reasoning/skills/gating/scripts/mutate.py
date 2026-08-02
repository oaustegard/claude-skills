#!/usr/bin/env python3
"""Break the code on purpose and see whether the gate notices.

Writing a known-bad case by hand tests the one failure you thought of.  This
tests the ones you did not: it perturbs single tokens in the target file, runs
your gate after each perturbation, and reports the mutations that **survived**
— the ones where the code changed and the gate stayed green.  Each survivor is
a behaviour nothing is currently checking.

    python3 mutate.py --target grids.py -- python3 calibrate.py
    python3 mutate.py --target src/codec.py --max 40 -- pytest -q tests/

The gate command must pass on unmutated code first; if it does not, that is
reported and nothing else runs, because survivor counts against an already-red
gate mean nothing.

Uses `tokenize`, so string literals and comments are never touched — a
regex-based mutator will happily corrupt a docstring and report a "kill" that
is really a SyntaxError.

Stdlib only.  This is the zero-dependency pass that works against ANY gate
command; for a Python test suite specifically, `mutmut` and `cosmic-ray` are
more thorough and worth reaching for once this stops finding survivors.
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

#: Operator swaps.  Each flips a decision boundary, which is where gates that
#: only ever see well-formed input tend to be blind.
OPS = {
    "==": "!=", "!=": "==",
    "<": "<=", "<=": "<", ">": ">=", ">=": ">",
    "+": "-", "-": "+", "*": "/", "//": "/",
    "and": "or", "or": "and",
    "True": "False", "False": "True",
    "is": "is not",
    "min": "max", "max": "min",
    "all": "any", "any": "all",
}


@dataclass
class Mutation:
    line: int
    col: int
    end_col: int
    before: str
    after: str

    def label(self) -> str:
        return f"line {self.line}: {self.before} -> {self.after}"


def find_mutations(src: str) -> list[Mutation]:
    """Token-level mutation sites, skipping strings, comments and numbers-in-strings."""
    out: list[Mutation] = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as e:
        raise SystemExit(f"cannot tokenize target: {e}") from e
    for tok in toks:
        if tok.type not in (tokenize.OP, tokenize.NAME, tokenize.NUMBER):
            continue
        if tok.start[0] != tok.end[0]:
            continue  # multi-line token; skip
        s = tok.string
        if tok.type == tokenize.NUMBER:
            # perturb the literal: catches thresholds and tolerances that no
            # test actually pins, which is where "slack larger than the defect"
            # lives
            try:
                after = str(int(s) + 1) if s.isdigit() else None
            except ValueError:
                after = None
            if after is None:
                continue
            out.append(Mutation(tok.start[0], tok.start[1], tok.end[1], s, after))
        elif s in OPS:
            out.append(Mutation(tok.start[0], tok.start[1], tok.end[1], s, OPS[s]))
    return out


def apply_mutation(src: str, m: Mutation) -> str:
    lines = src.splitlines(keepends=True)
    ln = lines[m.line - 1]
    lines[m.line - 1] = ln[: m.col] + m.after + ln[m.end_col :]
    return "".join(lines)


def run(cmd: list[str], timeout: int) -> tuple[bool, str]:
    """True when the gate PASSES (exit 0)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return p.returncode == 0, f"exit {p.returncode}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as e:
        return False, f"oserror {e}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Mutate a file and report which mutations the gate misses.")
    ap.add_argument("--target", action="append", required=True,
                    help="source file to mutate (repeatable)")
    ap.add_argument("--max", type=int, default=60,
                    help="cap on mutations per target (default 60)")
    ap.add_argument("--timeout", type=int, default=600,
                    help="seconds per gate run (default 600)")
    ap.add_argument("--stride", type=int, default=1,
                    help="sample every Nth site instead of the first --max")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- followed by the gate command")
    a = ap.parse_args()
    cmd = [c for c in a.cmd if c != "--"]
    if not cmd:
        ap.error("provide the gate command after --")

    ok, why = run(cmd, a.timeout)
    if not ok:
        print(f"BASELINE RED ({why}) — the gate fails on unmutated code.\n"
              f"Fix that first; survivor counts against a red gate mean nothing.")
        return 2
    print(f"baseline: gate passes on unmutated code ({' '.join(cmd)})\n")

    survivors: list[tuple[str, Mutation]] = []
    killed = 0
    for target in a.target:
        path = Path(target)
        original = path.read_text()
        sites = find_mutations(original)[:: a.stride][: a.max]
        print(f"{target}: {len(sites)} mutation sites")
        try:
            for i, m in enumerate(sites, 1):
                path.write_text(apply_mutation(original, m))
                passed, why = run(cmd, a.timeout)
                if passed:
                    survivors.append((target, m))
                    mark = "SURVIVED"
                else:
                    killed += 1
                    mark = f"killed ({why})"
                print(f"  [{i}/{len(sites)}] {m.label():<34} {mark}", flush=True)
        finally:
            path.write_text(original)  # always restore, even on Ctrl-C

    total = killed + len(survivors)
    print(f"\n{'=' * 70}")
    if not total:
        print("no mutation sites found — is the target the file the gate exercises?")
        return 2
    print(f"killed {killed}/{total}   survived {len(survivors)}/{total}")
    if survivors:
        print("\nSURVIVORS — the code changed here and the gate stayed green:")
        for target, m in survivors:
            print(f"  {target}:{m.line}  {m.before} -> {m.after}")
        print("\nEach line is a behaviour nothing currently checks. Either add a "
              "check,\nor record it under the gate's stated coverage limits.")
        return 1
    print("\nevery mutation was caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
