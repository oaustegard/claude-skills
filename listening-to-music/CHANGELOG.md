# listening-to-music - Changelog

All notable changes to the `listening-to-music` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2026-09-25

### Added

- `render_strudel.mjs`: render Strudel code through superdough in headless Chromium to a float WAV; `--events` dumps per-layer note events.
- `record_page.mjs`: record any Web Audio page (click, seed hook, warm-up), served from an https origin so AudioWorklet synths play.
- `spectrogram.py`: note-axis CQT spectrogram with pYIN lead line and chroma, plus features in `.npz`.
- `roughness.py`: Sethares roughness per frame; `--pair` compares replicated before/after takes against take-to-take spread.
- `reference.py`: decode a reference spectrogram image (colormap inversion, tick calibration, drawn pitch line) and compare a render against it.
- `clashes.py`: note-level scan for semitone and minor-ninth rubs by layer pair.
- `rubs.py`: audio-side rub meter (CQT peaks at 3 bins per semitone; share of tonal energy in semitone and minor-ninth pairs), with `--pair` replicate comparison.
