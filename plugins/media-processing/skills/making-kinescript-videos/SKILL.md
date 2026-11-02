---
name: making-kinescript-videos
description: "Make an MP4 from a JSON scene file with Kinescript (drknowhow/kinescript, the `kine` CLI): text, shapes, charts, SVG, images, video clips, particles and 3D models on cue-based timing, with a checker that lints layout, contrast, reading time and the sound mix, and narration spoken by Kokoro TTS with word-level cues and captions. Covers setup in a Linux container (CPU backend, Python 3.12 venv for Kokoro), the write → voice → check → look → render loop, and controlling Kokoro's pronunciation, stress, pauses, pace and voice blends. Use for 'kine', 'Kinescript', 'kinescript scene', 'kine voice', 'narrated promo', 'explainer video', 'motion graphics video', 'video with voice-over and captions', 'Kokoro pronunciation', 'TTS says a name wrong', 'make the narrator emphasise', or any video built from type, shapes and captured footage."
metadata:
  version: 0.1.1
---

# Making videos with Kinescript

Kinescript renders a JSON scene to video with Skia and ffmpeg. Layers start
and end on cues (`"at": "title.out+0.2"`) rather than on hand-summed seconds,
and every frame is a pure function of the scene and the frame number. The
`kine` CLI also lints the scene (`check`), draws labelled contact sheets
(`look`) and speaks narration (`voice`). Oskar and Muninn contribute to it as
collaborators on `drknowhow/kinescript`, through branches and PRs.

Upstream moves fast: 1.0 to 1.6.1 shipped in the three days from 2026-10-29
to 11-01. **`kine docs` is the authoritative reference for the installed
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

- `pyproject.toml` allows skia-python ≥ 87, but 138.0 failed at `space.py:79`
  (`skia.M44` has no `Rows`) on 2026-11-01. Pin ≥ 144.
- With no GPU, `KINE_BACKEND=cpu` is used. Expect 3–7 fps at 1080p. The
  1650-frame games promo took 231 s at `-j 4`.
- **In `claude-workspace` sessions**, Kinescript is code nobody there wrote,
  so `kine` runs inside `scripts/jail.sh` (the hub's rule). Install from PyPI
  outside the jail.

### Kokoro for `kine voice`

Kokoro needs Python 3.10–3.12. If the system Python is newer, put the plugin
in its own venv and point `KINE_VOICE_CMD` at it:

```bash
uv venv -p 3.12 ~/kokoro-env
VIRTUAL_ENV=~/kokoro-env uv pip install --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu torch kinescript-kokoro
export KINE_VOICE_CMD="$HOME/kokoro-env/bin/python -m kinescript_kokoro"
export VIRTUAL_ENV=~/kokoro-env   # misaki fetches en_core_web_sm through uv on first use, which needs this
```

The CPU torch index avoids a multi-GB CUDA download. The first `kine voice` run downloads the model
(327 MB) and spaCy's small English model.

## Procedure

1. **Read `kine docs`** for layer types, cue syntax, motions and the sound rules.
   `kine new` writes a starter scene.
2. **Storyboard in writing**: scenes, their order, and one read per scene. For
   anything longer than a few layers, generate the scene from a Python builder
   that holds one timeline array (the games promo's `kine/build_scene.py` in
   `oaustegard/experiments` is the model). Don't hand-edit 500 lines of JSON.
3. **Narration**: give each voice sound a `text`, a `speaker` and a `rate`, then
   `kine voice scene.json`. It re-speaks only sounds whose text, speaker or rate
   changed. Mark words with `[[id]]` to cue layers from them (`"at": "vo1:go"`).
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
6. **Render**: `kine render scene.json -o out.mp4 -q high -j 4`. Run it as a
   background job if it will outlive the turn.
7. **Verify** the file: `ffprobe` for size, fps and duration, a frame strip
   (`ffmpeg -vf "select='not(mod(n\,90))',scale=270:-1,tile=8x2"`), and a
   listen to the voice track.

## Narration

- **Pace.** Oskar's target is 165–180 wpm, energetic, with varied
  intonation (memory 3eb81ac6). Kokoro voices run 200–240 wpm at rate 1, so
  start near `"rate": 0.8` and measure from the words file.
- **Mix.** Give sounds a `role` and Kinescript levels them: voice at −18
  LUFS, music at −16 and ducked 14 dB under a voice. The games promo came
  out at −16.1 LUFS and −2.0 dBTP with no manual mixing.
- **Cue from words, not from the file start.** A Kokoro clip opens with
  0.3–0.4 s of silence.
- **Kokoro cannot raise its pitch for a question or act on `[tags]`.** For a
  line that needs either, set that sound's `backend` to `elevenlabs` or
  `chatterbox` (see `kine docs`, SOUND).
- Muninn's own voice is `"speaker": "bm_fable,bm_fable,bm_lewis"`, a 2:1
  blend chosen in September for fable's rasp and lewis's low register.

## Gotchas seen in use

Each gotcha is dated with the version it was seen in. Check it against
`kine docs` and the CHANGELOG before working around it.

- **Group children are placed from the group's anchor, not its top-left
  corner** (1.4.0). A centre-anchored group needs a child at `(-w/2, -h/2)`
  to fill it. `kine check` reports a misplaced child as off-screen.
- **`loop: true` does not lengthen a video layer** (1.4.0). Give the layer
  a `dur`.
- **Video and shader layers default to a top-left anchor** even when `x` is
  given, by design and documented since 1.3.1. Set `anchor` explicitly.
- **Captures for footage**: with Playwright's fake clock, install the clock,
  reload, then pause. Freezing it after load stalls most games. WebGPU pages
  also need the GPU queue drained before each screenshot. Both are from the
  games promo, `oaustegard/experiments` `games-promo/`.
- The repo's own `CLAUDE.md` mandates `c3_*` tools. Where they are not
  installed, its own first line says to use the usual tools.

## Contributing upstream

Work on a branch of `drknowhow/kinescript` and open a PR. Dimitri merges his
own work as PRs too, so don't commit to `main` there, whatever the hub's
commit-to-main rule says. Run `python -m pytest` first. A visual change
also needs `kine check` and `kine look --boxes`.
