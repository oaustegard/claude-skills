---
name: making-remotion-videos
description: "Make an MP4 from React components with Remotion, rendered headlessly in this container. Covers project scaffolding with pinned versions, the frame-pure composition contract, the still-frame review loop, rendering with the preinstalled Chromium, and the product demo reel - an app shown inside a phone frame, built from Playwright captures of the real UI. Use for 'Remotion', 'make a video in React', 'demo reel', 'promo video for my app', 'app preview video', 'product video', 'phone mockup video', 'vertical video for social', 'Instagram reel', 'TikTok-format video', 'animated explainer with text and screenshots', or any motion graphics job built from layout, type and UI captures."
metadata:
  version: 0.2.4
---

# Making videos with Remotion

Remotion renders a React component once per frame in headless Chromium and
encodes the frames with ffmpeg. The DOM and CSS are the drawing API, so type,
layout, screenshots and UI mockups come out sharp and on-brand with little code.
Each frame is a pure function of `useCurrentFrame()`.

Before building, name the route and why (Oskar's standing steer, memory
06886186). Remotion fits when the video is mostly type, layout, product UI and
2D motion. It is not the cheapest route for particle fields or generative art.

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| Hand-drawn character animation, p5.js, painterly frames | `animating-with-code` |
| AI-generated footage (Veo, Gemini video) | `creating-video` |
| Trim, transcode, concatenate or caption existing footage | `processing-video` |
| A comic or storyboard drawn from existing footage | `drawing-video` |
| A looping in-page animation the user views in a browser | an HTML artifact; no render needed |

Abandon Remotion mid-run when a frame takes more than about 5 s to render after
the bundle is built. That points to heavy WebGL or canvas work, which a
pre-rendered frame sequence or a native ffmpeg/numpy route does better.

## Procedure

1. **Scaffold** with pinned versions (all `@remotion/*` packages at one exact
   version, at least two weeks old):
   ```bash
   bash /mnt/skills/user/making-remotion-videos/scripts/scaffold.sh /path/to/project
   ```
   It writes `package.json`, `tsconfig.json`, `src/index.ts`, a hello `Root.tsx`,
   copies the phone and scroll components into `src/`, and runs `npm install`
   (about 40 s).
2. **Vendor the fonts.** Never use `@remotion/google-fonts` here: see failure
   modes below.
   ```bash
   cd /path/to/project
   python3 /mnt/skills/user/making-remotion-videos/scripts/vendor_fonts.py "Instrument Serif:ital@0;1" "DM Sans:wght@400;700"
   ```
   Paste the printed `loadFont()` calls into a `theme.ts` that every scene imports.
3. **Prove the toolchain** before writing scenes:
   ```bash
   bash /mnt/skills/user/making-remotion-videos/scripts/render.sh still Main out/probe.png 45
   ```
4. **Storyboard in writing.** List the scenes with frame durations and one *read*
   each: the single thing the viewer must take away. A caption needs about
   1.5 s plus 0.3 s per word on screen. Put durations in a data array and
   derive the total from it. Never hand-sum frame counts.
5. **Build scenes** under the contract below. Sequence them with
   `TransitionSeries` from `@remotion/transitions`. Each transition overlaps
   its neighbours, so the total is the sum of durations minus the transition
   lengths. Compute that in code and export it to `<Composition>`.
6. **Review loop with stills.** Render one still per read (the frame where it
   should be fully legible) and tile them into a contact sheet. Look at it before
   rendering any video.
   ```bash
   for f in 40 100 260 530; do bash .../render.sh still Main out/s$f.png $f; done
   montage out/s*.png -tile 4x1 -geometry 360x640+6+6 out/sheet.png
   ```
   Fix layout collisions, illegible type and dead frames here: a still costs
   about 3 s and a full render minutes.
