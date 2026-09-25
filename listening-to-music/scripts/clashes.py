#!/usr/bin/env python3
"""Note-level clash scan: which simultaneous notes rub, in which layers, and how often.

  node render_strudel.mjs code.js --events ev.json --cycles 16
  python3 clashes.py ev.json [--key d:ionian] [--worst 8]

Input: {"cycles": N, "events": [{"layer", "t0", "t1", "midi"}, ...]} (times in cycles). A
generator can write the same format from its own note data (e.g. a page's test hook).
Harsh = a minor 2nd or minor 9th between two sounding notes, or a major 7th with its lower note
below middle C. Reported as bar-lengths of overlap per cycle, by layer pair (a layer against
itself = a rub inside the voicing). --key also reports time spent on notes outside the key.

For harmony this is the precise instrument; roughness from the audio is the confirmation.
"""

import argparse
import collections
import json

MODES = {
    "ionian": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "aeolian": [0, 2, 3, 5, 7, 8, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}
PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def nm(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


ap = argparse.ArgumentParser()
ap.add_argument("events")
ap.add_argument("--key")
ap.add_argument("--worst", type=int, default=8)
a = ap.parse_args()
with open(a.events) as fh:
    D = json.load(fh)
ev = D["events"]
cycles = D.get("cycles") or max(e["t1"] for e in ev)
harsh = collections.Counter()
worst = []
ev = sorted(ev, key=lambda e: e["t0"])
for i, e1 in enumerate(ev):
    for e2 in ev[i + 1 :]:
        if e2["t0"] >= e1["t1"]:
            break
        ov = min(e1["t1"], e2["t1"]) - max(e1["t0"], e2["t0"])
        if ov <= 1e-9:
            continue
        d = abs(e1["midi"] - e2["midi"])
        if d in (1, 13) or (d == 11 and min(e1["midi"], e2["midi"]) < 60):
            pair = " × ".join(sorted([e1["layer"], e2["layer"]]))
            kind = {1: "m2", 13: "m9", 11: "M7 low"}[d]
            harsh[(pair, kind)] += ov
            worst.append(
                (
                    ov,
                    max(e1["t0"], e2["t0"]),
                    pair,
                    kind,
                    nm(e1["midi"]),
                    nm(e2["midi"]),
                )
            )
tot = sum(harsh.values())
print(
    f"harsh overlap: {tot / cycles:.3f} bar-lengths per cycle over {cycles} cycles, {len(ev)} notes"
)
for (pair, kind), v in harsh.most_common():
    print(f"  {v / cycles:.3f}  {pair:28s} {kind}")
if a.key:
    t, mode = a.key.lower().split(":")
    tonic = PC[t[0]] + (1 if t[1:] in ("#", "s") else -1 if t[1:] == "b" else 0)
    sc = {(tonic + x) % 12 for x in MODES[mode]}
    out = collections.Counter()
    for e in ev:
        if e["midi"] % 12 not in sc:
            out[e["layer"]] += e["t1"] - e["t0"]
    print(
        "out of key:",
        ", ".join(f"{k} {v / cycles:.3f}" for k, v in out.most_common()) or "none",
    )
if worst:
    print("longest clashes (cycle position, pair, notes):")
    for ov, t, pair, kind, n1, n2 in sorted(worst, reverse=True)[: a.worst]:
        print(f"  at {t:7.3f}  {ov:.3f} long  {pair:24s} {kind:6s} {n1}-{n2}")
