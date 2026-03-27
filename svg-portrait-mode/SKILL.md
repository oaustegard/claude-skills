---
name: svg-portrait-mode
description: "Portrait Mode" for SVGs — sharp detailed subjects, simplified backgrounds. Uses MediaPipe segmentation + image-to-svg pipeline for layered processing. Like phone portrait mode, but vectorized.
metadata:
  version: 0.3.0
---

# SVG Portrait Mode

Layered vectorization with selective detail. Uses MediaPipe for segmentation
and the image-to-svg pipeline for per-layer processing.

## Quick Start

```python
from portrait_mode import portrait_mode

svg, stats = portrait_mode("photo.jpg")
# stats: {'background': 639, 'body': 1753, 'face': 6777, 'total': 9169}
```

## How It Works

1. **MediaPipe Segmentation** → person/face/background masks
2. **Per-layer processing** using image-to-svg pipeline:
   - Background: K=16 + oilpaint (flat, simplified)
   - Body: K=48 + kuwahara (medium detail)
   - Face: K=96, no smoothing (maximum fidelity)
3. **SVG Compositing** → layers stacked back-to-front

## Requirements

MediaPipe models in `/home/claude/`:
- `selfie_segmenter.tflite`
- `blaze_face_short_range.tflite`

Cross-skill dependency:
- `image-to-svg` pipeline at `/mnt/skills/user/image-to-svg/`

## Custom Settings

```python
svg, stats = portrait_mode("photo.jpg",
    face_K=128,           # More face detail
    face_smooth=None,     # No smoothing on face
    body_K=64,            # More body detail
    body_smooth="kuwahara:2",
    background_K=8,       # Flatter background
    background_smooth="oilpaint:16",
    svg_width=1200
)
```

## Layer Settings

| Layer | Default K | Default Smooth | Purpose |
|-------|-----------|----------------|---------|
| Background | 16 | oilpaint:12 | Flat, atmospheric |
| Body | 48 | kuwahara:3 | Medium detail |
| Face | 96 | None | Maximum fidelity |

## Architecture

```
image.jpg
    ↓
MediaPipe Segmentation
    ↓
┌─────────────────────────────────────┐
│  Background    Body       Face      │
│  K=16         K=48       K=96       │
│  oilpaint     kuwahara   none       │
└─────────────────────────────────────┘
    ↓            ↓          ↓
image-to-svg  image-to-svg  image-to-svg
    ↓            ↓          ↓
layer_bg.svg  layer_body.svg  layer_face.svg
    ↓            ↓          ↓
└─────────── Composite ───────────────┘
                 ↓
          portrait.svg
```

## Changelog

### 0.3.0
- Complete rewrite using image-to-svg pipeline
- ImageMagick preprocessing (oilpaint, kuwahara) per layer
- Proper contour extraction with stroke=fill gap coverage
- Fixed: faces no longer become featureless blobs

### 0.2.0
- Added MediaPipe integration (broken implementation)

### 0.1.0
- Initial release (manual K-means, unusable)
