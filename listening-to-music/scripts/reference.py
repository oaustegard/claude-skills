#!/usr/bin/env python3
"""Turn a reference spectrogram IMAGE back into numbers, and score a render against it.

Use when the only reference is a picture (a screenshot of a librosa/matplotlib plot).

  # 1. find exact tick rows/cols (dark marks just outside the plot frame)
  python3 reference.py ticks ref.png --rows 46 51 --span 25 492        # y ticks: columns 46-51, rows 25-492
  python3 reference.py ticks ref.png --cols 673 679 --span 40 1275     # x ticks: rows 673-679
  # 2. decode the spectrogram panel (colormap inversion) and, optionally, a drawn pitch line
  python3 reference.py decode ref.png --box 53,31,1268,486 --y C2=486 C6=119 --x 57=51 62=295 \
          [--cmap magma] [--line 3ce6ff --ignore 1125,33,1268,58] --out ref.npz
  python3 reference.py decode-chroma ref.png --box 53,521,1268,672 --x 57=51 62=295 --out refchroma.npz
  # 3. compare with a render analysed by spectrogram.py (use --t0 there so the time axes match)
  python3 reference.py compare ref.npz take.npz [--chroma refchroma.npz]

Levels are 0..1 (0 = bottom of the colormap, 1 = top), one row per semitone C2..B6, matching
spectrogram.py's D after (D + 80) / 80. Axis ticks sit at note frequencies, so bin centres fall
on the tick rows; decoding with edges instead shifts every note by half a semitone.
"""

import argparse

import matplotlib
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_midi(s):
    s = s.strip()
    pc = NOTE[s[0].upper()]
    rest = s[1:]
    if rest and rest[0] in "#s":
        pc += 1
        rest = rest[1:]
    elif rest and rest[0] in "b":
        pc -= 1
        rest = rest[1:]
    return pc + 12 * (int(rest) + 1)


def cal(pairs, conv):
    (a, pa), (b, pb) = [(conv(k), float(v)) for k, v in (p.split("=") for p in pairs)][
        :2
    ]
    return (
        lambda px: a + (px - pa) * (b - a) / (pb - pa),
        lambda val: pa + (val - a) * (pb - pa) / (b - a),
    )


def img(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(float)


def invert(rgb, cmap):
    lut = matplotlib.colormaps[cmap](np.linspace(0, 1, 256))[:, :3] * 255
    _, i = cKDTree(lut).query(rgb.reshape(-1, 3))
    return (i / 255.0).reshape(rgb.shape[:2])


def cmd_ticks(a):
    im = img(a.image)
    if a.rows:
        band = im[a.span[0] : a.span[1], a.rows[0] : a.rows[1]].mean(axis=(1, 2))
        idx = np.flatnonzero(band < 120) + a.span[0]
    else:
        band = im[a.cols[0] : a.cols[1], a.span[0] : a.span[1]].mean(axis=(0, 2))
        idx = np.flatnonzero(band < 120) + a.span[0]
    groups = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1) if len(idx) else []
    print("tick positions:", [int(np.rint(g.mean())) for g in groups if len(g)])


def cmd_decode(a):
    im = img(a.image)
    x0, y0, x1, y1 = map(int, a.box.split(","))
    px2midi, midi2px = cal(a.y, note_midi)
    px2t, _ = cal(a.x, float)
    L = invert(im[y0:y1, x0:x1], a.cmap)
    ps = abs(midi2px(37) - midi2px(36))
    rows = []
    for k in range(60):
        c = midi2px(36 + k) - y0
        lo, hi = int(np.rint(c - ps / 2)), int(np.rint(c + ps / 2)) + 1
        lo, hi = max(lo, 0), min(hi, L.shape[0])
        rows.append(L[lo:hi].mean(axis=0) if hi > lo else np.full(L.shape[1], np.nan))
    times = np.array([px2t(x) for x in range(x0, x1)])
    out = {"L": np.array(rows), "times": times}
    if a.line:
        rgb = np.array([int(a.line[i : i + 2], 16) for i in (0, 2, 4)], float)
        near = np.linalg.norm(im[y0:y1, x0:x1] - rgb, axis=2) < a.line_tol
        for box in (
            a.ignore or []
        ):  # e.g. the legend swatch, which has the line's colour
            bx0, by0, bx1, by1 = map(int, box.split(","))
            near[
                max(by0 - y0, 0) : max(by1 - y0, 0), max(bx0 - x0, 0) : max(bx1 - x0, 0)
            ] = False
        lt, lm = [], []
        for j in range(near.shape[1]):
            yy = np.flatnonzero(near[:, j])
            if len(yy):
                lt.append(times[j])
                lm.append(px2midi(np.median(yy) + y0))
        out["line_t"], out["line_midi"] = np.array(lt), np.array(lm)
        print(
            f"pitch line: {len(lt)} columns, midi {np.min(lm):.1f}-{np.max(lm):.1f}"
            if lt
            else "pitch line: none found (check --line colour / --line-tol)"
        )
    np.savez(a.out, **out)
    print(
        f"saved {a.out}: 60 semitone rows x {L.shape[1]} columns, {times[0]:.2f}-{times[-1]:.2f} s"
    )


