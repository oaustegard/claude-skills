---
name: image-to-svg
version: 1.6.0
description: Convert raster images (photos, paintings, illustrations) into SVG vector reproductions. Use when the user uploads an image and asks to reproduce, vectorize, trace, or convert it to SVG. Also use when asked to decompose an image into shapes, create an SVG version of a picture, or faithfully reproduce artwork as vector graphics. Do NOT use for creating original SVG illustrations from text descriptions — only for converting existing raster images.
---
 
# Image to SVG Reproduction
 
Convert raster images into faithful SVG reproductions using data-driven color quantization and contour extraction. **Never hand-draw shapes from visual interpretation** — always extract geometry from the actual pixel data.

## Core Principle

**Trust the data, not your imagination.** Claude's visual interpretation of images is unreliable for precise color matching, shape positioning, and spatial relationships. Every shape, color, and position must come from computational analysis of the source pixels.

## Quick Start

```bash
pip install opencv-python-headless scikit-image scipy scikit-learn --break-system-packages -q
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

All mode defaults (K, dark_lum, compactness_min, etc.) can be overridden via `**kwargs`:
```python
svg, flow = image_to_svg("source.jpg", mode="graphic", K=12, min_area=20)
```

## Palette Remapping (Warhol Effects)

Separate structure from color: K-means finds regions, palette remapping assigns bold colors. This produces screen-print / pop art effects.

```python
# Named preset
svg, flow = image_to_svg("photo.jpg", mode="graphic", K=4, palette="pop")

# Custom hex list (darkest → lightest mapping order)
svg, flow = image_to_svg("photo.jpg", mode="graphic", K=8,
    palette=["#000", "#dc143c", "#ff69b4", "#ffd700", "#32cd32", "#00bfff", "#ff8c00", "#f5f5f5"])

# Override background separately
svg, flow = image_to_svg("photo.jpg", mode="graphic", K=4, palette="ocean", bg_color="#000000")
```

**Built-in presets**: `bw`, `mono3`, `mono4`, `pop`, `pop2`, `neon`, `warhol4`, `warhol6`, `warhol8`, `sunset`, `ocean`

**How it works**: Unique shape colors are sorted by luminance. Palette entries are mapped proportionally — `palette[0]` replaces the darkest cluster, `palette[-1]` replaces the lightest. Background defaults to the lightest palette entry unless `bg_color` is set. Palette length doesn't need to match K exactly; colors are binned proportionally.

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
4. **edge_map** — Sobel edge detection via `cv2.Sobel` (parallel with detect_background)
5. **extract_contours** — Per-cluster contour extraction with dark territory awareness and woodcut prevention (d=1 dilation; stroke handles gaps)
6. **assemble_svg** — Z-ordered painter's algorithm assembly with stroke=fill gap coverage

### Resume on failure

```python
svg, flow = image_to_svg("source.jpg", mode="photo")
# If extract_contours failed:
flow.override(extract_contours, corrected_shapes)
flow.resume()  # quantize, detect_background, edge_map stay cached
```


## Batch API

Generate multiple variants from one image, sharing computation across runs with the same K:

```python
from pipeline import image_to_svg_batch

results = image_to_svg_batch("photo.jpg", [
    {"name": "photo",   "mode": "photo"},
    {"name": "warhol",  "mode": "graphic", "K": 12, "palette": "warhol4"},
    {"name": "neon",    "mode": "graphic", "K": 12, "palette": "neon"},
    {"name": "sunset",  "mode": "graphic", "K": 12, "palette": "sunset"},
    {"name": "bw",      "mode": "graphic", "K": 16, "palette": "bw"},
], svg_width=1400)

for name, svg in results.items():
    with open(f"{name}.svg", "w") as f:
        f.write(svg)
```

Variants sharing the same K run the pipeline (preprocess → quantize → edge_map → extract_contours) **once**, then fan out at assembly for palette remapping. This guarantees structural identity across palette variants (same shapes, same paths) and saves ~20-60s per shared K group.

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

## Gap Coverage: stroke=fill

Every `<path>` element gets `stroke="{fill}" stroke-width="4" stroke-linejoin="round"`. This bleeds each shape outward by 2px with its own fill color, covering inter-cluster gaps with the locally correct color.

**Why stroke beats dilation for gaps**: Dilation operates on binary masks *before* contour simplification — it blurs detail. Stroke operates on final polygons *after* `approxPolyDP` — it catches all gaps including those introduced by simplification. Pure vector, no file size penalty beyond attribute bytes (~12%).

**Background fallback**: When `detect_background` finds no clusters, the bg rect uses `#000000` (black) instead of white. Black reads as shadow; white reads as absence.

**Dilation** is reduced to `iterations=1` — just enough for morphological noise cleanup. Gap coverage is fully handled by stroke.

## Anti-Patterns

1. **Never hand-draw shapes** from visual interpretation. Use CV extraction.
2. **Never claim a fix works without rendering and comparing.** A rendered comparison is the only verification.
3. **Never use geometric primitives** (circles, rectangles) to approximate extracted contours.
4. **Never extract coordinates from the source image and insert into the SVG** without verifying alignment.
5. **Never boost saturation globally.** Do targeted per-color adjustments based on measured ΔE.
6. **Never aggressively merge near-background colors.** Only merge colors <10 RGB distance from background AND heavily touching edges.
7. **Don't use bezier smoothing unless requested.** Simple L polygons produce smaller SVGs.
8. **Don't use a dilation kernel larger than 3×3.** Use `iterations=1` on a 3×3 kernel — stroke=fill handles gap coverage in vector space, so dilation only needs to close noise holes.

## Known Limitations

- **Thin linework**: The dark shape gating that prevents woodcut artifacts in photos can filter deliberate thin lines in graphic art. The `"graphic"` mode loosens this, but very fine crosshatching may still degrade.
- **Ring/arc structures**: Large dark rings (like Kandinsky's outer circle) fragment across multiple K-means clusters. Each cluster's contours are independent, so the ring doesn't form one smooth shape. A dark-cluster-merging step would help.
- **Gradient transitions**: At any K, smooth gradients produce staircase banding. Higher K reduces this but never eliminates it.

## Dependencies

```bash
pip install opencv-python-headless scikit-image scipy scikit-learn --break-system-packages
apt-get install -y librsvg2-bin  # for rsvg-convert
```

**Compiled acceleration**: `nn_assign.c` is auto-compiled on first use if `gcc` is available (27x faster label assignment). Falls back to numpy if unavailable.

**Cross-skill dependencies** (resolved automatically by pipeline.py):
- [flowing](/mnt/skills/user/flowing/SKILL.md) — DAG workflow runner
