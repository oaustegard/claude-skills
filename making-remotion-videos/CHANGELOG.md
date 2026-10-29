# making-remotion-videos - Changelog

All notable changes to the `making-remotion-videos` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.1] - 2026-10-29

### Added

- Narration: record a coined name once and splice it into every line; choose its spelling by consistency of 3 transcribed takes; OmniVoice CMU phoneme override; paced OmniVoice results.

## [0.2.0] - 2026-10-29

### Other

- making-remotion-videos 0.2.0: narration

## [0.2.0] - 2026-10-29

### Added

- Narration: a voiceover section and references/narration.md. Covers slot-sized scripts, best-of-three takes picked by ASR WER, loudnorm to -16 LUFS, the track passed as a prop to `<Html5Audio>`, and onset/loudness checks. Compares Gemini 3.8 Flash TTS with OmniVoice 0.2.1 (the VoiceStudio engine) as measured on the aeyu.io reel, including the jailed OmniVoice install recipe.

## [0.1.0] - 2026-10-29

### Other

- making-remotion-videos: new skill for Remotion video in CCotw

## [0.1.0] - 2026-10-29

### Added

- Initial skill: Remotion 4.0.535 scaffold with pinned versions, local font vendoring (the render browser rejects the egress proxy's CA), a render wrapper that uses the preinstalled headless shell with yuv420p/bt709 output, the frame-pure composition contract, the still-frame contact-sheet review loop, and a product demo reel protocol (phone frame, scroll shots, tap indicator, Playwright capture with a frozen fake clock). Built and verified on the aeyu.io demo reel (oaustegard/experiments aeyu-demo-reel/).