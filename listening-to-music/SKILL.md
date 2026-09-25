---
name: listening-to-music
description: "Listen to generated music by measuring it: render Strudel code or record a Web Audio page through the real engine in headless Chromium, then read spectrograms, pYIN pitch lines, chroma, sensory roughness and a note-level clash scan. Use to check whether generated music sounds right or better (before/after a change), to match a reference track or a reference spectrogram image, or to find discordant chords, a buried melody, clipping or muddy mixes. Triggers on 'does it sound better', 'listen to', 'render and check', 'spectrogram', 'sfft/stft', 'discordant', 'clashing chords', 'sounds off', 'compare to the original', 'reproduce this track in Strudel'. Pairs with strudeling (writing Strudel); for format conversion use processing-video."
metadata:
  version: 0.1.0
---

# Listening to music

Claude hears nothing, but it can render audio in the real engine and measure it. Set up the loop
**render → look → measure → change one thing → re-render**, and keep a table of the numbers per
version. A version is better when a number you chose beforehand moves by more than the
take-to-take noise, and the spectrogram shows the same thing.

Requirements: Node with `playwright` and Chromium (preinstalled in Claude Code on the web),
Python with `librosa soundfile scipy matplotlib pillow`
(`pip install --break-system-packages librosa`). The first render installs `@strudel/web` into
`~/.cache/listening-to-music/`. All scripts live in `scripts/`; run them with `--help` or read the
docstring for options.

## 1. Render

```bash
S=/path/to/listening-to-music/scripts
node $S/render_strudel.mjs loop.js --out v1.wav --seconds 40 --warmup 4        # Strudel code
node $S/record_page.mjs page.html --click "#power" --out v1.wav --seconds 40 --warmup 8 \
     --query "station=house" --eval "window.__fm.setSeed(7)"                   # any Web Audio page
```

Both print peak level and flag clipping. A peak above 1.0 means the listener hears hard clipping;
fix levels before judging anything else.

For a before/after comparison, fix the randomness (a seed hook via `--eval`) so both versions
play the same material, and record each version twice.

## 2. Look

```bash
python3 $S/spectrogram.py v1.wav --out v1.png --from-onset --pyin-floor G3 --label v1
```

Then open `v1.png` with the image viewer. The top panel is a note-axis CQT spectrogram with the
pYIN lead line, and the bottom panel is chroma. Compare it with the reference picture or the
previous version side by side. The `.npz` next to it holds the numbers for step 3.

## 3. Measure

| Question | Tool | Reads |
|---|---|---|
| Do simultaneous notes rub? (discordant chords) | `render_strudel.mjs --events` → `clashes.py` | minor 2nd/9th overlap per cycle, by layer pair; worst moments |
| Do they rub in the recording? | `rubs.py`, `--pair` for replicated takes | share of tonal peak energy in semitone/minor-9th pairs |
| Is it rougher or smoother overall? | `roughness.py`, `--pair` for replicated takes | Sethares roughness median/p90 |
| Does it match a reference image? | `reference.py ticks/decode/compare` | per-semitone profile, melody agreement, overtone offsets, chroma agreement |
| Is the melody audible over the mix? | `spectrogram.py` pYIN voiced %, `reference.py compare` melody % | |

The clash scan is exact for the notes as written. `rubs.py` confirms them in the audio, where
release tails and reverb add overlaps the note data does not show. Record harmony checks with
percussion and noise textures muted in both versions: drum partials form their own peaks and hold
a full mix at a rub share near 0.28 whatever the chords do. Use `--warmup`, 40 s or more, and two
takes per version; `--pair` prints the take-to-take spread and says when a change is inside it.

Summed roughness (`roughness.py`) is a coarse overall measure. On Strudel FM (2026-09-24) it
could not tell the harmony fix apart from take-to-take noise in sleep and house. On the same
takes, the rub meter measured sleep −51%, ambient −33%, lofi −20% and house −13%, with spreads of
0.006–0.015. A loud bass drone dominates the roughness normalisation and hides a pad's rubs.
Don't treat an unmoved roughness figure as proof that nothing changed.

## 4. Change one thing, re-render, re-measure

Change one parameter or rule at a time, and after each change render and rerun the same
measurements. A metric can reward the wrong thing, so check it against the spectrogram each
round.

## Known traps (each cost a round on 2026-09-24)

- **Mini-notation strings are patterns, not values.** `.delaytime("3/8")` means "3, over 8
  cycles", so the delay was 3 s (clamped to 1 s). Pass a number: `.delaytime(0.39)`.
  `.gain("0.9, 0.3")` on a stacked pattern is itself a stack, so every hit fired twice and the
  drums peaked at 2.9× full scale. Give each layer its own scalar gain.
- **AudioWorklet synths (`supersaw`, …) need a secure context.** Pages served from
  `http://` get no `audioWorklet`, and those synths are silent while everything else plays. The
  scripts serve local pages from `https://local.test/` for this reason. `initStrudel` also loads
  the worklets only on the first document click, so the scripts click.
- **pYIN floor.** With a C3 floor, a loud bass made pYIN pick the bass's upper partials an octave
  below the tune. Tracking fell from 60% to 25% even though the melody was unchanged. Set the
  floor just under the melody's lowest note.
- **Lines above a melody are often its overtones.** In a reference, lines at the melody's pitch
  +12, +19 and +24 semitones are usually its harmonics, not a second part. Test it with
  `reference.py compare` (the overtone rows against the control rows) before voicing a pad
  from them. A misread gave a Gmaj7 that the source never played.
- **Measure in the engine.** An offline numpy model of Strudel's FM mispredicted the rendered
  harmonic spectrum. The low-passed saw it favoured came out darker in the engine than FM.
- **A metric can be confounded.** A "lead prominence" score rewarded a pad that doubled the
  melody's notes. Before trusting a metric, ask what else could raise it.
- **Check reproducibility once.** Render the same version twice and confirm the numbers repeat,
  so differences between versions can be trusted.
- **Decoding reference images.** Bin centres sit on the tick rows. Get exact ticks with
  `reference.py ticks` rather than by eye; a half-bin error splits every note across two
  semitones.
