#!/usr/bin/env python3
"""Read sheet music into note events: MusicXML/MXL, MIDI, ABC, Humdrum, or an image/PDF via OMR.

  python3 read_score.py tune.musicxml --out ref.json       # also .mxl .mid .abc .krn
  python3 read_score.py page.png --out ref.json            # optical music recognition (oemer)
  python3 read_score.py scan.pdf --out ref.json            # each page rasterised, then OMR
  python3 read_score.py corpus:bach/bwv66.6 --out ref.json # music21's bundled corpus

One layer per part (its name, or P1, P2 ...). Times are in bars, with a pickup measure shifted
so that bar 1's downbeat falls on 1.0 - (pickup length). Tied notes are merged. Prints key,
metre, bar count and per-part ranges.

OMR is the weak link. oemer reads clean engraved single-staff and piano scores tolerably and
handwriting or dense orchestral pages badly; it mislabels accidentals, rhythms and voices.
Before building on an OMR read, re-engrave it with score.py and compare the picture with the
original page, and run compare_notes.py against anything more reliable you have. The measured
accuracy on a known engraved chorale is in SKILL.md; reading the image yourself into ABC is
usually better (see SKILL.md).
OMR setup: pip install oemer, then replace its onnxruntime-gpu with onnxruntime<1.20 (newer
releases reject oemer's model: "pads must not contain negative values") and, if numpy<2 results,
opencv-python-headless<4.11. The first run downloads the model checkpoints from GitHub.
ABC voice names are not carried into part names by music21; ABC parts come back as P1, P2 ...
"""

import argparse
import glob
import os
import subprocess
import tempfile

import music21 as m21
from notes import save

IMAGE = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


def omr(image, workdir):
    before = set(glob.glob(os.path.join(workdir, "*.musicxml")))
    subprocess.run(["oemer", "-o", workdir, image], check=True)
    new = sorted(set(glob.glob(os.path.join(workdir, "*.musicxml"))) - before)
    if not new:
        raise SystemExit(f"oemer produced no MusicXML for {image}")
    return new[-1]


def load_any(src):
    if src.startswith("corpus:"):
        return m21.corpus.parse(src.split(":", 1)[1])
    ext = os.path.splitext(src)[1].lower()
    if ext in IMAGE or ext == ".pdf":
        work = tempfile.mkdtemp(prefix="omr-")
        pages = [src]
        if ext == ".pdf":
            subprocess.run(
                ["pdftoppm", "-r", "300", "-png", src, os.path.join(work, "page")],
                check=True,
            )
            pages = sorted(glob.glob(os.path.join(work, "page*.png")))
        scores = [m21.converter.parse(omr(p, work)) for p in pages]
        if len(scores) == 1:
            return scores[0]
        joined = scores[0]
        for s in scores[1:]:
            for p_to, p_from in zip(joined.parts, s.parts):
                for m in p_from.getElementsByClass(m21.stream.Measure):
                    p_to.append(m)
        return joined
    return m21.converter.parse(src)


ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--out", required=True)
a = ap.parse_args()

sc = load_any(a.src).stripTies()
ts = next(
    iter(sc.recurse().getElementsByClass(m21.meter.TimeSignature)), None
) or m21.meter.TimeSignature("4/4")
bar_ql = ts.barDuration.quarterLength
mm = next(iter(sc.recurse().getElementsByClass(m21.tempo.MetronomeMark)), None)
first = (
    next(iter(sc.parts[0].getElementsByClass(m21.stream.Measure)), None)
    if sc.parts
    else None
)
pickup = 0.0
if first is not None and first.duration.quarterLength < bar_ql:
    pickup = bar_ql - first.duration.quarterLength
events = []
for i, part in enumerate(sc.parts or [sc]):
    name = str(part.partName or "").strip().strip('"').replace(" ", "_")
    if not name:
        name = f"P{i + 1}"
    for n in part.flatten().notes:
        off = float(n.getOffsetInHierarchy(part)) + pickup
        dur = float(n.quarterLength) or 0.25
        for p in n.pitches:
            events.append(
                {
                    "layer": name,
                    "t0": off / bar_ql,
                    "t1": (off + dur) / bar_ql,
                    "midi": int(p.midi),
                }
            )
cycles = max((e["t1"] for e in events), default=0)
bpm = mm.getQuarterBPM() if mm else None
save(a.out, events, cycles=cycles, beats=round(float(bar_ql)), bpm=bpm)
key = sc.analyze("key") if events else None
print(
    f"{a.src}: key {key}, metre {ts.ratioString}, {cycles:.1f} bars, pickup {pickup} quarters, tempo {bpm or 'unmarked'}"
)
for name in dict.fromkeys(e["layer"] for e in events):
    ms = [e["midi"] for e in events if e["layer"] == name]
    lo, hi = (
        m21.pitch.Pitch(midi=min(ms)).nameWithOctave,
        m21.pitch.Pitch(midi=max(ms)).nameWithOctave,
    )
    print(f"  {name}: {len(ms)} notes, {lo}-{hi}")
print(f"wrote {a.out}")