def cmd_decode_chroma(a):
    im = img(a.image)
    x0, y0, x1, y1 = map(int, a.box.split(","))
    px2t, _ = cal(a.x, float)
    V = invert(im[y0:y1, x0:x1], a.cmap)
    ps = V.shape[0] / 12
    ch = np.array(
        [
            V[int(V.shape[0] - ps * (k + 1)) : int(V.shape[0] - ps * k)].mean(axis=0)
            for k in range(12)
        ]
    )  # C at bottom
    np.savez(a.out, chroma=ch, times=np.array([px2t(x) for x in range(x0, x1)]))
    print("saved", a.out)


def cmd_compare(a):
    R = np.load(a.ref)
    T = np.load(a.take)
    L, rt = R["L"], R["times"]
    D = (T["D"] + 80) / 80
    tt = T["times"]
    j = np.clip(np.searchsorted(tt, rt), 0, D.shape[1] - 1)
    M = D[:, j]
    pr, pm = np.nanmean(L, axis=1), M.mean(axis=1)
    print(f"per-semitone profile RMSE {np.sqrt(np.nanmean((pr - pm) ** 2)):.3f}")
    for lo, hi, lab in (
        (0, 12, "C2-B2"),
        (12, 24, "C3-B3"),
        (24, 36, "C4-B4"),
        (36, 48, "C5-B5"),
        (48, 60, "C6-B6"),
    ):
        print(
            f"  {lab}: reference {np.nanmean(pr[lo:hi]):.2f}  take {np.mean(pm[lo:hi]):.2f}"
        )
    if "line_t" in R.files and len(R["line_t"]):
        lt, lm = R["line_t"], R["line_midi"]
        f0 = T["f0"]
        mt = np.interp(
            lt,
            tt,
            np.nan_to_num(
                12 * np.log2(np.where(np.isnan(f0), 1, f0) / 440) + 69, nan=-100
            ),
        )
        mt[np.interp(lt, tt, np.isnan(f0).astype(float)) > 0.5] = -100
        ok = np.abs(mt - lm) <= 1
        octv = np.abs(np.abs(mt - lm) - 12) <= 1
        print(
            f"melody: within 1 semitone {ok.mean():.0%}, octave errors {octv.mean():.0%}, unvoiced/other {1 - ok.mean() - octv.mean():.0%}"
        )

        # overtone test: level at the line's pitch + k semitones, relative to the frame's median in C4-B6
        def offsets(Lv, cols):
            res = []
            for off in (0, 12, 19, 24, 28, 5, 14):
                b = np.round(lm - 36).astype(int) + off
                ok_ = (b >= 0) & (b < 60)
                res.append(
                    np.nanmedian(
                        Lv[b[ok_], cols[ok_]]
                        - np.nanmedian(Lv[24:60][:, cols[ok_]], axis=0)
                    )
                )
            return res

        cr = np.clip(np.searchsorted(rt, lt), 0, L.shape[1] - 1)
        ct = np.clip(np.searchsorted(tt, lt), 0, D.shape[1] - 1)
        print(
            "overtone levels vs frame median  fund   H2    H3    H4    H5  ctl+5 ctl+14"
        )
        print(
            "  reference                    ",
            " ".join(f"{v:+.2f}" for v in offsets(L, cr)),
        )
        print(
            "  take                         ",
            " ".join(f"{v:+.2f}" for v in offsets(D, ct)),
        )
        print(
            "  (harmonics well above the controls = those lines are overtones of the line, not separate parts)"
        )
    if a.chroma:
        C = np.load(a.chroma)
        ct = C["times"]
        k = np.clip(np.searchsorted(tt, ct), 0, T["chroma"].shape[1] - 1)
        agree = np.mean(C["chroma"].argmax(0) == T["chroma"][:, k].argmax(0))
        print(f"chroma: dominant pitch class agrees in {agree:.0%} of frames")


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("ticks")
p.add_argument("image")
p.add_argument("--rows", nargs=2, type=int)
p.add_argument("--cols", nargs=2, type=int)
p.add_argument("--span", nargs=2, type=int, required=True)
p = sub.add_parser("decode")
p.add_argument("image")
p.add_argument("--box", required=True)
p.add_argument("--y", nargs=2, required=True)
p.add_argument("--x", nargs=2, required=True)
p.add_argument("--cmap", default="magma")
p.add_argument("--line")
p.add_argument("--line-tol", type=float, default=70)
p.add_argument(
    "--ignore",
    action="append",
    help="x0,y0,x1,y1 image box to leave out of the line search (legend); repeatable",
)
p.add_argument("--out", required=True)
p = sub.add_parser("decode-chroma")
p.add_argument("image")
p.add_argument("--box", required=True)
p.add_argument("--x", nargs=2, required=True)
p.add_argument("--cmap", default="viridis")
p.add_argument("--out", required=True)
p = sub.add_parser("compare")
p.add_argument("ref")
p.add_argument("take")
p.add_argument("--chroma")
a = ap.parse_args()
{
    "ticks": cmd_ticks,
    "decode": cmd_decode,
    "decode-chroma": cmd_decode_chroma,
    "compare": cmd_compare,
}[a.cmd](a)
