"""Shared note-event helpers: the events JSON every sheet-music script reads and writes.

Format: {"cycles": N, "beats": 4, "bpm": 120, "events": [{"layer", "t0", "t1", "midi"}, ...]}
t0/t1 are in cycles (one cycle = one bar of `beats` quarter notes, as in Strudel's setcpm(bpm/4)).
bpm is optional and only needed to convert to seconds.
"""

import json

import music21 as m21


def load(path):
    with open(path) as fh:
        d = json.load(fh)
    d.setdefault("beats", 4)
    return d


def save(path, events, cycles=None, beats=4, bpm=None):
    cycles = cycles or (max((e["t1"] for e in events), default=0))
    out = {"cycles": cycles, "beats": beats, "events": events}
    if bpm:
        out["bpm"] = bpm
    with open(path, "w") as fh:
        json.dump(out, fh)


def spell(midi, key):
    """A music21 Pitch for a MIDI number, spelled to suit the key (flats in flat keys)."""
    p = m21.pitch.Pitch(midi=int(midi))
    if key is None:
        return p
    scale = {q.name for q in key.getScale().getPitches()}
    if (
        key.mode == "minor"
    ):  # melodic/harmonic minor: raised sixth and leading tone (E# in f#)
        for deg in (6, 7):  # raise the degree by an accidental, keeping its letter
            q = key.pitchFromDegree(deg)
            r = m21.pitch.Pitch(q.step)
            r.accidental = m21.pitch.Accidental(
                (q.accidental.alter if q.accidental else 0) + 1
            )
            scale.add(r.name)
    cands = [p, *p.getAllCommonEnharmonics()]
    for c in cands:
        if c.name in scale:
            return c
    # outside the key: one accidental, in the direction of the key signature
    want = "-" if key.sharps < 0 else "#"
    single = [c for c in cands if len(c.name) <= 2]
    for c in single:
        if want in c.name:
            return c
    return single[0] if single else p


def score_from_events(d, layers=None, key=None, grid=16, title=None):
    """Build a music21 Score: one part per layer, notes quantised to 1/grid of a whole note.

    Each layer is chordified on its own, so overlapping notes inside a layer become chords
    with ties rather than invalid overlaps.
    """
    beats = d.get("beats", 4)
    q = 4 / grid  # quarterLength per step: grid 16 = sixteenth notes, in any metre
    names = layers or sorted({e["layer"] for e in d["events"]})
    raw = m21.stream.Stream()
    for e in d["events"]:
        raw.insert(0, m21.note.Note(midi=e["midi"]))
    if key is None and len(raw.notes):
        key = raw.analyze("key")
    sc = m21.stream.Score()
    if title:
        sc.insert(0, m21.metadata.Metadata(title=title))
    for name in names:
        evs = [e for e in d["events"] if e["layer"] == name]
        if not evs:
            continue
        s = m21.stream.Stream()
        for e in evs:
            a = round(e["t0"] * beats / q) * q
            b = max(a + q, round(e["t1"] * beats / q) * q)
            n = m21.note.Note(spell(e["midi"], key))
            n.quarterLength = b - a
            s.insert(a, n)
        c = s.chordify()
        part = m21.stream.Part(id=name)
        part.partName = name
        part.insert(0, m21.instrument.Instrument(instrumentName=name))
        mids = sorted(e["midi"] for e in evs)
        part.insert(
            0,
            m21.clef.BassClef() if mids[len(mids) // 2] < 57 else m21.clef.TrebleClef(),
        )
        part.insert(0, m21.meter.TimeSignature(f"{beats}/4"))
        if key is not None:
            part.insert(0, m21.key.KeySignature(key.sharps))
        for el in c.notesAndRests:
            off = el.getOffsetBySite(c)
            if isinstance(el, m21.chord.Chord):  # chordify drops spelling; restore it
                el.pitches = tuple(spell(p.midi, key) for p in el.pitches)
            if isinstance(el, m21.chord.Chord) and len(el.pitches) == 1:
                n = m21.note.Note(el.pitches[0])
                n.quarterLength = el.quarterLength
                n.tie = el.tie
                el = n
            part.insert(off, el)
        total = d.get("cycles", 0) * beats
        if total > part.highestTime:
            r = m21.note.Rest(quarterLength=total - part.highestTime)
            part.insert(part.highestTime, r)
        part.makeRests(fillGaps=True, inPlace=True)
        sc.insert(0, part)
    return sc, key
