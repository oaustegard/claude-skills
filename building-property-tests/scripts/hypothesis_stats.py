#!/usr/bin/env python3
"""Run a Hypothesis suite and check how often each generated class occurred.

    hypothesis_stats.py [--min LABEL=PCT ...] [--test REGEX] [--json]
                        [--allow-test-failures] -- pytest -q test_props.py

Adds ``--hypothesis-show-statistics`` to the command when it is missing, reads
the "Events:" block of each test's generate phase, and reports the share of
generated test cases in which each ``hypothesis.event(label)`` fired.
Hypothesis's own bookkeeping events ("Retried draw ...", "Aborted test
because ...", "gave up because ...") are dropped.

``--min LABEL=PCT`` (repeatable) fails the run when, in any test matched by
``--test`` (default: every test that reported events), no event whose label
matches the regex LABEL reached PCT percent. A class that never fired reads as
0%, which is the case this exists to catch: a generator that never produced
the interaction under test. Emit one event per class you gate on; shares of
different labels are not summed, because one test case can fire several.

Exit codes: 0 all thresholds met; 1 a threshold missed; 2 no statistics
could be parsed, or the suite failed and --allow-test-failures was not given.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

TEST_HEADER = re.compile(r"^(\S+::\S+):\s*$")
PHASE = re.compile(r"^\s*- during (\w+) phase")
EVENT = re.compile(r"^\s*\* ([\d.]+)%, (.+?)\s*$")
INTERNAL = ("Retried draw", "Aborted test because", "gave up because")

Stats = Dict[str, Dict[str, float]]


def parse(text: str) -> Stats:
    """Map each test id to {event label: percent} from its generate phase.

    Args:
        text: pytest output containing a Hypothesis Statistics section.
    Returns:
        {test_id: {label: percent}}; tests with no events map to {}.
    """
    stats: Stats = {}
    test: Optional[str] = None
    phase: Optional[str] = None
    in_stats = False
    for line in text.splitlines():
        if "Hypothesis Statistics" in line:
            in_stats = True
            continue
        if not in_stats:
            continue
        m = TEST_HEADER.match(line)
        if m:
            test, phase = m.group(1), None
            stats.setdefault(test, {})
            continue
        m = PHASE.match(line)
        if m:
            phase = m.group(1)
            continue
        m = EVENT.match(line)
        if m and test is not None and phase == "generate":
            label = m.group(2)
            if not label.startswith(INTERNAL):
                stats[test][label] = float(m.group(1))
    return stats


def check(stats: Stats, mins: List[Tuple[str, float]],
          test_filter: Optional[str]) -> List[str]:
    """Return one message per (test, threshold) that was not met."""
    misses = []
    for test, events in sorted(stats.items()):
        if test_filter and not re.search(test_filter, test):
            continue
        if not test_filter and not events:
            continue
        for pattern, floor in mins:
            matching = {k: v for k, v in events.items() if re.search(pattern, k)}
            best = max(matching.values(), default=0.0)
            if best < floor:
                seen = ", ".join(f"{k}={v:g}%" for k, v in sorted(matching.items())) or "never fired"
                misses.append(f"{test}: /{pattern}/ best {best:g}% < {floor:g}% ({seen})")
    return misses


def parse_min(spec: str) -> Tuple[str, float]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--min wants LABEL=PCT, got {spec!r}")
    label, pct = spec.rsplit("=", 1)
    try:
        return label, float(pct.rstrip("%"))
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--min {spec!r}: {e}") from e


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print("usage: hypothesis_stats.py [options] -- pytest ...", file=sys.stderr)
        return 2
    cut = argv.index("--")
    ap = argparse.ArgumentParser(prog="hypothesis_stats.py")
    ap.add_argument("--min", action="append", type=parse_min, default=[])
    ap.add_argument("--test", default=None, help="regex over test ids the --min checks apply to")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow-test-failures", action="store_true")
    args = ap.parse_args(argv[:cut])
    cmd = argv[cut + 1:]
    if not cmd:
        print("no command after --", file=sys.stderr)
        return 2
    if "--hypothesis-show-statistics" not in cmd:
        cmd = cmd + ["--hypothesis-show-statistics"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stats = parse(proc.stdout)
    if not stats:
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        print("no Hypothesis statistics parsed: is this a Hypothesis suite, "
              "and did pytest collect it?", file=sys.stderr)
        return 2
    misses = check(stats, args.min, args.test)
    if args.json:
        print(json.dumps({"returncode": proc.returncode, "events": stats,
                          "misses": misses}, indent=2))
    else:
        for test, events in sorted(stats.items()):
            print(test)
            for label, pct in sorted(events.items(), key=lambda kv: -kv[1]):
                print(f"  {pct:6.2f}%  {label}")
        for m in misses:
            print(f"BELOW FLOOR  {m}")
    if proc.returncode != 0 and not args.allow_test_failures:
        print(f"suite exited {proc.returncode}; rerun with --allow-test-failures "
              f"to check coverage of a failing suite", file=sys.stderr)
        return 2
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
