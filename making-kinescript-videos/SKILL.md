---
name: making-kinescript-videos
description: "Make an MP4 from a JSON scene file with Kinescript (drknowhow/kinescript, the `kine` CLI): text, shapes, charts, SVG, images, video clips, particles and 3D models on cue-based timing, with a checker that lints layout, contrast, reading time and the sound mix, and narration spoken by Kokoro TTS with word-level cues and captions, and avatars (drawn or glTF characters) that lip-sync to it. Covers setup in a Linux container (CPU backend, Python 3.12 venv for Kokoro), the write → voice → check → look → render loop, and controlling Kokoro's pronunciation, stress, pauses, pace and voice blends. Use for 'kine', 'Kinescript', 'kinescript scene', 'kine voice', 'narrated promo', 'explainer video', 'motion graphics video', 'video with voice-over and captions', 'Kokoro pronunciation', 'TTS says a name wrong', 'make the narrator emphasise', 'video thumbnail is blank', 'poster frame', 'talking avatar', 'presenter character', 'lip sync', or any video built from type, shapes and captured footage."
metadata:
  version: 0.3.2
---

# Making videos with Kinescript

Kinescript renders a JSON scene to video with Skia and ffmpeg. Layers start
and end on cues (`"at": "title.out+0.2"`) rather than on hand-summed seconds,
and every frame is a pure function of the scene and the frame number. The
`kine` CLI also lints the scene (`check`), draws labelled contact sheets
(`look`) and speaks narration (`voice`). Its author is Dimitri (GitHub
`drknowhow`). Oskar Austegard, who maintains this skill collection, contributes
as a collaborator. Muninn is the name of the Claude agent that works for him.

This file was last checked against Kinescript 2.5.0 (2026-11-12), and
upstream releases often. **`kine docs` is the authoritative reference for the installed
version.** Read it before writing a scene, and don't rely on feature lists
remembered from earlier sessions, this file included.

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| Real web UI in a phone frame, arbitrary DOM/CSS layout | `making-remotion-videos` |
| AI-generated footage (Veo, Gemini video) | `creating-video` |
| Trim, transcode or caption existing footage | `processing-video` |
| Hand-drawn or p5.js character animation | `animating-with-code` |

## Setup in a Linux container

```bash
sudo apt-get install -y ffmpeg libegl1 libgl1 libfontconfig1   # skia needs EGL even on the CPU backend
pip install kinescript "skia-python>=144"
kine doctor
```

- Pin skia-python ≥ 144. `pyproject.toml` allows ≥ 87, but 138.0 crashes.
- With no GPU, `KINE_BACKEND=cpu` is used. Kinescript 2.5.0 rendered a
  2:12 1080p explainer (3,968 frames of text, shapes and captions) in 41 s at
  `-j 4` on 4 CPUs, 98 fps (`oaustegard/experiments/colbert-pooling-explainer`).
  Versions before 2.x managed 3–7 fps, so budget from a short `--from/--to`
  render rather than from memory.
- **In `oaustegard/claude-workspace` sessions**, that repo's rules require
  third-party code to run inside its sandbox, `scripts/jail.sh` (no network,
  no secrets). Install from PyPI outside it and run `kine` through it.

### Kokoro for `kine voice`

`kine voice` needs a voice plugin. Kokoro's, `kinescript-kokoro`, is not on
PyPI: it lives in the Kinescript repo at `plugins/kinescript-kokoro`. Kokoro
0.9.4 and misaki 0.9.4, the latest releases (April 2025), require Python
3.10–3.12; on 3.13 pip falls back to kokoro 0.7.16. So give Kokoro its own
3.12 venv and point `KINE_VOICE_CMD` at it; `kine` stays in the system Python:

```bash
git clone --depth 1 https://github.com/drknowhow/kinescript ~/kinescript
uv python install 3.12 && uv venv -p 3.12 ~/kokoro-env
VIRTUAL_ENV=~/kokoro-env uv pip install --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu torch "kokoro==0.9.4" "misaki[en]==0.9.4" \
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
export KINE_VOICE_CMD="env PYTHONPATH=$HOME/kinescript/plugins/kinescript-kokoro $HOME/kokoro-env/bin/python -m kinescript_kokoro"
```

The CPU torch index avoids a multi-GB CUDA download; the venv comes to 1.4 GB.
Installing spaCy's model up front saves misaki's first-use download. The first
`kine voice` run downloads the model (327 MB). With no network at voice time
(a sandbox), fetch `hexgrad/Kokoro-82M` (`config.json`, `kokoro-v1_0.pth`,
`voices/*.pt`) with `huggingface_hub.snapshot_download` beforehand and pass
`HF_HOME` and `HF_HUB_OFFLINE=1` inside `KINE_VOICE_CMD`.

