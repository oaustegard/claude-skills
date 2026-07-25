---
name: parsing-video
description: "Interpret video content visually by sampling frames into timestamped contact sheets that can be read as images. Use when: user asks what happens in a video; asks to summarize, describe, review, or QA video content or footage; asks about scenes, actions, people, or objects in a video; needs a storyboard-style overview of a clip; asks to find where something occurs in a video. Triggers on 'watch this video', 'what's in this video', 'summarize the video', 'describe the footage', 'contact sheet', 'storyboard', 'review this clip', 'find the scene where', 'scene detection', 'shot boundaries', 'detect cuts', 'dwell points'. For converting, trimming, or transcoding video, use processing-video instead."
metadata:
  version: 0.4.0
---

# Parsing Video

Claude cannot play video, but it can read images. To interpret a video, sample frames evenly across its duration, tile them into timestamped **contact sheets**, and Read the sheets. A 4×4 sheet compresses ~16 moments into one image, preserving narrative flow — what changed, in what order, roughly when.

Requires ffmpeg/ffprobe (`apt-get update && apt-get install -y ffmpeg` if missing).

## Workflow

### 1. Probe first

```bash
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4
```

Note duration, resolution, and whether there's an audio stream. Duration drives how many sheets you need.

### 2. Generate contact sheet(s)

```bash
python3 scripts/contact_sheet.py input.mp4                          # 1 sheet, 4x4, whole video
python3 scripts/contact_sheet.py input.mp4 --sheets 3               # 48 frames across 3 sheets
python3 scripts/contact_sheet.py input.mp4 --start 120 --end 300    # zoom into 2:00–5:00
python3 scripts/contact_sheet.py input.mp4 --grid 3x3 --tile-width 500  # fewer, larger tiles
```

The script probes duration, samples frames at interval midpoints, stamps each tile with its source timestamp (`H:MM:SS`, bottom-left), and tiles them into `<name>_sheet_NN.png`. It prints each sheet's time range.

**Sheet budget** — more sheets = more Read calls; scale to duration and task:

| Duration | Sheets | Sampling interval |
|---|---|---|
| < 2 min | 1 (4×4) | ~4–7 s |
| 2–10 min | 2–4 | ~10–40 s |
| 10–60 min | 4–8, or coarse-then-zoom | ~1–2 min |
| > 1 hour | coarse pass, then zoom | varies |

### 3. Read and interpret

Read each sheet image. Tiles run left-to-right, top-to-bottom in time order; use the stamped timestamps to anchor observations ("the scene changes around 1:42"). Cross-sheet continuity: the last tile of sheet N immediately precedes the first tile of sheet N+1.

### 4. Zoom when needed

Contact sheets trade resolution for coverage. When something needs a closer look:

```bash
# Re-sheet a narrower window at higher tile resolution
python3 scripts/contact_sheet.py input.mp4 --start 95 --end 125 --grid 3x3 --tile-width 500

# Or extract a single full-resolution frame at the moment of interest
ffmpeg -ss 00:01:42 -i input.mp4 -frames:v 1 detail.png
```

## Content-aware sampling

Uniform sampling guarantees temporal coverage but ignores structure: it can straddle a cut mid-interval, waste tiles on a static shot, or land mid-pan on a motion-blurred frame. Two refinements, both feeding `--at`. Choose by footage type: **edited content** (films, trailers, TV) → shot boundaries; **continuously shot footage** (handheld, drone, screen recordings, dashcam) → dwell points; unknown → uniform first, refine after.

### Shot boundaries (cuts)

Detect cuts and align tiles to them:

```bash
# ffmpeg scene score: frames whose difference from the previous frame exceeds 0.3
TS=$(ffmpeg -i input.mp4 -vf "select='gt(scene,0.3)',metadata=print:file=-" -f null - 2>/dev/null \
     | grep -oP 'pts_time:\K[0-9.]+' | paste -sd,)
python3 scripts/contact_sheet.py input.mp4 --at "$TS"
```

Each selected frame is the *first frame of the new shot* (the score compares against the previous frame). Threshold 0.3–0.4 suits most content; lower it for subtle cuts, raise it for noisy footage.

**Know what scene detection misses.** The scene score is a frame-pair difference metric:

- **Gradual transitions** (dissolves, fades, wipes) spread the change across many frames, each below threshold — they often go undetected.
- **Within-shot content changes**: between two cuts, objects can enter, leave, or change substantially with no boundary ever firing. A long static-camera shot with lots of action yields *one* tile under pure scene-aligned sampling.
- **Camera motion** (pans, handheld shake) can fire false positives.

