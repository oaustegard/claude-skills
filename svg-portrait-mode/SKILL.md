---
name: svg-portrait-mode
description: "Portrait Mode" for SVGs — sharp detailed subjects, simplified backgrounds. Claude interprets user intent ("focus on the dog, blur the background") and generates depth-aware vectorization. Like phone portrait mode, but the blur is low-K quantization.
metadata:
  version: 0.1.0
---

# SVG Portrait Mode

Selective detail vectorization: detailed subjects, simplified backgrounds. The SVG equivalent of phone portrait mode.

## Concept

| Portrait Mode (Photos) | Portrait Mode (SVGs) |
|------------------------|----------------------|
| Gaussian blur | Low-K quantization |
| Sharp subject | High-K + fine contours |
| Depth map | Treatment map |
| Bokeh | Flat color fields |

## Treatments (Depth Levels)

| Treatment | K | Effect | Use For |
|-----------|---|--------|---------|
| `solid` | 1 | Single color | Distant sky |
| `flat` | 2 | 2-tone | Simple backgrounds |
| `simplified` | 5 | Chunky shapes | Midground |
| `detailed` | 24 | Preserved texture | Subject |
| `textured` | 32 | High fidelity | Focal point |
| `outline` | 1 | Strokes only | Stark edges |

## Quick Start

```python
from portrait_mode import compose_from_json

config = {
    "regions": [
        {"name": "subject", "method": "bbox", 
         "params": {"x1": 0.2, "y1": 0.4, "x2": 0.8, "y2": 0.95}, 
         "treatment": "detailed", "z_order": 10},
        {"name": "background", "method": "remainder", 
         "treatment": "flat", "z_order": 0}
    ]
}

svg, stats = compose_from_json("photo.jpg", config)
```

## Region Methods

| Method | Params | Example |
|--------|--------|---------|
| `position` | `{"y": [start, end]}` | Top 30%: `{"y": [0, 0.3]}` |
| `bbox` | `{"x1", "y1", "x2", "y2"}` | Normalized 0-1 coordinates |
| `color` | `{"hsv_ranges": [...]}` | HSV color matching |
| `saturation` | `{"min", "max"}` | Gray detection: `{"max": 30}` |
| `luminance` | `{"min", "max"}` | Brightness selection |
| `mask_file` | `{"path": "..."}` | External mask image |
| `remainder` | `{}` | Everything unclaimed |

## Workflow

1. User uploads image
2. User describes intent: "focus on X, simplify Y, outline Z"
3. Claude sees image → identifies regions → maps to treatments
4. Claude generates JSON config
5. `compose_from_json()` executes → SVG

## Forced Palettes

Override natural colors (e.g., make gray grass green):

```python
"palettes": {
    "grass": [[85, 130, 60], [110, 155, 80]],
    "sky": [[135, 180, 220]]
}
```

## Style Presets

- **Classic Portrait**: subject detailed, background flat
- **Stage Light**: subject detailed, background solid black  
- **High Key**: subject detailed, background solid white
- **Contour**: all regions outline mode
- **Collage**: foreground textured, midground simplified, background flat
