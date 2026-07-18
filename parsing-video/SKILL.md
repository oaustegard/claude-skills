---
name: parsing-video
description: "Interpret video content visually by sampling frames into timestamped contact sheets that can be read as images. Use when: user asks what happens in a video; asks to summarize, describe, review, or QA video content or footage; asks about scenes, actions, people, or objects in a video; needs a storyboard-style overview of a clip; asks to find where something occurs in a video. Triggers on 'watch this video', 'what's in this video', 'summarize the video', 'describe the footage', 'contact sheet', 'storyboard', 'review this clip', 'find the scene where'. For converting, trimming, or transcoding video, use processing-video instead."
metadata:
  version: 0.1.0
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

## Interpreting honestly

- Report what is visible in the sampled frames; events between samples are invisible. Say "between 1:30 and 1:40 the scene changes from X to Y", not fabricated specifics about the transition.
- Fast action (a ball in flight, a single gesture) can fall entirely between samples — tighten the window and re-sheet before concluding something didn't happen.
- Timestamps are accurate to ~1 s (seek + rounding), fine for general video.

## Limits — when NOT to use contact sheets

- **Fine print, dense text, small UI details**: tiles are ~380 px wide; text becomes unreadable. Extract full-resolution frames at the relevant timestamps instead.
- **Audio content**: sheets are silent. If speech matters, extract the audio (`ffmpeg -i in.mp4 -vn audio.mp3`) and transcribe it separately; note to the user if no transcription path is available.
- **Frame-exact analysis** (sports officiating, VFX QC): sampling misses frames by design; extract every frame in a narrow window (`ffmpeg -ss 84 -to 86 -i in.mp4 frames_%03d.png`).

For transformation tasks — convert, trim, merge, compress, GIF, subtitles — use the **processing-video** skill.