So treat scene-aligned sampling as a **refinement, not a replacement**: run uniform sheets first for guaranteed temporal coverage, then a scene-aligned sheet (or a union of both timestamp sets via `--at`) when shot structure matters. If cut detection quality itself matters, the purpose-built tool is **PySceneDetect** (`uv pip install --system scenedetect[opencv-headless]`, then `scenedetect -i input.mp4 list-scenes`) — its content/adaptive detectors are more robust to motion and noise than the raw ffmpeg score, but they are still cut-oriented and share the within-shot blindness above.

### Dwell points (where the camera settles)

In continuously shot footage cuts are rare or absent — the structure lives in camera *moves*. In the frame-difference signal, held compositions are the **valleys** and pans/zooms are the **peaks** between them. The valley midpoints are the frames worth sampling: sharp, deliberately framed, one per composition — where uniform sampling would land mid-pan on smeared pixels.

```bash
python3 scripts/contact_sheet.py input.mp4 --at "$(python3 scripts/dwell_points.py input.mp4 --max 16)"
```

`dwell_points.py` computes the motion signal cheaply (4 fps at 160 px via ffmpeg's scene metric), smooths it over ~1 s, and takes spans below a **relative** threshold (default p40 of the signal) lasting at least `--min-dwell` (1 s). It keeps the `--max` longest holds and prints their midpoints; stderr lists each hold span with its duration so you can see the video's rhythm before reading a single frame.

Caveats:
- The threshold is relative, so on **constant-motion footage** (one unbroken pan) it degrades to picking the least-motion moments — harmless but arbitrary; prefer uniform sampling there. It exits non-zero when no hold lasts `--min-dwell`.
- **Subject motion during a held shot** (a person gesturing in a static frame) raises the valley floor but rarely fills it; if a busy-but-held shot is missed, lower `--percentile`.
- Dwells say where the camera settled, not what changed — combine with uniform coverage for anything time-critical.

## Overseeing a multi-clip edit

When acting as the editing agent over a generated or assembled cut (see the
**creating-video** skill), review at two levels:

1. **The whole assembly.** Contact-sheet the *final stitched cut*, not just the
   individual clips. Per-clip sheets each look fine in isolation; character drift,
   prop jumps, and logic breaks only appear when the shots sit in sequence. One
   4×4 sheet over a 30 s cut gives ~2–3 tiles per scene — enough to catch them.

2. **The seams.** A cut hides continuity errors at the boundary — the outgoing
   clip's last frame vs the incoming clip's first frame. `scripts/seams.py` pairs
   them, one row per cut, for a one-look check:

   ```bash
   python3 scripts/seams.py clip1.mp4 clip2.mp4 ... clipN.mp4 --out seams.png
   ```

Read every sheet against the **continuity checklist** for generated video:

- **Character** — same face/hair/wardrobe across every shot they appear in.
- **Prop** — same identity, size, color, and attachment point shot to shot
  (the classic failure: a small object that changes size or moves between shots).
- **Physical logic** — is the world coherent across the cut (a window open before
  something enters through it; an action's result matching its setup)?
- **Action completeness** — is the key beat actually *shown*, not cut around?

Report which scene or seam fails and what the fix is (tighten the prompt, or
regenerate just that shot) — that verdict is the deliverable the editing agent
acts on.

## Interpreting honestly

- Report what is visible in the sampled frames; events between samples are invisible. Say "between 1:30 and 1:40 the scene changes from X to Y", not fabricated specifics about the transition.
- Fast action (a ball in flight, a single gesture) can fall entirely between samples — tighten the window and re-sheet before concluding something didn't happen.
- Timestamps are accurate to ~1 s (seek + rounding), fine for general video.

## Limits — when NOT to use contact sheets

- **Fine print, dense text, small UI details**: tiles are ~380 px wide; text becomes unreadable. Extract full-resolution frames at the relevant timestamps instead.
- **Audio content**: sheets are silent. If speech matters, extract the audio (`ffmpeg -i in.mp4 -vn audio.mp3`) and transcribe it separately; note to the user if no transcription path is available.
- **Frame-exact analysis** (sports officiating, VFX QC): sampling misses frames by design; extract every frame in a narrow window (`ffmpeg -ss 84 -to 86 -i in.mp4 frames_%03d.png`).

For transformation tasks — convert, trim, merge, compress, GIF, subtitles — use the **processing-video** skill.
