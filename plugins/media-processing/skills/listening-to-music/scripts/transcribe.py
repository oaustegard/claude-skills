#!/usr/bin/env python3
"""Transcribe a recording's melody (and optionally its bass) into note events.

  python3 transcribe.py take.wav --out melody.json --bpm 115 [--offset onset|<seconds>]
          [--floor G3 --ceiling C6] [--bass] [--beats 4] [--min-note 0.08]

pYIN pitch track -> median-smoothed semitones -> notes (runs of one semitone lasting at least
--min-note seconds, rests where unvoiced) -> times in bars from --offset (the downbeat of bar 1;
`onset` = first non-silent sample). Without --bpm, librosa's beat tracker guesses the tempo;
check it against the spectrogram, because a half- or double-time guess puts every note in the
wrong bar.

Monophonic by design: one melody line (and one bass line with --bass, pYIN on the band
C1-C3). Chords and inner voices are not transcribed; read them from the chroma or the score of
the generating code instead. Output feeds score.py, compare_notes.py and to_strudel.py.
"""

import argparse
import itertools

import librosa
import numpy as np
import soundfile as sf
from notes import save


def line(y, sr, hop, floor, ceiling, min_note, layer, onsets, gap=0.15, split=True):
    f0, _, _ = librosa.pyin(
        y,
        sr=sr,
        hop_length=hop,
        fmin=librosa.note_to_hz(floor),
        fmax=librosa.note_to_hz(ceiling),
    )
    m = np.where(np.isnan(f0), np.nan, librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0)))
    k = 5  # median filter over ~115 ms keeps vibrato and scoops from splitting notes
    sm = np.array(
        [
            np.nanmedian(m[max(0, i - k // 2) : i + k // 2 + 1])
            if not np.isnan(m[i])
            else np.nan
            for i in range(len(m))
        ]
    )
    semi = np.where(np.isnan(sm), -1, np.round(sm)).astype(int)
    dt = hop / sr
    runs, start = [], 0
    for i in range(1, len(semi) + 1):
        if i == len(semi) or semi[i] != semi[start]:
            runs.append([start * dt, i * dt, int(semi[start])])
            start = i
    # a short voiced run just before a note within 2 semitones is its scoop or glide: fold it in
    for i in range(len(runs) - 2, -1, -1):
        r, nxt = runs[i], runs[i + 1]
        if (
            r[2] >= 0
            and nxt[2] >= 0
            and r[1] - r[0] < 1.5 * min_note
            and abs(r[2] - nxt[2]) <= 2
        ):
            nxt[0] = r[0]
            r[2] = -1
    notes = [r for r in runs if r[2] >= 0 and r[1] - r[0] >= min_note]
    # the same pitch interrupted by a short unvoiced gap (a drum hit, a breath) is one note
    merged = []
    for r in notes:
        if merged and merged[-1][2] == r[2] and r[0] - merged[-1][1] <= gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    # a repeated note has no unvoiced gap between strikes: split where the note's own pitch
    # gets at least 6 dB louder at an onset (other parts' onsets and echoes don't qualify)
    if split:
        C = librosa.amplitude_to_db(
            np.abs(
                librosa.cqt(
                    y, sr=sr, hop_length=hop, fmin=librosa.note_to_hz("C1"), n_bins=96
                )
            )
        )
        cut = []
        for r in merged:
            b = r[2] - 24  # bin of this MIDI note (C1 = 24)
            edges = [r[0]]
            for t in onsets[(onsets > r[0] + min_note) & (onsets < r[1] - min_note)]:
                i = int(t / dt)
                if (
                    0 <= b < C.shape[0]
                    and i + 3 < C.shape[1]
                    and C[b, i + 1 : i + 4].max() - C[b, max(i - 3, 0) : i].min() >= 6
                ):
                    edges.append(float(t))
            edges.append(r[1])
            cut += [[s0, s1, r[2]] for s0, s1 in itertools.pairwise(edges)]
        merged = cut
    # start each note at the detected onset just before it (pitch settles after the attack)
    for r in merged:
        before = onsets[(onsets <= r[0] + 0.02) & (onsets >= r[0] - 0.16)]
        if len(before):
            r[0] = float(before[-1])
    return [(r[0], r[1], r[2], layer) for r in merged]


ap = argparse.ArgumentParser()
ap.add_argument("wav")
ap.add_argument("--out", required=True)
ap.add_argument("--bpm", type=float)
ap.add_argument("--beats", type=int, default=4)
ap.add_argument("--offset", default="onset")
ap.add_argument("--floor", default="G3")
ap.add_argument("--ceiling", default="C6")
ap.add_argument("--bass", action="store_true")
ap.add_argument("--min-note", type=float, default=0.08)
ap.add_argument(
    "--no-split",
    action="store_true",
    help="do not split held pitches at re-attacks (echo-heavy leads)",
)
a = ap.parse_args()

x, sr0 = sf.read(a.wav, always_2d=True)
y = librosa.resample(x.mean(axis=1), orig_sr=sr0, target_sr=22050)
sr, hop = 22050, 256
if a.offset == "onset":
    nz = np.flatnonzero(np.abs(y) > 1e-3)
    offset = nz[0] / sr if len(nz) else 0.0
else:
    offset = float(a.offset)
bpm = a.bpm
if not bpm:
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    print(f"tempo guess {bpm:.1f} BPM (pass --bpm to override)")
bar = a.beats * 60 / bpm
onsets = librosa.onset.onset_detect(
    y=y, sr=sr, hop_length=hop, units="time", backtrack=True
)
found = line(
    y, sr, hop, a.floor, a.ceiling, a.min_note, "melody", onsets, split=not a.no_split
)
if a.bass:
    found += line(
        y,
        sr,
        hop,
        "C1",
        "C3",
        max(a.min_note, 0.12),
        "bass",
        onsets,
        gap=0.4,
        split=False,
    )
events = [
    {"layer": L, "t0": (t0 - offset) / bar, "t1": (t1 - offset) / bar, "midi": mm}
    for t0, t1, mm, L in found
    if t1 > offset
]
save(a.out, events, cycles=(len(y) / sr - offset) / bar, beats=a.beats, bpm=bpm)
by = {}
for e in events:
    by[e["layer"]] = by.get(e["layer"], 0) + 1
print(
    f"{a.out}: {', '.join(f'{k} {v} notes' for k, v in by.items())}; bar = {bar:.3f} s from {offset:.3f} s"
)