## Procedure

1. **Read `kine docs`** for layer types, cue syntax, motions and the sound rules,
   and `kine docs 3d` as well when the scene uses depth, a camera or models.
   `kine new` writes a starter scene.
2. **Storyboard in writing**: scenes, their order, and the one thing the
   viewer must take from each. For anything longer than a few layers,
   generate the scene from a Python builder that holds one timeline array
   (the games promo's `kine/build_scene.py` is an example). Don't hand-edit
   500 lines of JSON.
3. **Narration**: in the scene's `audio` list, give each voice sound a `text`, a `speaker` and a `rate`, then
   `kine voice scene.json`. It re-speaks only sounds whose text, speaker or rate
   changed. It writes the audio and a words file of word timings. Mark a word with
   `[[go]]` before it to cue a layer from it (`"at": "vo1:go"`).
   Before speaking anything, read
   [references/kokoro-speech.md](references/kokoro-speech.md), which covers
   names, numbers, stress, pauses, pace and blends.
4. **`kine check scene.json`**: fix every error, read every warning, run it
   again. The warnings for tiny text and reading time are worth acting on:
   they pushed the games promo's type to ≥ 44 px and its sublines to five
   words or fewer.
5. **`kine look scene.json --boxes`** (and `--audio` once there is sound):
   read the contact sheet image before rendering. `kine still` renders one
   frame. `kine probe --at T` gives every layer's resolved box.
6. **Poster frame**: set `canvas.poster` to a moment that shows the title,
   e.g. `"poster": "title.in+0.5"` (seconds, a marker, a cue or a word). Feeds,
   players and a `<video>` without a poster show frame 0 before play, and a
   scene that fades in from its background shows up there as a blank rectangle.
   With `poster` set, the render draws that frame as frame 0 (one frame,
   1/fps s, before the opening; audio unchanged). `kine check` warns
   `blank-first-frame` when frame 0 is empty and no poster is set. For a page,
   `kine still scene.json --at poster -o poster.jpg` gives the `<video poster>`
   image. `--no-poster` keeps the real frame 0 for a master.
7. **Render**: `kine render scene.json -o out.mp4 -q high -j 4`. Long renders
   belong in a background job. The result's `"poster"` names the frame used.
8. **Verify** the file: `ffprobe` for size, fps and duration, a frame strip
   (`ffmpeg -vf "select='not(mod(n\,90))',scale=270:-1,tile=8x2"`) whose first
   tile is the poster, and a listen to the voice track.

## Brands

When the person has a brand, or makes several videos that should look alike,
use a Kinescript brand (1.9.0) instead of copying colours and fonts into
each scene. `kine docs brands` has the full format.

**Muninn's videos use the Muninn brand**: `brand/kinescript/` in
`oaustegard/muninn.austegard.com` (paper and night palettes from the site,
Fraunces, Source Serif 4, DM Mono, the raven mark, Muninn's voice). Copy that
folder into the project as `brand/` and set `"brand": "brand"`.

- **Find or make one.** `kine brand list` shows the library
  (`~/.kinescript/brands`). `kine brand init acme` makes one from the default
  Kinescript brand. `kine brand import acme logos/mark.svg` proposes dark and
  light palettes from a logo, each passing check's contrast; show the
  proposal to the person, then rerun the command with `--apply`. Over MCP, the
  `kine_brand` tool does each of these as an `action`.
- **Use it in the project.** `kine brand use acme` copies it into `brand/`.
  The scene says `"brand": "brand"` and, if it needs one, `"variant": "light"`.
  A later change to the library brand reaches the project only when you run
  `use` again, so old videos keep rendering the same.
- **Write scenes in the brand's names, not literals**: `"$accent"`, `"$text"`,
  `"textStyle": "heading"`, `"enter": "$motion.enter"`. The built-ins
  (titleCard, lowerThird, charts, logo, bug, sting, endCard) already draw in
  it. `"intro": true`, `"outro": true` and `"music": true` add the brand's
  sting, end card and music bed. Voices take the brand's speaker unless a
  sound names its own.
- **Change it through the tools**, not by editing `brand.json` by hand:
  `kine brand set acme palettes.dark.accent '"#ff633f"'`, `add-file`, or
  `kine brand wizard` for the person. Each write is checked; pass `--rev`
  (`base_rev`) from your last read so a change made meanwhile is not
  overwritten.
- **`kine check` reports brand problems**: `brand-locked` when the scene
  changes a part the brand locks (remove the override, don't remove the
  lock), and contrast and logo size issues for the brand's colours and
  placements.

## Avatars

An avatar (2.0) is a character that talks: its mouth follows a voice line's
words, and it blinks, breathes and glances on its own. `kine docs avatars` is
the reference.

- **Start from the built-in one.** `"avatar": "kine:host"` is a plain,
  friendly figure in the scene's palette with all nine mouth shapes and
  Kokoro's af_heart voice. `kine avatar new FOLDER` copies it as SVG parts to
  redraw. A brand can name avatars (`"avatar": "brand:host"`).
- **Make it talk with `say`**, which takes a line (`{"text": ...}`, spoken by
  `kine voice`), a sound id, or a list of them:
  `{"id": "host", "use": "avatar", "avatar": "kine:host", "x": "30%", "h": 600, "say": {"text": "..."}}`.
  Cue other layers from its words, e.g. `"at": "host-say:render"`.
- **Time the acting** as lists on the layer: `expressions`
  (`{"name": "smile", "at": ..., "dur": ...}`), `gestures` (`nod`, `wave`, ...)
  and `gaze` (`camera`, `left`, `#chart`, ...). Kinescript checks them but
  does not infer them from the text: you write them.
- **3D avatars** are a glTF file whose mouth, blink and expressions are morph
  targets by name, with gestures as the model's clips. `examples/avatar3d.json`
  is one, built from `examples/make_media.py`.
- **Check before rendering.** `kine avatar check FOLDER` validates a folder.
  `kine look FOLDER` draws every pose on one sheet; a broken pivot or a
  missing mouth shape shows there. `kine check` on the scene reports
  `mouth-approximate` (no word times), `avatar-missing-shape` and gesture
  overlaps.
- **Cost.** Drawn avatars cost little more than still pictures of them. A 3D
  head costs about as much as any model of its triangle count, moving or not.

## Narration

- **Pace.** Oskar wants narration at 165–180 wpm, energetic, with varied
  intonation. Punctuation pauses slow real narration well below the
  200–240 wpm a bare sentence gives at rate 1: lines of two or three
  sentences in the 2:1 fable/lewis blend measured 139 wpm at rate 0.78 and
  179 at 0.95. Start near `"rate": 0.95`, measure words ÷ speaking time from
  the words files after `kine voice`, and scale the rate.
- **Mix.** Give sounds a `role` and Kinescript levels them: voice at −18
  LUFS, music at −16 and ducked 14 dB under a voice, with no manual mixing.
- **Cue from words, not from the file start.** A Kokoro clip opens with
  0.3–0.4 s of silence.
- **Kokoro cannot raise its pitch for a question or act on tags such as
  `[laughs]`.** For a
  line that needs either, set that sound's `backend` to `elevenlabs` or
  `chatterbox` (see `kine docs`, SOUND).
- Muninn's voice is `"speaker": "bm_fable,bm_fable,bm_lewis"`, a 2:1
  blend of fable's rasp and lewis's low register.

## Gotchas seen in use

The version in brackets is the one where each was seen. Check it against
`kine docs` and the CHANGELOG before working around it.

- **A colour key takes `hsl()` only as an expression** (2.5.0). `"fill":
  "=hsl(200, 0.6, 0.5)"` works; `"fill": "hsl(200, 0.6, 0.5)"` is a
  `bad-colour` error. A scene builder can write hex instead.

- **Group children are placed from the group's anchor, not its top-left
  corner** (1.4.0). A centre-anchored group needs a child at `(-w/2, -h/2)`
  to fill it. `kine check` reports a misplaced child as off-screen.
- **`loop: true` does not lengthen a video layer** (1.4.0). Give the layer
  a `dur`.
- **Video and shader layers default to a top-left anchor** even when `x` is
  given (1.3.1, by design). Set `anchor` explicitly.
- **Capturing a web page as footage** frame by frame with Playwright's fake
  clock: call `page.clock.install()`, reload, then pause the clock and step
  it. Installing it after load stalls most games. WebGPU pages also need the
  GPU queue drained before each screenshot. The games promo's
  `capture/lib.cjs` does both.
- The Kinescript repo's `CLAUDE.md` mandates the maintainer's `c3_*` MCP
  tools. Where they are not installed, its first line says to use the usual
  tools.

## Contributing upstream

Work on a branch of `drknowhow/kinescript` and open a PR. Dimitri merges his
own work as PRs too, so never commit to its `main`. Run `python -m pytest` first. A visual change
also needs `kine check` and `kine look --boxes`.
