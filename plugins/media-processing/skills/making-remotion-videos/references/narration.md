# Narration for a Remotion reel

How the aeyu.io reel got its voiceover (2026-10-29, sources in
`oaustegard/experiments` `aeyu-demo-reel/vo/`). The reel's scenes are fixed, so
the voiceover fits the timeline rather than the reverse.

## Script

`vo/script.json` is a list of `{id, start, end, text}`. Take `start` a few tenths
after each scene starts, and `end` a few tenths before the next line's start.
Size the text to the slot before generating anything:

```python
for l in S: print(l["id"], round(len(l["text"].split()) / (l["end"] - l["start"]) * 60), "wpm needed")
```

Rewrite any line that needs more than about 180 wpm. Oskar's standing pace target
for narration is 165–180 wpm, energetic, with varied intonation (memory 3eb81ac6).

## Routes

| | Gemini 3.8 Flash TTS | OmniVoice 0.2.1 (k2-fsa) |
|---|---|---|
| Where | `invoking-gemini` `generate_speech()`, API | local, inside `claude-workspace/scripts/jail.sh` |
| Speed here | 27 takes in 2.5 min | about 29× slower than real time on 4 CPU cores when cloning, about 10× with a designed voice |
| Voice control | prebuilt or designed voice id, plus a free-text `style` | tag design (`male, young adult, low pitch, british accent`), or cloning from a 3–10 s reference with its transcript |
| Pace control | the style string only | `duration=` per line (exact), or `speed=` |
| Pitch variation, 2 test lines | 4.1–6.6 semitones SD | designed voices 1.8–3.2; cloned from a lively reference 2.7–4.1 |
| "Year bests" | "your best" in 6 of 6 takes | correct in most takes |

OmniVoice is the default engine of debpalash/VoiceStudio, the 94k-star app
billed as an "open-source, fully-local ElevenLabs alternative". The app itself
is an Electron studio; the engine is what matters for a render.

### OmniVoice in the jail

The weights are 3.3 GB: `k2-fsa/OmniVoice` at revision `c5fdb5ccb1`, with
`audio_tokenizer/` included. Download them outside the jail with
`huggingface_hub.snapshot_download` into `/tmp/jail/omnivoice/models/OmniVoice`.
Install wheels with `--no-deps` into separate `.deps*` directories created before
the `chown`. The system torch 2.14 CPU build is reused, so torch is not installed:

```
omnivoice==0.2.1 transformers==5.19.0 pydub==0.25.1 soundfile==0.14.0
safetensors==0.8.0 regex==2026.9.10
audioop-lts==0.2.2          # Python 3.13 removed audioop; pydub needs it
accelerate==1.15.0 psutil==7.2.2   # the audio tokenizer loads with device_map
```

Run with `-e PYTHONPATH=<all .deps dirs> -e HF_HUB_OFFLINE=1 -e HOME=/tmp/jail/omnivoice`.
`vo/omnivoice_run.py` takes a JSON list of lines with optional `instruct`,
`ref_audio`, `ref_text`, `duration` and `seed`. Each failure surfaced as an
import error at first run: `pyaudioop`, then `accelerate`. Read the traceback,
add the wheel, and re-run.

A cloned voice carries the reference's delivery. A 6 s Gemini Charon clip in the
"energetic, brisk explainer" style, with no words shared with the script, gave
OmniVoice its energy. Unpaced, the clone then averaged 211 wpm, with lines up to
283. Set `duration = min(slot − 0.15, words / 170 × 60)` per line.

## Picking and mixing

`vo/assemble.py TAKES NAME [SCRIPT]`: for each line, trim silence (40 dB),
transcribe with faster-whisper `small.en`, and pick the take with the lowest WER,
then the longest that fits its slot. If none fits, time-stretch by up to 1.12×.
It places each take at its slot start in a 48 kHz track, applies
`loudnorm=I=-16:TP=-1.5:LRA=11`, and writes `NAME.wav` plus `NAME_picks.json`.

Two quirks of this container's faster-whisper 1.2.1: passing a file path fails
in PyAV (`open() got an unexpected keyword argument 'metadata_errors'`), so pass
a 16 kHz float32 array. ASR also cannot judge a coined brand name ("aeyu" came
back as "IU.io", "au.io" and "I-O dot I-O"). Exclude those lines from the WER
score and get the pronunciation from a person.

## Verified on the aeyu reel

Speech onsets from `silencedetect` were 0.31, 2.61, 6.12 … 31.31 s against
planned starts of 0.3, 2.6, 6.1 … 31.3 s, and integrated loudness was −15.8 LUFS.
The paced OmniVoice track, with `duration` set per line, measured 182 wpm with
speech onsets on every slot start and −16.0 LUFS.

## Pronouncing a coined name

Record the name once and splice that one clip into every line that says it:
the closing line is "Try the demo at" plus the clip, with an 80 ms gap. When it
was generated inside each line, Gemini said "aeyu" two different ways in one
reel (Oskar heard "I owe" and "AU").

To choose the spelling, generate each candidate 3 times and keep the one whose
takes all transcribe alike. For Gemini, "AY-you dot I-O." gave "AU.io" in 3 of
3 takes. "AY-yoo dot eye-oh." drifted between "AO", "AU" and "AEO", and
"Ay, you." gave "Hey you". OmniVoice read every spelling as "IU.io"
("eye-you"). Its inline CMU override `[EY1 Y UW0] dot I-O.` gave "AU.io" in 4
of 4 takes.

The same override did not rescue "Year bests": `[Y IH1 R] bests` still
transcribed as "your best" in 3 of 3 takes. Both voices said "Best of the year"
correctly, so the script uses that wording.
