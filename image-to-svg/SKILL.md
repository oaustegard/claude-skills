---
name: image-to-svg
version: 1.4.0
description: Convert raster images (photos, paintings, illustrations) into SVG vector reproductions. Use when the user uploads an image and asks to reproduce, vectorize, trace, or convert it to SVG. Also use when asked to decompose an image into shapes, create an SVG version of a picture, or faithfully reproduce artwork as vector graphics. Do NOT use for creating original SVG illustrations from text descriptions — only for converting existing raster images.
---
 
# Image to SVG Reproduction
 
Convert raster images into faithful SVG reproductions using data-driven color quantization and contour extraction. **Never hand-draw shapes from visual interpretation** — always extract geometry from the actual pixel data.

## Core Principle

**Trust the data, not your imagination.** Claude's visual interpretation of images is unreliable for precise color matching, shape positioning, and spatial relationships. Every shape, color, and position must come from computational analysis of the source pixels.

## Quick Start

```bash
pip install opencv-python-headless scikit-image scipy --break-system-packages -q
apt-get install -y librsvg2-bin -qq
```

```python
import sys
sys.path.insert(0, '/mnt/skills/user/image-to-svg/scripts')
from pipeline import image_to_svg

svg, flow = image_to_svg("source.jpg", mode="painting")

with open("output.svg", "w") as f:
    f.write(svg)

flow.summary()  # timing + status per step
```

## Mode Selection

**Look at the image** and ask: "Does this have smooth gradients or hard edges?" Gradients → higher K. Hard edges → lower K.

| Mode | K | Best for | Dark shape gating |
|------|---|----------|-------------------|
| `"graphic"` | 28 | Logos, icons, Kandinsky, flat design | Loose (keeps thin lines) |
| `"illustration"` | 40 | Comics, editorial, digital art | Moderate |
| `"painting"` | 56 | Renaissance, Impressionist, watercolor | Standard |
| `"photo"` | 64 | Portraits, landscapes, still life | Standard (prevents woodcut artifacts) |

Default is `"painting"`. When uncertain, start there.

**Tradeoffs**: K=64 produces ~2300 shapes (~1.2MB SVG) vs K=28's ~1000 shapes (~550KB). Processing time roughly doubles with K. The quality gain in tonal gradation is substantial for photos but wasted on graphic art.

## Pipeline Architecture

Uses the [flowing](/mnt/skills/user/flowing/SKILL.md) DAG runner. Steps with independent inputs run in parallel:

```
preprocess → quantize → ┬─ detect_background ─┬─ extract_contours → assemble_svg
                        └─ edge_map           ─┘
```

Steps:
1. **preprocess** — Bilateral + Gaussian blur (edge-preserving texture removal)
2. **quantize** — K-means color quantization at chosen K
3. **detect_background** — Identifies background clusters by edge contact (parallel with edge_map)
4. **edge_map** — Structural edges via [seeing-images](/mnt/skills/user/seeing-images/SKILL.md) (parallel with detect_background)
5. **extract_contours** — Per-cluster contour extraction with dark territory awareness and woodcut prevention
6. **assemble_svg** — Z-ordered painter's algorithm assembly

### Resume on failure

```python
svg, flow = image_to_svg("source.jpg", mode="photo")
# If extract_contours failed:
flow.override(extract_contours, corrected_shapes)
flow.resume()  # quantize, detect_background, edge_map stay cached
```

## Verification Protocol

**After EVERY run, render and visually compare side-by-side.** This is non-negotiable.

```python
import subprocess
from PIL import Image

subprocess.run(['rsvg-convert', '-w', '1400', 'output.svg', '-o', 'output.png'])

orig = Image.open('source.jpg')
rendered = Image.open('output.png')
target_h = 800
orig_r = orig.resize((int(orig.width * target_h / orig.height), target_h))
rend_r = rendered.resize((int(rendered.width * target_h / rendered.height), target_h))
gap = 20
comp = Image.new('RGB', (orig_r.width + rend_r.width + gap, target_h), (255,255,255))
comp.paste(orig_r, (0, 0))
comp.paste(rend_r, (orig_r.width + gap, 0))
comp.save('comparison.png')
# LOOK AT comparison.png BEFORE claiming success
```

## Manual Post-Processing

### Handling Subtle Color Differences

When two regions have similar luminance but different hue/saturation, K-means in RGB space merges them. Use **HSV multispectral analysis**:

```python
hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
h_ch, s_ch, v_ch = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]

# Separate gray (low saturation) from red (high saturation) at similar brightness
red_mask = ((h_ch < 12) | (h_ch > 168)) & (s_ch > 120) & (v_ch > 80)
gray_mask = (s_ch < 80) & (v_ch > 40) & (v_ch < 120) & spatial_constraint
```

**Saturation is the key discriminator** for colors that look similar in grayscale but are visually distinct.

### Positioning Overlays

When adding shapes not captured by quantization, **derive coordinates from the SVG render**, not the source image. The extraction pipeline shifts positions due to contour simplification.

```python
# WRONG: extract from source, insert into SVG (coordinate mismatch)
# RIGHT: render SVG → detect gap in render → create shape in render coords → insert
svg_render = cv2.imread('rendered_svg.png')
```

## Anti-Patterns

1. **Never hand-draw shapes** from visual interpretation. Use CV extraction.
2. **Never claim a fix works without rendering and comparing.** A rendered comparison is the only verification.
3. **Never use geometric primitives** (circles, rectangles) to approximate extracted contours.
4. **Never extract coordinates from the source image and insert into the SVG** without verifying alignment.
5. **Never boost saturation globally.** Do targeted per-color adjustments based on measured ΔE.
6. **Never aggressively merge near-background colors.** Only merge colors <10 RGB distance from background AND heavily touching edges.
7. **Don't use bezier smoothing unless requested.** Simple L polygons produce smaller SVGs.
8. **Don't use a dilation kernel larger than 3×3.** 5×5 causes blotchy artifacts.

## Known Limitations

- **Thin linework**: The dark shape gating that prevents woodcut artifacts in photos can filter deliberate thin lines in graphic art. The `"graphic"` mode loosens this, but very fine crosshatching may still degrade.
- **Ring/arc structures**: Large dark rings (like Kandinsky's outer circle) fragment across multiple K-means clusters. Each cluster's contours are independent, so the ring doesn't form one smooth shape. A dark-cluster-merging step would help.
- **Gradient transitions**: At any K, smooth gradients produce staircase banding. Higher K reduces this but never eliminates it.

## Dependencies

```bash
pip install opencv-python-headless scikit-image scipy --break-system-packages
apt-get install -y librsvg2-bin  # for rsvg-convert
```

**Cross-skill dependencies** (resolved automatically by pipeline.py):
- [flowing](/mnt/skills/user/flowing/SKILL.md) — DAG workflow runner
- [seeing-images](/mnt/skills/user/seeing-images/SKILL.md) — `edges()` function for structural edge detection
