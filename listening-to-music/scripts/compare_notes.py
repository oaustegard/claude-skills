#!/usr/bin/env python3
"""Compare two sets of notes: a reference (a score, the generating code) against a candidate
(a transcription, a render, an OMR read).

  python3 compare_notes.py ref.json cand.json [--ref-layer LEAD] [--cand-layer melody]
          [--bars 1-8] [--onset-tol 0.05] [--octave-free]

Scores with mir_eval's transcription metrics: a candidate note matches a reference note when
its onset is within --onset-tol bars and its pitch within 50 cents. Prints precision, recall
and F1 without and with offsets (offset within 20% of the note or 0.05 bars), then the
unmatched notes so they can be looked up in the score.
--octave-free  folds both sides into one octave first (use when pYIN picks the wrong octave).
--align N      searches shifts of up to N bars for the candidate (unknown downbeat); prints the shift.
"""

import argparse

import mir_eval
import numpy as np
from notes import load

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def pick(d, layer, bars):
    ev = [
        e
        for e in d["events"]
        if (layer is None or e["layer"] == layer) and e["t0"] >= 0
    ]
    if bars:
        lo, hi = (int(x) for x in bars.split("-"))
        ev = [e for e in ev if lo - 1 <= e["t0"] < hi]
    ev.sort(key=lambda e: e["t0"])
    iv = np.array([[e["t0"], max(e["t1"], e["t0"] + 1e-3)] for e in ev]).reshape(-1, 2)
    return iv, np.array([e["midi"] for e in ev]), ev


ap = argparse.ArgumentParser()
ap.add_argument("ref")
ap.add_argument("cand")
ap.add_argument("--ref-layer")
ap.add_argument("--cand-layer")
ap.add_argument("--bars")
ap.add_argument("--onset-tol", type=float, default=0.05)
ap.add_argument("--octave-free", action="store_true")
ap.add_argument(
    "--align", type=float, default=0, help="search a time shift of up to this many bars"
)
a = ap.parse_args()

ri, rp, rev = pick(load(a.ref), a.ref_layer, a.bars)
cd = load(a.cand)
if a.octave_free:
    rp = 60 + rp % 12


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


if a.align:
    # the candidate's downbeat is unknown (a recording that starts mid-loop): try shifts on a
    # 1/32-bar lattice and keep the one with the most onset+pitch matches
    best = (-1, 0.0)
    for k in range(-int(a.align * 32), int(a.align * 32) + 1):
        sh = k / 32
        iv, ps, _ = pick(
            {
                "events": [
                    {**e, "t0": e["t0"] + sh, "t1": e["t1"] + sh} for e in cd["events"]
                ]
            },
            a.cand_layer,
            a.bars,
        )
        if a.octave_free:
            ps = 60 + ps % 12
        if len(ps) == 0:
            continue
        n = len(
            mir_eval.transcription.match_notes(
                ri, hz(rp), iv, hz(ps), onset_tolerance=a.onset_tol, offset_ratio=None
            )
        )
        if n > best[0]:
            best = (n, sh)
    print(f"aligned: shifted candidate by {best[1]:+.3f} bars")
    cd = {
        **cd,
        "events": [
            {**e, "t0": e["t0"] + best[1], "t1": e["t1"] + best[1]}
            for e in cd["events"]
        ],
    }
ci, cp, cev = pick(cd, a.cand_layer, a.bars)
if a.octave_free:
    cp = 60 + cp % 12
P, R, F, _ = mir_eval.transcription.precision_recall_f1_overlap(
    ri, hz(rp), ci, hz(cp), onset_tolerance=a.onset_tol, offset_ratio=None
)
P2, R2, F2, _ = mir_eval.transcription.precision_recall_f1_overlap(
    ri, hz(rp), ci, hz(cp), onset_tolerance=a.onset_tol, offset_min_tolerance=0.05
)
print(f"reference {len(rp)} notes, candidate {len(cp)} notes")
print(f"onset+pitch:        precision {P:.0%}  recall {R:.0%}  F1 {F:.0%}")
print(f"onset+pitch+offset: precision {P2:.0%}  recall {R2:.0%}  F1 {F2:.0%}")
match = mir_eval.transcription.match_notes(
    ri, hz(rp), ci, hz(cp), onset_tolerance=a.onset_tol, offset_ratio=None
)
mr, mc = {i for i, _ in match}, {j for _, j in match}


def label(e):
    return f"bar {int(e['t0']) + 1} +{e['t0'] % 1:.3f} {NAMES[e['midi'] % 12]}{e['midi'] // 12 - 1}"


miss = [label(e) for i, e in enumerate(rev) if i not in mr]
extra = [label(e) for j, e in enumerate(cev) if j not in mc]
if miss:
    print(
        "missed (in reference only):",
        "; ".join(miss[:12]) + (" ..." if len(miss) > 12 else ""),
    )
if extra:
    print(
        "extra (in candidate only): ",
        "; ".join(extra[:12]) + (" ..." if len(extra) > 12 else ""),
    )
