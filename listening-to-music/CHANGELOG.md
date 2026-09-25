# listening-to-music - Changelog

All notable changes to the `listening-to-music` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-09-25

### Other

- listening-to-music 0.2.0: sheet music in and out

## [0.2.0] - 2026-09-25

### Added

- Sheet music, both directions, on a shared events JSON (`notes.py`):
  - `score.py`: engrave events as a score (music21 + Verovio PNG), key-aware spelling, `--harmony` beat-by-beat chord names, Roman numerals and rub flags, `--zoom` for high-resolution pages.
  - `transcribe.py`: monophonic melody (and `--bass`) from audio with glide folding, gap merging, onset snapping and pitch-specific re-attack splitting (`--no-split` for echo-heavy leads).
  - `compare_notes.py`: mir_eval note precision/recall/F1 with and without offsets, unmatched notes listed, `--align` for unknown downbeats, `--octave-free`.
  - `read_score.py`: MusicXML/MXL/MIDI/ABC/Humdrum, music21 corpus, and images/PDF via oemer OMR, into events.
  - `to_strudel.py`: events into Strudel code, one `<...>` step per bar.
- SKILL.md section with measured accuracies (round trip 100%, transcription 87%/82%, OMR 6%, reading engraved images directly 100% on a blind test).

## [0.1.0] - 2026-09-25

### Added

- `render_strudel.mjs`: render Strudel code through superdough in headless Chromium to a float WAV; `--events` dumps per-layer note events.
- `record_page.mjs`: record any Web Audio page (click, seed hook, warm-up), served from an https origin so AudioWorklet synths play.
- `spectrogram.py`: note-axis CQT spectrogram with pYIN lead line and chroma, plus features in `.npz`.
- `roughness.py`: Sethares roughness per frame; `--pair` compares replicated before/after takes against take-to-take spread.
- `reference.py`: decode a reference spectrogram image (colormap inversion, tick calibration, drawn pitch line) and compare a render against it.
- `clashes.py`: note-level scan for semitone and minor-ninth rubs by layer pair.
- `rubs.py`: audio-side rub meter (CQT peaks at 3 bins per semitone; share of tonal energy in semitone and minor-ninth pairs), with `--pair` replicate comparison.