7. **Render** the video in the background if it will outlive the turn (the
   hub's long-job rule):
   ```bash
   bash .../render.sh video Main out/reel.mp4
   ```
8. **Verify** (next section), then deliver. Keep sources and captures in git and
   the MP4 out of git unless it is small. Upload large renders to R2 or a
   release.

## The composition contract

- Every visual value derives from `useCurrentFrame()` through `interpolate`,
  `spring` or plain arithmetic. No `useState` timers, no `setTimeout`, no
  CSS `animation`/`transition`. Remotion seeks frames in any order across
  parallel tabs, so a CSS animation renders as a random phase or not at all.
- Randomness comes from `random(seed)` in `remotion`, never `Math.random()`.
- Assets load through `staticFile()` from `public/` with `<Img>`, `<Video>`
  (`@remotion/media`) or `<Audio>`. These hold the frame until loaded. A plain
  `<img>` does not, and the frame renders blank.
- Async data (fetch, fonts outside `@remotion/fonts`) wraps in
  `delayRender()` / `continueRender()`, or goes through `calculateMetadata`.
- Pass `extrapolateLeft/Right: "clamp"` to every `interpolate` that should hold
  its end value. The default extrapolates, so a fade continues past 0 and 1.
- Keep the canvas at the delivery size (1080×1920 for vertical, 1920×1080 for
  landscape) and design in those pixels. Scaling a smaller composition up
  softens type.

## Product demo reels

For a reel of a real web app inside a phone, follow
[references/product-reel.md](references/product-reel.md). It covers capturing
the live UI at phone size with Playwright, stepping live animations frame by
frame with Playwright's fake clock, the phone frame, sticky headers, tap
indicators and the timeline the aeyu.io reel used.

## Narration

Mix the voiceover outside Remotion into one WAV the length of the
composition. Put each line at its slot start, apply linear gain only (peaks at
about −2 dBFS; never `loudnorm`, see below), and play it with `<Html5Audio src={staticFile(vo)} />` at the root. Pass the
track as a prop (`--props='{"vo":"vo/x.wav"}'`) so voice A/B tests reuse one
composition. Write the script as lines with `start`/`end` slots taken from the
scene timeline, then size each line to its slot: words ÷ slot seconds × 60
should be 140–180 wpm.

- **TTS routes, measured 2026-10-29 on the aeyu reel** (details in
  [references/narration.md](references/narration.md)): Gemini 3.8 Flash TTS
  (`invoking-gemini` `generate_speech`, prebuilt or designed voice, style
  string) took 2.5 min for 27 takes and had the most varied pitch. OmniVoice
  (k2-fsa, the engine behind VoiceStudio) runs locally in the jail at about 29×
  slower than real time on 4 CPU cores. Its tag-based voice design (gender,
  age, pitch, accent) cannot ask for energy and came out flat. Cloning a
  lively 6 s reference worked better, and its per-line `duration` argument
  sets pace exactly.
- **Take three per line and pick by ASR.** Score each take with faster-whisper
  WER against the script, then pick the longest one that fits its slot.
  Gemini rendered "Year bests" as "your best" in 6 of 6 takes, with or without
  CAPITALS stress; "Best of the YEAR" survived 3 of 3.
- **A coined name: test it by ear, and spell it if voices mangle it.** ASR
  cannot judge it, since it mapped all eight mangled readings of "aeyu" to one
  transcript. See references/narration.md.
- **Record a coined name once and splice the clip** into every line that says
  it. Pick its spelling by generating 3 takes per candidate and keeping the one
  whose takes all transcribe alike. OmniVoice takes CMU phonemes inline:
  `[EY1 Y UW0]`.
- **Fill the slot, don't just fit it.** Oskar on the aeyu reel: "weirdly
  hurried, then with a gap between slides". Lines that merely fit ran at
  180–280 wpm and left up to 1.7 s of silence before each cut. Size each line to
  about 160 wpm over its slot, cap pauses inside a take at about 0.2 s, and
  pick or stretch (0.92–1.12×) each take to end about 0.25 s before the next
  line.
- **Check pace, not just fit.** Unpaced OmniVoice averaged 211 wpm with lines
  at 283. A take that fits its slot can still be rushed.
- **Verify the mix:** `ffmpeg -i out/reel.mp4 -af silencedetect=noise=-40dB:d=0.25 -f null -`
  lists the speech onsets, which should match the slot starts. `-af ebur128=peak=true`
  gives integrated loudness and peak.
- **Don't loudness-normalize TTS up to −16 LUFS.** TTS already peaks near
  0 dBFS (the aeyu mix measured −21.1 LUFS with peaks at −1.1 dBFS), so a
  single-pass `loudnorm` to −16 adds about 5 dB of limiting. Oskar heard it
  as "amplified too much". Linear gain to a −2 dBFS peak landed at about
  −22 LUFS and kept the speech's dynamics.

## Verification

```bash
ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate:format=duration -of default=nw=1 out/reel.mp4
ffmpeg -v error -i out/reel.mp4 -vf "select='not(mod(n\,90))',scale=270:-1,tile=8x2" -frames:v 1 out/strip.png
```

Expect `h264`, the composition size, `yuv420p`, the composition fps and a duration
of total frames divided by fps. Then read the strip. A *bad success* is a
file that probes correctly but has blank screens where an `<img>` raced its
load, fallback serif type where a font failed, or a scene that never appears
because a duration constant was wrong. Only looking at frames catches these.

## Common failure modes

- **`ERR_CERT_AUTHORITY_INVALID` on fonts.gstatic.com, then `TypeError: Failed to
  fetch`, and the render aborts** → the render browser does not trust the
  egress proxy's CA, though curl does. Vendor fonts with `vendor_fonts.py`.
  The same applies to any HTTPS asset fetched during render: download it into
  `public/` first. Diagnosed 2026-10-29 on the aeyu.io reel. Every still failed
  until fonts went local.
- **`"browserExecutable" was specified as ... but the path doesn't exist`** →
  the Playwright headless shell lives at
  `/opt/pw-browsers/chromium_headless_shell-<rev>/chrome-headless-shell-linux64/chrome-headless-shell`,
  with `-linux64` in the directory name. `render.sh` globs for it. Without the
  flag Remotion tries to download Chrome Headless Shell.
- **Output probes as `yuvj420p`** → the default for the probe render. Some
  players and uploaders mishandle full-range video. `render.sh` passes
  `--pixel-format=yuv420p --color-space=bt709`.
- **Text below the caption collides with the next element** → layout was
  designed at one scale and an element was resized later. Catch it on the
  contact sheet: the aeyu reel's first sheet had every subtitle under the
  phone's top edge.
- **The video is shorter than planned and the last scene is cut** → total
  duration was hand-summed while `TransitionSeries` overlaps. Derive it.

## Cost on this box

4 cores, 15 GB. The bundle step takes about 15 s per invocation, including
for stills. The 35.5 s aeyu reel (1065 frames, 1080×1920, four full-page
screenshots and 285 captured frames) rendered in 79 s at the default
concurrency of 4, to a 5.5 MB file at crf 20.
