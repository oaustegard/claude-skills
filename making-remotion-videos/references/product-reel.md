# Product demo reel: a web app inside a phone

The protocol behind the aeyu.io reel (2026-10-29, sources in
`oaustegard/experiments` `aeyu-demo-reel/`). The output is a 1080×1920 vertical
video of 30 to 40 s: title, hook, five app shots inside a phone frame with a
caption each, a trust or differentiator beat, and a call to action.

## 1. Find a demo state

Real UI with sample data beats mockups. Look for a demo route
(`/demo`, `?demo=1`), a seeded test account or a fixture loader. aeyu.io has
`/demo`, which loads canned rides into IndexedDB without OAuth. Never capture a
signed-in session holding a real person's data.

## 2. Capture at phone size

Copy `assets/capture_ui.cjs` into the project as `capture/capture.cjs` and edit
`SHOTS`. Three kinds of capture:

| Kind | How | Used in Remotion as |
|---|---|---|
| Scrollable screen | `page.screenshot({ fullPage: true })` at 390 CSS px wide, DPR 3 | `<ScrollShot>` with scroll keyframes |
| Live animation (canvas, WebGPU, rAF) | `freezeClock()`, start it, then `sequence()` | `<FrameSequence>`, one capture per output frame |
| Positions | `getBoundingClientRect()` plus scroll offset → `layout.json` | tap points, scroll targets, sticky header height |

Rules, each paid for once:

- **Set the viewport to 390×844 yourself.** Playwright's `iPhone 14` preset is
  390×664 (Safari's toolbars subtracted). Frames captured with it stop at
  three quarters of the phone screen, and the rest renders as empty
  background. Diagnosed 2026-10-29: the replay and heatmap shots both came back
  1170×1992 instead of 1170×2532.
- **Step animations with the fake clock, not a screencast.** A real-time CDP
  screencast of a WebGPU heatmap on SwiftShader delivered 4 fps. With the
  clock frozen (`install()` then `pauseAt()`), `fastForward(step)` then
  `runFor(34)` then a 40 ms real wait gives exact, evenly spaced frames
  however slow the renderer is. Choose `step`
  = animation length ÷ output frames, so a 20 s app animation shown in 4.5 s
  is 135 frames of 148 ms each.
- **Click controls by exact accessible name.** `aria-label*="lay"` and `/play/i`
  both matched aeyu's "Make a 30 second replay video" before "Play replay". The
  capture then recorded 150 frames of an export progress counter over a still
  scene. Diagnosed 2026-10-29. Use `getByRole('button', { name: 'Play replay',
  exact: true })`.
- **`clock.install()` does not freeze time.** Playwright's fake clock keeps
  ticking at real speed until `clock.pauseAt()`. A WebGPU screenshot takes
  about a second, so each frame let the app run ahead. A 30 s replay finished
  by frame 13 of 150 whatever the step size, and the heatmap by mid-sequence.
  A probe on about:blank looked correct because little real time passed
  between its steps. Diagnosed 2026-10-29 after two wrong theories ("the
  label is nominal", "rAF timestamps differ"). The template's `freezeClock()`
  calls `install()` and then `pauseAt()`.
- **Check that the motion spreads across the sequence.** Diff each frame
  against the last: `compare -metric AE -fuzz 2% fNNNN.jpg f0149.jpg null:`
  should stay non-zero until near the end. A run of zeros early means the
  animation finished early (a running clock, or a span set too long). A run of
  zeros from frame 0 means nothing started.
- `runFor(TICK)` also advances page time. The template computes each step as
  page time per frame minus `TICK`.
- **One page per motion shot.** After `freezeClock()` a page's timers only
  move when you advance them, so later `waitForTimeout` calls on it wait for
  nothing.
- **WebGPU needs flags:** `--enable-unsafe-webgpu --enable-features=Vulkan
  --use-vulkan=swiftshader --use-angle=swiftshader --use-webgpu-adapter=swiftshader`,
  launched from `/opt/pw-browsers/chromium`. Without `--use-vulkan=swiftshader`
  the canvas stays blank.
- The aeyu capture of 4 stills plus 285 sequence frames took about 12 min.
  Run it with `run_in_background`.

## 3. Compose

Components in `assets/components/` (the scaffold copies them):

- `Phone`: bezel, status bar, island and home indicator around a
  `SCREEN_W`-wide screen. `K = SCREEN_W / 390` converts page CSS px to
  composition px. Colour the status bar like the app's header.
- `ScrollShot`: full-page capture scrolled by `[{f, y}]` keyframes (eased).
  `stickyH` re-draws the top of the same image as a fixed header, as the
  live app's sticky header behaves.
- `FrameSequence`: plays `dir/f0000.jpg…` at one capture per frame.
- `Tap`: touch indicator (dot, then expanding ring) at composition coordinates.

Layout at 1080×1920 that held up: the phone at `SCREEN_W = 700` scaled 0.86,
top at y = 330. The caption block sits above it (82 px serif headline, 36 px
sans subline, top 70) and a small wordmark below it. At scale 1.0 the phone
covered the caption's second line.

Timeline that read well (30 fps, 15-frame transitions):

| Scene | Frames | Read |
|---|---|---|
| Title | 90 | wordmark and tagline |
| Hook | 120 | the contrast the product exists for, in two lines |
| Phone shots ×5 | 150, 150, 150, 135, 135 | one feature each: caption plus motion |
| Differentiator | 120 | the one claim competitors cannot make |
| CTA | 135 | icon, wordmark, URL in a button |

Inside the phone, `slide({direction: "from-right"})` between screens reads
as navigation. Use `fade()` where the next shot continues the same page,
as when the replay scrolls down to the awards. Run the captions as a second
`TransitionSeries` with the same durations so they change with the screen.

Use the product's own tokens: copy colours and fonts from its CSS `:root`. The
reel then looks like the app it shows.

## 4. Review and render

Contact sheet of one still per caption, then a frame of each motion shot at its
start, middle and end. Check that captured frames fill the screen and that the
animation visibly advances. Render with `scripts/render.sh video`.
