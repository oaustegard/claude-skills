---
name: animating-with-code
description: "Make a short animated film by writing the drawing code yourself: every frame a pure function of time, rendered headlessly to MP4. Covers storyboarding with a per-shot timing sheet of viewer 'reads', blocking key poses as stills, the contact-sheet / frame-strip / crop review loop, and the hand-painted character kit JohnHeibel/ClaudeAnimationBase (p5.js + p5.brush, the Clawd mascot, 31 emotions). Use for 'animate', 'make a cartoon', 'animated short', 'motion graphic', 'Clawd video', 'p5 animation', or any video request where Claude draws the frames. Not for AI-generated footage (creating-video), transcoding or trimming existing video (processing-video), or a comic from footage (drawing-video)."
metadata:
  version: 0.1.0
---

# Animating with code

You write the drawing; a headless browser (or PIL, cairo, ffmpeg) renders it. The
method below comes from the ClaudeAnimationBase kit's guide and holds for any
renderer. The kit itself is the fastest route to a hand-painted character short.

Before building, name the route and why (Oskar's standing steer, memory 06886186):
the kit, a CSS/HTML page captured frame by frame, a pure ffmpeg filtergraph, or
PIL/cairo frames.

## The contract: frames are pure functions of t

- A shot is `fn(t)`. Same `t`, same pixels. No counters, no state carried between
  frames, no integrated physics, no unseeded random. Then frames can
  render out of order, split across parallel workers, and resume after a crash.
- Stable per-object values come from a hash of an index. Deliberate wobble
  ("boil") comes from a seed that changes on a fixed clock (the kit uses 12 Hz,
  each drawing held two frames).
- Reseed per element. A moving element consumes a variable amount of randomness;
  without its own seed it shifts the stream for everything drawn after it and
  the still parts jitter every frame.

## Procedure

1. **Storyboard in writing, before any scene code.** One logline (wants ___, but
   ___, so ___), a small palette with a colour arc, a motif that pays off, and
   the emotion keys across the whole film. Then per shot: time span, transition
   in, the event, the reaction, the camera, and the **reads**.
2. **Write the reads.** A read is one thing the viewer must understand, with a
   start and end time. Each needs time for the eye to find it, to understand it,
   and to register before the next starts. No two important reads overlap. If
   they do not fit the shot, lengthen the shot or cut a read. Timing is where
   generated animation fails most: everything at one brisk speed, events stacked,
   moments gone before they land.
3. **Check the storyboard:** an event in every shot, a transition at every seam
   (including in and out of the film), no text, the ending rhymes with the opening.
   If a person is waiting, show them the storyboard before building.
4. **Block key poses as stills** at each shot's storytelling moments. If the
   poses do not read as stills, motion will not save them.
5. **Add motion between poses**, one shot at a time, in order: anticipation
   before big moves, slow in/out instead of raw lerp, arcs, overlapping action
   (eyes lead, body follows, appendages settle last), no twinning (offset left
   and right, offset characters' phases), exaggeration.
6. **Review loop** (below) on every shot. Fix, look again.
7. **Render** the full film; verify with `ffprobe` that duration and frame count
   match the config.

## Review loop

You cannot see motion by reading code. Render images and open them with Read.

| view | what it shows | catches |
|---|---|---|
| contact sheet | first, middle, last frame of every shot | missing events, small or lost characters, dead stretches |
| fixed-step sheet (every 0.1–0.15 s) | one shot, read in order | timing: where is the eye now, does the viewer get it yet |
| frame strip | every frame of a 0.5 s stretch | pops, snaps, missing anticipation, boil jitter on still parts |
| crop | full-res detail | faces, contacts (feet on ground, props in hands), muddy glows |
| crop following a world point | the same detail through a moving camera | contacts on camera moves |

Count frames per read (24 = 1 s). A read that gets a few frames, or shares its
frames with another read, will be missed. Budget: one sheet per shot, one strip
per key motion and per transition, one crop per face that carries the story.

## Rules from the kit's guide

Defaults, overridden by whatever the person asks for.

- **No text.** No captions, labels, signs, or words on screens. Reactions are
  painted marks (`!`, `?`, sweat, hearts, a bulb). A sign that restates the story
  is the classic failure.
- **Flat 2D, no projected 3D.** Turns go through drawn key views (front, 3/4,
  side, back 3/4, back) with smears. Depth from overlap, scale and paler, bluer
  colour.
- **Nothing still.** Idle motion per emotion, drifting cameras, swaying grass. A
  frozen frame reads as a bug.
- **Faces act, never snap.** Mood changes go squint, swap under the squint, take,
  overshoot, settle.
- **One beat.** A single BPM drives idles and bounces even with no music.
- **No pure black or white.** Additive light for glows: pigment-mixing brushes
  turn yellow-over-blue green.

## The ClaudeAnimationBase route

`https://github.com/JohnHeibel/ClaudeAnimationBase`, MIT, verified at commit
`0ac8bf2` (2026-09-24). Its `ANIMATION_GUIDE.md` (36 KB) is the full API: read it
whole before drawing. `render.mjs` provides the review views as flags
(`--sheet=`, `--strip=a:b`, `--crop=x,y,w,h`, `--crop-at=`, `--stills=`, `--clip`,
`--frames --workers=N` + `--encode`).

Recipe for a CCotw container, verified 2026-10-25 (4 CPUs, no GPU, Chromium at
`/opt/pw-browsers/chromium-*/chrome-linux64/chrome`):

```bash
SCRATCH=/path/outside/the/checkout   # the session scratchpad
CHROME=$(ls -d /opt/pw-browsers/chromium-*/chrome-linux64/chrome | tail -1)
git clone --depth 1 https://github.com/JohnHeibel/ClaudeAnimationBase /tmp/jail/cab
# deps from the registry, outside the checkout, no install scripts; versions from package-lock.json
mkdir -p "$SCRATCH/cabdeps" && cd "$SCRATCH/cabdeps" && npm init -y >/dev/null \
  && npm install --ignore-scripts p5@2.3.3 p5.brush@2.2.3 puppeteer-core@25.11.0
cp -r "$SCRATCH/cabdeps/node_modules" /tmp/jail/cab/
sed -i '/fonts.googleapis.com/d' /tmp/jail/cab/studio.html          # only letter() uses it
sed -i "s/{ waitUntil: 'networkidle0' }/{ waitUntil: 'networkidle0', timeout: 0 }/; s/{ timeout: 60000 }/{ timeout: 0 }/" /tmp/jail/cab/render.mjs
chown -R nobody:nogroup /tmp/jail/cab
sh scripts/jail.sh -C /tmp/jail/cab -- node render.mjs --soft-gl \
  --chrome="$CHROME" \
  --sheet=0.5,2,4,6,8,10 --cols=3 --w=480 --out=out/sheet.jpg
```

In claude-workspace, run the kit only inside `scripts/jail.sh` (hub rule for
code nobody here wrote). Elsewhere, drop the jail prefix.

**Cost.** Under SwiftShader the demo's six-frame sheet took 0.3, 0.2, 36, 47, 40
and 42 s per frame. At ~40 s, the 11 s demo (264 frames) is about 3 hours on one
worker. Before a full render, either ask the scene to avoid p5.brush watercolour
`fill` (the kit's README suggests this for machines without a GPU), split across
`--frames --workers=N` and run it as a background job, or render on a GPU host
(`--gpu-angle=gl-egl|vulkan`). The review loop stays cheap: sheets and strips
render a handful of frames.

## Failure signals

| signal | cause | fix |
|---|---|---|
| `connect ENETUNREACH 127.0.0.1:<port>` from puppeteer | network namespace with `lo` down | claude-workspace `scripts/jail.sh` raises `lo` since 711fac1; pull the hub |
| `Navigation timeout of 30000 ms exceeded`, with `ERR_INTERNET_DISCONNECTED` | page waits on Google Fonts with no network | delete the fonts link |
| same timeout, no failed request | p5.brush init takes ~20 s under SwiftShader | `timeout: 0` on `goto` and `waitForFunction` |
| `Failed to construct 'OffscreenCanvas': Value is not of type 'unsigned long'` | a NaN in a point list; the stack points at the scene, not the NaN | guard degenerate geometry (`Math.acos` of a ratio > 1) |
| an outline collapses to a dot at zoom ≥ 2 | stroke drawn far from the origin | draw long edges as `inkLine`s no bigger than the canvas |
| still parts flicker in a strip | shared random stream behind a moving element | `boilSeed(key)` before each element |
| five `WebGL: INVALID_OPERATION ... not from the associated program` warnings | p5.brush, once per page | harmless; any other page error is real |

## Verification

Open every sheet and strip with Read and look before calling a shot done. For the
final file, this must match the config's duration and fps:

```bash
ffprobe -v error -show_entries format=duration:stream=nb_frames,r_frame_rate -of default=nw=1 out/video.mp4
```
 Report
the route used, the render time per frame, and anything the review loop found
that you did not fix.
