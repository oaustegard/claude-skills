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
# auto-detects image type, applies appropriate settings
# stats: {'image_type': 'painting', 'background': 4, 'body': 617, 'face': 1205, 'total': 1826}
```

## How It Works

1. **Image type detection** → Claude API classifies as photo/painting/illustration/graphic
2. **MediaPipe Segmentation** → person/face/background masks
3. **Per-layer processing** using image-to-svg pipeline:
   - Background: K=6-8 + heavy oilpaint + **downscaled to 20-25%** (produces large blobby shapes)
   - Body: K=40-48 + oilpaint/kuwahara (medium detail)
   - Face: K=80-96, no smoothing (maximum fidelity)
4. **SVG Compositing** → layers stacked back-to-front with coordinate scaling

The background downscaling is the key to the "blobby flat" aesthetic: processing a 25%-size
image through image-to-svg at full `svg_width` produces paths 4x larger than normal — large
flat color regions with clear outlines, no fine detail.

## Requirements

MediaPipe models in `/home/claude/`:
- `selfie_segmenter.tflite`
- `blaze_face_short_range.tflite`

Cross-skill dependency:
- `image-to-svg` pipeline at `/mnt/skills/user/image-to-svg/`

API key for image type detection:
- `ANTHROPIC_API_KEY` or `API_KEY` env var (falls back to `painting` if unavailable)

## Custom Settings

```python
svg, stats = portrait_mode("photo.jpg",
    image_type="painting",    # Override auto-detection
    face_K=96,                # More face detail
    face_smooth=None,         # No smoothing on face
    body_K=48,                # More body detail
    body_smooth="kuwahara:3",
    background_K=6,           # Fewer background colors
    background_smooth="oilpaint:24",
    background_scale=0.20,    # Smaller = more blobby (0.1-0.5 range)
    svg_width=1200
)
```

## Layer Defaults by Image Type

| Type | bg K | bg scale | body K | face K |
|------|------|----------|--------|--------|
| photo | 8 | 0.25 | 48 | 96 |
| painting | 6 | 0.20 | 40 | 80 |
| illustration | 6 | 0.25 | 32 | 64 |
| graphic | 6 | 0.30 | 24 | 48 |

## Architecture

```
image.jpg
    ↓
detect_image_type() → photo/painting/illustration/graphic
    ↓
MediaPipe Segmentation
    ↓
┌──────────────────────────────────────────────┐
│  Background (×0.2)   Body        Face        │
│  K=6                 K=40        K=80        │
│  oilpaint:24         oilpaint:8  none        │
│  107×160px →         539×800px   539×800px   │
│  paths scale 5×      paths 1×    paths 1×    │
└──────────────────────────────────────────────┘
    ↓                    ↓          ↓
image-to-svg         image-to-svg  image-to-svg
(4 paths)            (617 paths)   (1205 paths)
    ↓                    ↓          ↓
  <g transform=       <g id=      <g id=
   "scale(sx,sy)">    "body">     "face">
    ↓
└──────────────── Composite ─────────────────┘
                     ↓
              portrait.svg
```

## Changelog

### 0.4.0
- Auto image type detection via Claude Haiku API (photo/painting/illustration/graphic)
- Per-type layer defaults (LAYER_DEFAULTS dict)
- Background downscaling (`background_scale` param, default 0.20-0.25 by type)
  → dramatically reduces background path count (e.g. 4 paths vs hundreds)
  → produces large blobby flat shapes with clear outlines
- Coordinate-correct compositing: background wrapped in `<g transform="scale(sx,sy)">`
  to handle different viewBox from downscaled processing

### 0.3.0
- Complete rewrite using image-to-svg pipeline
- ImageMagick preprocessing (oilpaint, kuwahara) per layer
- Proper contour extraction with stroke=fill gap coverage
- Fixed: faces no longer become featureless blobs

### 0.2.0
- Added MediaPipe integration (broken implementation)

### 0.1.0
- Initial release (manual K-means, unusable)
