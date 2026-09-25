#!/usr/bin/env python3
"""Write notes out as sheet music, and name the harmony beat by beat.

  python3 score.py events.json --out score.png [--layers LEAD,KEYS,BASS] [--bars 1-8]
         [--key D:major] [--grid 16] [--title "v3"] [--harmony] [--musicxml score.musicxml]

Reads the events JSON (render_strudel.mjs --events, transcribe.py, read_score.py). Writes
engraved PNG page(s) via Verovio (score-1.png, score-2.png, ... when there is more than one
page); open them with the image viewer.
--harmony  also prints one line per beat: the sounding pitches across all layers, music21's
           chord name and a Roman numeral in the detected (or given) key, and flags beats with a
           semitone or minor-ninth rub. A notation view of the same question clashes.py answers.
"""

import argparse
import os

import cairosvg
import music21 as m21
import verovio
from notes import load, score_from_events


def bar_slice(d, bars):
    if not bars:
        return d
    lo, hi = (int(x) for x in bars.split("-"))
    ev = [
        {**e, "t0": e["t0"] - (lo - 1), "t1": min(e["t1"], hi) - (lo - 1)}
        for e in d["events"]
        if lo - 1 <= e["t0"] < hi
    ]
    return {**d, "events": ev, "cycles": hi - lo + 1}


def engrave(xml_path, out_png, width=2100, scale=45, zoom=1.0):
    tk = verovio.toolkit()
    tk.setOptions(
        {
            "pageWidth": width,
            "scale": scale,
            "adjustPageHeight": True,
            "footer": "none",
            "header": "auto",
            "breaks": "auto",
        }
    )
    tk.loadFile(xml_path)
    pages = tk.getPageCount()
    outs = []
    for i in range(1, pages + 1):
        svg = tk.renderToSVG(i)
        name = out_png if pages == 1 else out_png.replace(".png", f"-{i}.png")
        cairosvg.svg2png(
            bytestring=svg.encode(), write_to=name, background_color="white", scale=zoom
        )
        outs.append(name)
    return outs


def harmony(sc, key, beats):
    ch = sc.chordify()
    rows = []
    for c in ch.recurse().getElementsByClass(m21.chord.Chord):
        off = c.getOffsetInHierarchy(ch)
        mids = sorted({p.midi for p in c.pitches})
        rub = any(b - a in (1, 13) for a in mids for b in mids)
        try:
            rn = m21.roman.romanNumeralFromChord(c, key).figure if key else ""
        except Exception:
            rn = "?"
        rows.append(
            (
                int(off // beats) + 1,
                off % beats + 1,
                " ".join(p.nameWithOctave for p in sorted(c.pitches)),
                c.pitchedCommonName,
                rn,
                rub,
            )
        )
    return rows


ap = argparse.ArgumentParser()
ap.add_argument("events")
ap.add_argument("--out", required=True)
ap.add_argument("--layers")
ap.add_argument("--bars")
ap.add_argument("--key", help="e.g. D:major, F#:minor; default: detected")
ap.add_argument("--grid", type=int, default=16)
ap.add_argument("--title")
ap.add_argument("--harmony", action="store_true")
ap.add_argument("--musicxml")
ap.add_argument(
    "--zoom",
    type=float,
    default=1.0,
    help="PNG scale; 3 gives scan-like resolution for OMR tests",
)
a = ap.parse_args()

d = bar_slice(load(a.events), a.bars)
key = None
if a.key:
    tonic, mode = a.key.split(":")
    key = m21.key.Key(tonic.replace("b", "-") if len(tonic) > 1 else tonic, mode)
sc, key = score_from_events(
    d,
    layers=a.layers.split(",") if a.layers else None,
    key=key,
    grid=a.grid,
    title=a.title,
)
xml = a.musicxml or os.path.splitext(a.out)[0] + ".musicxml"
sc.write("musicxml", fp=xml)
pages = engrave(xml, a.out, zoom=a.zoom)
print(f"key {key}; {len(sc.parts)} part(s); wrote {xml} and {', '.join(pages)}")
if a.harmony:
    rows = harmony(sc, key, d.get("beats", 4))
    rubs = sum(r[5] for r in rows)
    print(f"harmony, {len(rows)} chord changes, {rubs} with a semitone/minor-9th rub:")
    for bar, beat, pitches, name, rn, rub in rows:
        print(
            f"  bar {bar:3d} beat {beat:4.2f}  {rn:8s} {name:32s} {pitches}{'   << rub' if rub else ''}"
        )
