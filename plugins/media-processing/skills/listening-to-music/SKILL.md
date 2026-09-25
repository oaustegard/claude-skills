---
name: listening-to-music
description: "Listen to generated music by measuring it and by reading it as sheet music: render Strudel code or record a Web Audio page through the real engine in headless Chromium, then read spectrograms, pYIN pitch lines, chroma, roughness and semitone-rub meters; engrave notes as a score with beat-by-beat harmony; transcribe a melody from audio; read MusicXML/MIDI/ABC or a score image into notes and into Strudel code. Use to check whether generated music sounds right or better (before/after a change), to match a reference track, spectrogram image or score, or to find discordant chords, a buried melody, clipping or muddy mixes. Triggers on 'does it sound better', 'listen to', 'render and check', 'spectrogram', 'sfft/stft', 'discordant', 'clashing chords', 'sounds off', 'compare to the original', 'reproduce this track in Strudel', 'sheet music', 'score', 'notation', 'MusicXML', 'MIDI', 'ABC', 'transcribe', 'OMR'. Pairs with strudeling (writing Strudel); for format conversion use processing-video."
metadata:
  version: 0.2.0
---

# Listening to music

Claude hears nothing, but it can render audio in the real engine and measure it. Set up the loop
**render → look → measure → change one thing → re-render**, and keep a table of the numbers per
version. A version is better when a number you chose beforehand moves by more than the
take-to-take noise, and the spectrogram shows the same thing.

Requirements: Node with `playwright` and Chromium (preinstalled in Claude Code on the web),
Python with `librosa soundfile scipy matplotlib pillow`, and for sheet music
`music21 verovio mir_eval cairosvg`
(`pip install --break-system-packages librosa music21 verovio mir_eval cairosvg`). The first render installs `@strudel/web` into
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

## Sheet music: notation out, notation in

Notation is the other way to hear. A score shows voicings, clusters (noteheads pushed sideways
are seconds), register and rhythm at a glance, and Claude reads clean engraving accurately. All
these scripts share one events JSON (layer, t0, t1, midi; times in bars).

```bash
node $S/render_strudel.mjs loop.js --events ev.json --cycles 8          # notes as written
python3 $S/score.py ev.json --out score.png --layers LEAD,KEYS,BASS --harmony   # engrave + analyse
python3 $S/transcribe.py take.wav --out mel.json --bpm 115              # notes as heard (melody)
python3 $S/compare_notes.py ev.json mel.json --ref-layer LEAD --cand-layer melody --align 1
python3 $S/read_score.py tune.musicxml --out ref.json                   # .mxl .mid .abc .krn, corpus:
python3 $S/to_strudel.py ref.json --out tune.js                         # score -> Strudel code
```

`score.py --harmony` prints each chord change with its pitches, music21's chord name, a Roman
numeral in the detected key, and a rub flag. On Strudel FM the same four lofi bars went from 15
of 28 chord changes with a rub to 0 of 28 after the voicing fix, and the engraving showed why:
the old Fmaj7 had its E and F side by side.

Measured on 2026-09-25 (compare_notes.py, onset within 0.05 bar and pitch within 50 cents):

| Path | Test | F1 |
|---|---|---|
| read_score → to_strudel → render events | Bach BWV 66.6, 4 parts, 163 notes | 100% every part |
| transcribe.py, one line | same chorale, soprano alone, piano, not used for tuning | 87% |
| transcribe.py `--no-split` | synth lead with delay echoes | 82% (65% with splitting) |
| transcribe.py | full four-part chorale | 0%: monophonic only |
| OMR (oemer 0.1.8) | clean engraved soprano line | 6%; key read as flats, quarters as whole notes |
| Claude reading the image → ABC | unseen chorale, soprano + bass, 38 notes | 100% (one clean engraving) |

So:
- **Score images:** read them yourself. Open the page and zoom into dense staves by cropping a
  3× render or scan. Write ABC (`K:`, `M:`, `L:`, one `V:` per staff), convert it with
  `read_score.py`, re-engrave with `score.py`, and compare the two pictures bar by bar before
  using the notes. Use oemer only as a rough first pass, and never trust it unchecked.
- **Transcription** is monophonic. For chords and inner voices, read the generating code's events
  or the score. Splitting at re-attacks is on by default, because a re-struck piano note has no
  gap; switch it off with `--no-split` for leads with delay or echo.
- **Unknown downbeat:** a recording that starts mid-loop needs `compare_notes.py --align N`. It
  searches shifts up to N bars and prints the one used.

## 4. Change one thing, re-render, re-measure

Change one parameter or rule at a time, and after each change render and rerun the same
measurements. A metric can reward the wrong thing, so check it against the spectrogram each
round.

## Known traps (each cost a round on 2026-09-24/25)

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
- **music21 respelling.** `chordify()` discards pitch spelling, and a Key's inferred tonic
  transposes to the wrong letter (a leading tone of F instead of E♯ in F♯ minor). `notes.spell`
  re-spells after every chordify from the key's own scale plus the raised 6th and 7th. Without
  that, the score reads as wrong notes.
- **Quantise to a beat subdivision, not a bar fraction.** A 16-step bar in 3/4 produced 64th
  notes and triple dots; the grid is now 16ths in any metre.
- **Decoding reference images.** Bin centres sit on the tick rows. Get exact ticks with
  `reference.py ticks` rather than by eye; a half-bin error splits every note across two
  semitones.
