---
name: svg-portrait-mode
description: "Portrait Mode" for SVGs — sharp detailed subjects, simplified backgrounds. Uses MediaPipe for automatic person/face segmentation, or manual region definition. Claude interprets user intent and generates the config.
metadata:
  version: 0.2.0
---

# SVG Portrait Mode

Selective detail vectorization using ML segmentation. The SVG equivalent of phone portrait mode.

## Quick Start (Automatic)

```python
from portrait_mode import portrait_mode_auto

# One line - MediaPipe handles segmentation
svg, stats = portrait_mode_auto("photo.jpg")

# With custom treatments
svg, stats = portrait_mode_auto("photo.jpg",
    subject_treatment="detailed",
    face_treatment="textured", 
    background_treatment="flat")
```

## Requirements

MediaPipe models in `/home/claude/`:
- `selfie_segmenter.tflite` (person/background)
- `blaze_face_short_range.tflite` (face detection)

## Treatments

| Treatment | K | Use For |
|-----------|---|---------|
| `solid` | 1 | Flat sky |
| `flat` | 2 | Simple backgrounds |
| `simplified` | 5 | Midground |
| `detailed` | 24 | Subject body |
| `textured` | 32 | Face, focal point |
| `outline` | 1 | Stark edges |

## Manual Config (Advanced)

```python
from portrait_mode import compose_from_json, get_mediapipe_masks

# Get masks
masks = get_mediapipe_masks("photo.jpg")
# Returns: {'person': 'path', 'background': 'path', 'face': 'path'}

# Custom config
config = {
    "regions": [
        {"name": "bg", "method": "mask_file", "params": {"path": masks['background']},
         "treatment": "flat", "z_order": 0},
        {"name": "person", "method": "mask_file", "params": {"path": masks['person']},
         "treatment": "detailed", "z_order": 5},
    ]
}

svg, stats = compose_from_json("photo.jpg", config)
```

## Region Methods

| Method | Use Case |
|--------|----------|
| `mask_file` | MediaPipe output, external masks |
| `position` | Spatial: `{"y": [0, 0.3]}` |
| `bbox` | Bounding box (shows edges - avoid) |
| `color` | HSV matching |
| `saturation` | Gray detection |
| `remainder` | Everything unclaimed |

## Forced Palettes

```python
"palettes": {
    "grass": [[85, 130, 60], [110, 155, 80]]
}
```

## Changelog

### 0.2.0
- Added MediaPipe integration
- `portrait_mode_auto()` for one-line usage
- `get_mediapipe_masks()` helper

### 0.1.0
- Initial release
- Manual region definition
