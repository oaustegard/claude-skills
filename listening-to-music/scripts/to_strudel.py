#!/usr/bin/env python3
"""Turn note events (from a score, a transcription, a render) into Strudel code.

  python3 to_strudel.py ref.json --out tune.js [--bpm 90] [--grid 16] [--sound piano]
          [--layers Soprano,Bass] [--bars 1-8]

Each layer becomes `$Name: note("<[bar 1] [bar 2] ...>")`, one alternation step per bar, notes
on a --grid steps-per-bar lattice (default: sixteenths) with @ weights for length and ~ for rests; simultaneous onsets
become [a,b,c]. A note held across a barline is re-struck in the next bar (mini-notation has no
tie across `< >` steps), and anything finer than the grid (triplets, grace notes) is rounded.
Round-trip check: render_strudel.mjs --events on the output, then compare_notes.py against the
input.
"""

import argparse
import re

from notes import load

NAMES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]


def nm(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def bar_tokens(evs, bar, grid):
    starts = {}
    for e in evs:
        s = round((e["t0"] - bar) * grid)
        if 0 <= s < grid:
            end = min(grid, max(s + 1, round((e["t1"] - bar) * grid)))
            starts.setdefault(s, []).append((e["midi"], end))
    if not starts:
        return "~"
    toks, pos = [], 0
    for s in sorted(starts):
        if s > pos:
            toks.append("~" if s - pos == 1 else f"~@{s - pos}")
        nxt = min([t for t in starts if t > s] + [grid])
        end = min(nxt, max(e for _, e in starts[s]))
        ms = sorted({m for m, _ in starts[s]})
        body = nm(ms[0]) if len(ms) == 1 else "[" + ",".join(nm(m) for m in ms) + "]"
        toks.append(body if end - s == 1 else f"{body}@{end - s}")
        pos = end
    if pos < grid:
        toks.append("~" if grid - pos == 1 else f"~@{grid - pos}")
    return "[" + " ".join(toks) + "]"


ap = argparse.ArgumentParser()
ap.add_argument("events")
ap.add_argument("--out", required=True)
ap.add_argument("--bpm", type=float)
ap.add_argument(
    "--grid", type=int, help="steps per bar; default 4 per beat (sixteenths)"
)
ap.add_argument("--sound", default="piano")
ap.add_argument("--layers")
ap.add_argument("--bars")
a = ap.parse_args()

d = load(a.events)
bpm = a.bpm or d.get("bpm") or 100
beats = d.get("beats", 4)
grid = a.grid or beats * 4
lo, hi = (
    (1, int(-(-d["cycles"] // 1)))
    if not a.bars
    else (int(x) for x in a.bars.split("-"))
)
names = (
    a.layers.split(",")
    if a.layers
    else list(dict.fromkeys(e["layer"] for e in d["events"]))
)
lines = [
    f"// from {a.events}: bars {lo}-{hi}, {beats}/4",
    f"setcpm({bpm:g}/{beats})",
    "",
]
for name in names:
    evs = [e for e in d["events"] if e["layer"] == name]
    bars = [bar_tokens(evs, b, grid) for b in range(lo - 1, hi)]
    label = re.sub(r"\W", "_", name)
    body = "\n  ".join(" ".join(bars[i : i + 4]) for i in range(0, len(bars), 4))
    lines.append(f'${label}: note(`<\n  {body}\n>`).s("{a.sound}").gain(.7)')
    lines.append("")
with open(a.out, "w") as fh:
    fh.write("\n".join(lines))
print(f"wrote {a.out}: {len(names)} layer(s), {hi - lo + 1} bars at {bpm:g} BPM")
