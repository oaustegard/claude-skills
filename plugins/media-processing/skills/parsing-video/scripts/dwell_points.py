#!/usr/bin/env python3
"""Find dwell points — the moments where the camera settles between moves.

Computes a frame-difference (motion) signal at low resolution and rate,
smooths it, and locates sustained valleys: spans whose motion stays below
a relative threshold. Camera moves (pans, zooms, shakes) are the peaks
between those valleys; the valley midpoints are sharp, deliberately
composed frames — the best tiles for a contact sheet.

Prints dwell midpoints comma-separated on stdout, ready for
contact_sheet.py --at. Diagnostics go to stderr.

Usage:
    python3 dwell_points.py input.mp4
    python3 contact_sheet.py input.mp4 --at "$(python3 dwell_points.py input.mp4 --max 16)"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys


def motion_signal(path: str, fps: float, width: int) -> tuple[list[float], list[float]]:
    """Return (times, scores): per-sample frame-difference scores at the analysis rate.

    Decodes at reduced rate/resolution; scores come from ffmpeg's scene
    metric (0–1 normalized frame-pair difference).
    """
    cmd = [
        "ffmpeg", "-v", "error", "-i", path,
        "-vf", f"fps={fps},scale={width}:-2,select='gte(scene,0)',metadata=print:file=-",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("ffmpeg not found — install it first (apt-get install -y ffmpeg)")
    if proc.returncode != 0:
        sys.exit(f"ffmpeg analysis failed: {proc.stderr.strip()}")

    times: list[float] = []
    scores: list[float] = []
    t: float | None = None
    for line in proc.stdout.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([0-9.eE+-]+)", line)
        if m and t is not None:
            times.append(t)
            scores.append(float(m.group(1)))
            t = None
    # First sample has no predecessor; its score is meaningless.
    return times[1:], scores[1:]


def smooth(values: list[float], window: int) -> list[float]:
    """Centered moving average with the given window size."""
    if window <= 1:
        return values
    half = window // 2
    out = []
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def percentile(values: list[float], pct: float) -> float:
    """Return the pct-th percentile (linear interpolation)."""
    s = sorted(values)
    k = (len(s) - 1) * pct / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def hms(seconds: float) -> str:
    """Format seconds as H:MM:SS."""
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def find_dwells(times: list[float], scores: list[float], thr: float,
                min_dwell: float, merge_gap: float) -> list[tuple[float, float]]:
    """Return (start, end) spans where the smoothed motion stays at or below thr."""
    spans: list[tuple[float, float]] = []
    run_start: float | None = None
    for t, s in zip(times, scores):
        if s <= thr:
            if run_start is None:
                run_start = t
        elif run_start is not None:
            spans.append((run_start, t))
            run_start = None
    if run_start is not None:
        spans.append((run_start, times[-1]))

    merged: list[tuple[float, float]] = []
    for span in spans:
        if merged and span[0] - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], span[1])
        else:
            merged.append(span)
    return [(a, b) for a, b in merged if b - a >= min_dwell]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="video file")
    ap.add_argument("--max", type=int, default=16,
                    help="keep at most this many dwells, longest first (default 16)")
    ap.add_argument("--min-dwell", type=float, default=1.0,
                    help="minimum hold duration in seconds to count as a dwell (default 1.0)")
    ap.add_argument("--percentile", type=float, default=40.0,
                    help="motion threshold as a percentile of the signal (default 40; "
                         "relative, so it adapts to how much the footage moves overall)")
    ap.add_argument("--fps", type=float, default=4.0, help="analysis sample rate (default 4)")
    ap.add_argument("--width", type=int, default=160, help="analysis frame width (default 160)")
    ap.add_argument("--smooth", type=float, default=1.0,
                    help="smoothing window in seconds (default 1.0)")
    ap.add_argument("--merge-gap", type=float, default=0.5,
                    help="merge dwells separated by gaps shorter than this (default 0.5)")
    args = ap.parse_args()

    times, scores = motion_signal(args.input, args.fps, args.width)
    if len(times) < 3:
        sys.exit("video too short for motion analysis — use uniform sampling")

    smoothed = smooth(scores, max(1, round(args.smooth * args.fps)))
    thr = percentile(smoothed, args.percentile)
    dwells = find_dwells(times, smoothed, thr, args.min_dwell, args.merge_gap)
    if not dwells:
        sys.exit("no dwells found (constant motion?) — use uniform sampling instead")

    dwells = sorted(sorted(dwells, key=lambda d: d[1] - d[0], reverse=True)[:args.max])
    print(f"{args.input}: {len(dwells)} dwell(s), motion threshold {thr:.4f} "
          f"(p{args.percentile:g} of smoothed signal)", file=sys.stderr)
    for a, b in dwells:
        print(f"  {hms(a)} – {hms(b)}  ({b - a:.1f}s hold) → sample at {hms((a + b) / 2)}",
              file=sys.stderr)
    print(",".join(f"{(a + b) / 2:.2f}" for a, b in dwells))


if __name__ == "__main__":
    main()
