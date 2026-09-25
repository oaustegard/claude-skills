#!/usr/bin/env python3
"""Look at a recording: CQT spectrogram (note axis) + pYIN lead line + chroma, and save the features.

  python3 spectrogram.py take.wav --out take.png [--start 0 --dur 25] [--from-onset]
          [--pyin-floor G3 --pyin-ceiling C6] [--label "v3"] [--t0 57]

Writes take.png (read it with the image viewer) and take.npz with D (dB, 60 semitone bins from
C2, ref=max, top_db=80), f0 (Hz per frame, NaN = unvoiced), chroma, times.
--from-onset  measures --start from the first non-silent sample (aligns renders that start late)
--pyin-floor  set it just under the melody's lowest note: a floor at C3 under a loud bass makes
              pYIN pick the bass's upper partials an octave below the tune.
"""

import argparse

import librosa
import librosa.display
import matplotlib
import numpy as np
import soundfile as sf

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("wav")
ap.add_argument("--out", required=True)
ap.add_argument("--start", type=float, default=0.0)
ap.add_argument("--dur", type=float, default=None)
ap.add_argument("--from-onset", action="store_true")
ap.add_argument("--pyin-floor", default="C3")
ap.add_argument("--pyin-ceiling", default="C6")
ap.add_argument("--label", default=None)
ap.add_argument(
    "--t0",
    type=float,
    default=0.0,
    help="value shown at the left edge of the time axis",
)
ap.add_argument(
    "--clip", action="store_true", help="clip to [-1, 1] first, as the sound card would"
)
a = ap.parse_args()

x, sr = sf.read(a.wav, always_2d=True)
if a.clip:
    x = np.clip(x, -1, 1)
m = x.mean(axis=1)
off = 0.0
if a.from_onset:
    nz = np.flatnonzero(np.abs(m) > 1e-3)
    off = nz[0] / sr if len(nz) else 0.0
s0 = int((off + a.start) * sr)
s1 = len(m) if a.dur is None else s0 + int(a.dur * sr)
y = librosa.resample(m[s0:s1], orig_sr=sr, target_sr=22050)
sr = 22050
hop = 512
fmin = librosa.note_to_hz("C2")
D = librosa.amplitude_to_db(
    np.abs(
        librosa.cqt(y, sr=sr, hop_length=hop, fmin=fmin, n_bins=60, bins_per_octave=12)
    ),
    ref=np.max,
    top_db=80,
)
f0, _, _ = librosa.pyin(
    y,
    sr=sr,
    hop_length=hop,
    fmin=librosa.note_to_hz(a.pyin_floor),
    fmax=librosa.note_to_hz(a.pyin_ceiling),
)
chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
times = librosa.times_like(D, sr=sr, hop_length=hop) + a.t0
np.savez(a.out.rsplit(".", 1)[0] + ".npz", D=D, f0=f0, chroma=chroma, times=times)

fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
gs = fig.add_gridspec(
    2,
    1,
    height_ratios=[3, 1],
    hspace=0.14,
    left=0.05,
    right=0.99,
    top=0.95,
    bottom=0.07,
)
ax = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1], sharex=ax)
librosa.display.specshow(
    D,
    sr=sr,
    hop_length=hop,
    x_axis="time",
    y_axis="cqt_note",
    fmin=fmin,
    bins_per_octave=12,
    ax=ax,
    cmap="magma",
    x_coords=times,
)
ax.plot(times, f0, color="#3ce6ff", lw=2, label="lead pitch (pYIN)")
ax.legend(loc="upper right")
ax.set_title(a.label or a.wav)
ax.set_xlabel("")
librosa.display.specshow(
    chroma,
    sr=sr,
    hop_length=hop,
    x_axis="time",
    y_axis="chroma",
    ax=ax2,
    cmap="viridis",
    x_coords=times,
)
ax2.set_xlabel("Time (s)")
fig.savefig(a.out)
voiced = np.mean(~np.isnan(f0))
print(
    f"saved {a.out} (+ .npz); {len(y) / sr:.1f} s from {off + a.start:.2f} s; pYIN voiced {voiced:.0%}"
)
