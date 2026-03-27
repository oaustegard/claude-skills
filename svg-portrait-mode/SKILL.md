---
name: svg-portrait-mode
description: "Portrait Mode" for SVGs — sharp detailed subjects, simplified backgrounds. Uses MediaPipe segmentation + image-to-svg pipeline for layered processing. Like phone portrait mode, but vectorized.
metadata:
  version: 0.4.0
---

# SVG Portrait Mode

Layered vectorization with selective detail. Uses MediaPipe for segmentation
and the image-to-svg pipeline for per-layer processing.

## Quick Start

```python
from portrait_mode import portrait_mode

svg, stats = portrait_mode("photo.jpg")
# stats: {'image_type': 'painting', 'background': 6, 'body': 749, 'face': 1205, 'total': 1960}
```

## How It Works

1. **Image Type Detection** → auto-classify as photo/painting/illustration/graphic
2. **MediaPipe Segmentation** → person/face/background masks
3. **Per-layer processing** using image-to-svg pipeline:
   - Background: K=6, oilpaint:24-28, **downscaled to ~20%** → big flat blobs
   - Body: K=48, oilpaint:8 (medium detail)
   - Face: K=80-96, no smoothing (maximum fidelity)
4. **SVG Compositing** → background as full base layer, body/face paths on top

The key trick: processing the background from a tiny image (e.g. 97×144px)
means K-means produces very few, very large clusters. When rendered at full
SVG width, these become large flat colored blobs — the "portrait mode" effect.

## Requirements

MediaPipe models in `/home/claude/`:
- `selfie_segmenter.tflite`
- `blaze_face_short_range.tflite`

Cross-skill dependency:
- `image-to-svg` pipeline at `/mnt/skills/user/image-to-svg/`

API key for image type detection:
- `API_KEY` env var or `/mnt/project/claude.env`

## Custom Settings

```python
svg, stats = portrait_mode("photo.jpg",
    image_type="photo",       # Skip auto-detection
    face_K=128,               # More face detail
    body_K=64,                # More body detail
    background_K=4,           # Even fewer bg blobs
    background_scale=0.15,    # Even smaller → even blobbier
    background_smooth="oilpaint:32",
    svg_width=1200
)
```

## Per-Type Defaults

| Type | Face K | Body K | BG K | BG Scale | BG Smooth |
|------|--------|--------|------|----------|-----------|
| photo | 96 | 48 | 6 | 0.20 | oilpaint:24 |
| painting | 80 | 48 | 6 | 0.18 | oilpaint:28 |
| illustration | 64 | 32 | 6 | 0.22 | oilpaint:20 |
| graphic | 48 | 24 | 8 | 0.25 | None |

## Architecture

```
image.jpg
    ↓
detect_image_type() → photo/painting/illustration/graphic
    ↓
MediaPipe Segmentation → person mask, face bbox, background
    ↓
┌──────────────────────────────────────────────────┐
│ Background (full img) Body (masked)  Face (masked)│
│ scale=0.18            K=48           K=80         │
│ K=6, oilpaint:28     oilpaint:8     no smooth     │
│ → 6 paths            → 749 paths    → 1205 paths  │
└──────────────────────────────────────────────────┘
    ↓                    ↓               ↓
image-to-svg          image-to-svg     image-to-svg
    ↓                    ↓               ↓
┌── Composite: bg(rect+paths) + body(paths) + face(paths) ──┐
    ↓
portrait.svg
```

## Changelog

### 0.4.0
- Auto image type detection via Anthropic API (photo/painting/illustration/graphic)
- Background downscaling: ~20% resolution → naturally large blobby SVG paths
- Full-image base layer (no mask) eliminates seam gaps
- Per-type layer defaults for K, smoothing, mode, and scale
- Foreground layers: paths-only compositing (skip pipeline bg rects)

### 0.3.0
- Complete rewrite using image-to-svg pipeline
- ImageMagick preprocessing (oilpaint, kuwahara) per layer
- Proper contour extraction with stroke=fill gap coverage
- Fixed: faces no longer become featureless blobs

### 0.2.0
- Added MediaPipe integration (broken implementation)

### 0.1.0
- Initial release (manual K-means, unusable)
