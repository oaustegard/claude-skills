# making-kinescript-videos - Changelog

All notable changes to the `making-kinescript-videos` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2026-11-02

### Added

- Initial skill: Kinescript setup on a CPU container (skia-python ≥ 144, EGL libraries, Kokoro in a Python 3.12 venv through `KINE_VOICE_CMD`), the write → voice → check → look → render loop, narration pace and mix, and gotchas from the gPu(doom) and games promos checked against 1.6.1.
- `references/kokoro-speech.md`: measured controls for Kokoro through misaki: phoneme links in Kokoro's alphabet (ASCII `g` is dropped), stress links and capitals, number flags, text-normalisation and homograph failures, pause lengths per punctuation mark, the absence of question intonation, pace per voice, and weighted voice blends by repetition or `.pt` file.
