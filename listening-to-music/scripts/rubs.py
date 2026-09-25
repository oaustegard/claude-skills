#!/usr/bin/env python3
"""Audio-side semitone-rub meter: the recording's counterpart to clashes.py.

  python3 rubs.py take.wav [more.wav ...] [--lo C3 --hi C6]
  python3 rubs.py --pair before1.wav after1.wav --pair before2.wav after2.wav

Per frame: CQT at 3 bins per semitone between --lo and --hi, spectral peaks within 30 dB of the
frame maximum, each snapped to its semitone. For every pair of peaks exactly 1 or 13 semitones
apart, add the weaker peak's amplitude, divided by the frame's total peak amplitude. The result
is the fraction of tonal energy that sits in semitone/minor-ninth rubs. Unlike roughness it
ignores broadband drums and does not let a loud bass drone swamp a pad.
"""

import argparse
import sys

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import find_peaks


def track(path, lo="C3", hi="C6", hop=1024):
    x, sr = sf.read(path, always_2d=True)
    y = librosa.resample(x.mean(axis=1), orig_sr=sr, target_sr=22050)
    sr = 22050
    fmin = librosa.note_to_hz(lo)
    n = 3 * (librosa.note_to_midi(hi) - librosa.note_to_midi(lo))
    C = np.abs(
        librosa.cqt(y, sr=sr, hop_length=hop, fmin=fmin, n_bins=n, bins_per_octave=36)
    )
    base = librosa.note_to_midi(lo)
    out = []
    for col in C.T:
        if col.max() <= 0:
            out.append(np.nan)
            continue
        p, _ = find_peaks(col, height=col.max() * 10 ** (-30 / 20))
        if len(p) < 2:
            out.append(0.0)
            continue
        semi = np.round(base + p / 3).astype(int)
        amp = col[p]
        best = {}
        for s_, a_ in zip(semi, amp):
            best[s_] = max(best.get(s_, 0), a_)
        ks = sorted(best)
        r = 0.0
        for i, s1 in enumerate(ks):
            for s2 in ks[i + 1 :]:
                if s2 - s1 in (1, 13):
                    r += min(best[s1], best[s2])
        out.append(r / sum(best.values()))
    return np.array(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("wavs", nargs="*")
    ap.add_argument("--lo", default="C3")
    ap.add_argument("--hi", default="C6")
    ap.add_argument("--pair", nargs=2, action="append", metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()
    if a.pair:
        mb, ma = [], []
        for b, af in a.pair:
            vb, va = np.nanmean(track(b, a.lo, a.hi)), np.nanmean(track(af, a.lo, a.hi))
            mb.append(vb)
            ma.append(va)
            print(
                f"{b} -> {af}: rub share {vb:.3f} -> {va:.3f} ({100 * (va - vb) / vb:+.0f}%)"
            )
        B, A = np.mean(mb), np.mean(ma)
        spread = max(np.ptp(mb), np.ptp(ma)) if len(mb) > 1 else float("nan")
        print(
            f"mean: before {B:.3f}, after {A:.3f}, change {100 * (A - B) / B:+.0f}%; take-to-take spread {spread:.3f}"
            + (
                "  (change is within the spread: no reliable difference)"
                if abs(A - B) <= spread
                else ""
            )
        )
        sys.exit(0)
    for w in a.wavs:
        print(f"{w}: rub share {np.nanmean(track(w, a.lo, a.hi)):.3f}")
