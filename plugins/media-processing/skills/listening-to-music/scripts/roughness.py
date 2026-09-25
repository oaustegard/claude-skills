#!/usr/bin/env python3
"""Sensory roughness (Sethares' fit of Plomp-Levelt) from the audio, frame by frame.

  python3 roughness.py before.wav [after.wav ...] [--out cmp.png] [--band 60 4000]
  python3 roughness.py --pair a1.wav b1.wav --pair a2.wav b2.wav   # replicated before/after

Each frame: the 24 strongest spectral peaks in the band, pairwise roughness summed and divided
by the frame's peak energy (level-independent). Prints median and 90th percentile per file.

Read the numbers with care:
- Drums, hats and noise textures are broadband and dominate the figure. To judge harmony,
  record with percussion and noise muted.
- One short take is noisy (samples load lazily, bars phase-shift). Use --warmup when
  recording, 40 s or more, and at least two takes per version; --pair prints the take-to-take
  spread next to the before/after change, so the change can be compared with the noise.
"""

import argparse
import sys

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import find_peaks


def track(path, band=(60, 4000), n_fft=8192, hop=2048, peaks=24):
    x, sr = sf.read(path, always_2d=True)
    x = x.mean(axis=1)
    S = np.abs(librosa.stft(x, n_fft=n_fft, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    keep = (f > band[0]) & (f < band[1])
    out = []
    for col in S.T:
        c = col * keep
        if c.max() <= 0:
            out.append(np.nan)
            continue
        p, _ = find_peaks(c, height=c.max() * 0.03)
        p = p[np.argsort(c[p])[::-1][:peaks]]
        fr, amp = f[p], c[p]
        if len(amp) < 2:
            out.append(np.nan)
            continue
        F1, F2 = np.meshgrid(fr, fr)
        A1, A2 = np.meshgrid(amp, amp)
        s = 0.24 / (0.0207 * np.minimum(F1, F2) + 18.96)
        df = np.abs(F1 - F2)
        R = A1 * A2 * (np.exp(-3.51 * s * df) - np.exp(-5.75 * s * df))
        out.append(np.triu(R, 1).sum() / (amp**2).sum())
    return np.array(out), hop / sr


def stats(r):
    r = r[~np.isnan(r)]
    return np.median(r), np.percentile(r, 90)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("wavs", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--band", nargs=2, type=float, default=[60, 4000])
    ap.add_argument("--pair", nargs=2, action="append", metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()
    band = tuple(a.band)
    if a.pair:
        med_b, med_a = [], []
        for b, af in a.pair:
            mb, _ = stats(track(b, band)[0])
            ma, _ = stats(track(af, band)[0])
            med_b.append(mb)
            med_a.append(ma)
            print(
                f"{b} -> {af}: median {mb:.3f} -> {ma:.3f} ({100 * (ma - mb) / mb:+.0f}%)"
            )
        mb, ma = np.mean(med_b), np.mean(med_a)
        spread = max(np.ptp(med_b), np.ptp(med_a)) if len(a.pair) > 1 else float("nan")
        print(
            f"mean of medians: before {mb:.3f}, after {ma:.3f}, change {100 * (ma - mb) / mb:+.0f}%; take-to-take spread {spread:.3f}"
            + (
                "  (change is within the spread: no reliable difference)"
                if abs(ma - mb) <= spread
                else ""
            )
        )
        sys.exit(0)
    tracks = []
    for w in a.wavs:
        r, dt = track(w, band)
        tracks.append((w, r, dt))
        med, p90 = stats(r)
        print(f"{w}: roughness median {med:.3f}, 90th pct {p90:.3f}")
    if a.out:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(12, 3.2), dpi=100)
        for w, r, dt in tracks:
            ax.plot(np.arange(len(r)) * dt, r, lw=1.1, label=w.rsplit("/", 1)[-1])
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("roughness")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(a.out)
        print("saved", a.out)
