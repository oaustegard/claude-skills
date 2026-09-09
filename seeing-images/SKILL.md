---
name: seeing-images
description: Augmented vision tools for analyzing images beyond native visual capabilities. Use when tasked with describing images in detail, reproducing images as SVGs, identifying subtle features, comparing image regions, reading degraded text, or any task requiring careful visual inspection. Also use when the image-to-svg skill needs ground truth about colors, shapes, or boundaries.
metadata:
  version: 1.0.1
---

# Seeing Images

Compensatory vision tools based on blindspots measured by vision diagnostic
v1-v4 on 2026-03-25. Which model it ran on is not recorded here and it has not
been re-run since, so read the thresholds as measured-then: they say a tool
exists for each failure, not that the current model fails at exactly that
number. Re-run the diagnostic before relying on a specific threshold.

## When to Use

Activate this skill when:
- Describing an uploaded image in detail
- Reproducing an image as SVG (use BEFORE drawing to establish ground truth)
- Comparing two images or regions for differences
- Reading text in degraded/compressed/low-contrast images
- Identifying subtle features (gradients, faint overlays, reflections)
- Any image task where accuracy matters more than speed

## Known Blindspots (from diagnostics)

Measured, not guessed:

| Blindspot | Threshold | Compensatory Tool |
|-----------|-----------|-------------------|
| Luminance contrast | ~15-20 RGB steps invisible | `enhance`, `histogram`, `sample` |
| Gradients | <30-step range invisible | `gradient_map`, `enhance` |
| Context color bias | Dress effect, simultaneous contrast | `isolate`, `sample` |
| Small elements | <15px effectively invisible | `crop`, `grid` |
| Dense counting | Degrades >15 items, ~50% error at 30 | `count_elements` |
| Subtle atmospherics | Steam, faint reflections lost in noise | `enhance`, `denoise` |

## Workflow

### Setup (one line, every time)
```python
import sys; sys.path.insert(0, '/mnt/skills/user/seeing-images/scripts')
from see import grid, sample, enhance, edges, histogram, isolate, palette, compare, count_elements, gradient_map, denoise, crop
```

### Quick Analysis (2-3 tool calls)
```python
grid(path, rows=2, cols=2)   # → view the output
sample(path, [(x1,y1), ...]) # → verify colors at points of interest
```

### Deep Analysis (for SVG reproduction, spot-the-difference, etc.)
```python
grid(path, rows=3, cols=3)                    # 1. Overview
palette(path, n=10)                           # 2. Dominant colors
edges(path, threshold=30)                     # 3. Shape boundaries
sample(path, [(x1,y1), (x2,y2), ...])        # 4. Exact RGB at points
enhance(path, region=(x,y,w,h), mode='auto')  # 5. Reveal low-contrast areas
isolate(path, region=(x,y,w,h))              # 6. Remove context bias
```

## Tool Reference

All functions in `scripts/see.py`. Every function that produces an image saves to `/home/claude/see_*.png` and returns the path. Use `view` tool on the returned path.

### grid(path, rows=3, cols=3, labels=True)
Splits image into labeled cells for systematic inspection. Call it first: it reduces attentional competition.

### sample(path, points, radius=3)
Returns exact RGB values at specified pixel coordinates. Use to verify what you think you see. Averages over a small radius to handle noise.

### histogram(path, region=None)
Color histogram showing value distribution. Reveals bimodal distributions (hidden gradients), dominant colors, and contrast range. With region=(x,y,w,h), analyzes only that area.

### enhance(path, region=None, factor=2.0, mode='contrast')
Boosts contrast in the image or a region. Modes: 'contrast', 'brightness', 'color', 'sharpness'. Use factor=3-5 for near-threshold features.

### edges(path, threshold=50)
Sobel edge detection revealing shape boundaries invisible at low contrast. Lower threshold = more edges (noisier). Output is a white-on-black edge map.

### gradient_map(path, region=None)
Computes local gradient magnitude across the image. Bright = high gradient, dark = flat. Reveals gradients below the 30-step detection threshold.

### isolate(path, region, padding=20, bg=(128,128,128))
Extracts a region and places it on a neutral gray background. Removes surrounding context that causes simultaneous contrast and Dress-type illusions. The `bg` parameter defaults to mid-gray to minimize context bias.

### compare(path, r1, r2)
Side-by-side comparison of two regions with diff overlay. Highlights pixel-level differences with amplification. Use for spot-the-difference tasks.

### count_elements(path, region=None, color_range=None, min_size=3)
Programmatic element counting using connected component analysis. Specify approximate color_range as ((r_min,g_min,b_min), (r_max,g_max,b_max)) to count specific colored elements.

### denoise(path, region=None, strength=3)
Median filter to reduce photographic noise, revealing subtle features hidden in the noise floor (like steam, faint reflections).

### palette(path, n=8)
Extracts the n most dominant colors using k-means clustering. Returns RGB values and their proportions. Essential for SVG reproduction.

## Accuracy Notes

Call `grid()` first on a complex image. Verify colors near context boundaries
with `sample()` or `isolate()`, counts above 15 with `count_elements()`,
gradients with `gradient_map()`, and faint features with `enhance()` before
describing them. Each of these is a row of the blindspot table, so the tool
call is the evidence — perception alone is not.
