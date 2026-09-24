---
name: drawing-with-pycairo
description: "Draws images, PDF/SVG vector files and animation frames with pycairo, and supplies what cairo lacks: shaped text for Arabic, Indic and other scripts, text along curves, blur/glow/drop shadows, path booleans, stroke-to-outline, and Gouraud-shaded 3D. Use when writing pycairo or cairo drawing code, generative art, custom diagrams or posters rendered in Python, or when cairo output needs non-Latin text, soft effects, merged shapes or shaded surfaces."
metadata:
  version: 0.1.0
---

# Drawing with pycairo

Cairo paints paths with solid colours, gradients, mesh gradients and images, and composites them with 20-odd operators. It writes PNG, PDF, SVG and PostScript. It does **not** shape text, filter pixels, combine paths, outline strokes, or do depth. `scripts/cairokit.py` fills each gap; `scripts/selftest.py` exercises all of it. Both were verified on pycairo 1.29.1 / cairo 1.18.0 / Python 3.11.

## Setup

```bash
pip install --break-system-packages pycairo numpy uharfbuzz fonttools skia-pathops
python3 /mnt/skills/user/drawing-with-pycairo/scripts/selftest.py /tmp/cairo-selftest
```

The self-test prints the cairo version, whether Pango is usable, per-panel timings, and the path of a 2×2 contact sheet. `Read` that sheet: panel A shows joined Arabic in green next to broken toy-API Arabic in red, B shows four boolean results and an outlined wave, C shows glow and a soft shadow, D shows a smooth-shaded torus. Then:

```python
import sys; sys.path.insert(0, "/mnt/skills/user/drawing-with-pycairo/scripts")
from cairokit import *
```

In the environment where this was built, pycairo was not preinstalled. Pango was also absent: the system PyGObject was compiled for Python 3.12 while `python3` was 3.11, and there were no Pango typelibs. `pango()` reports which case you are in.

## Render, then look

Every render ends with a `Read` of the PNG before the next edit or before reporting. Exit codes and timings don't show visual bugs. In the session that produced this skill, looking caught five defects that ran without error:
- a painter sort drawn near-to-far
- inward normals combined with a light pointing away from the camera, which left a black knot
- a scene scaled in absolute pixels, cropped once the frame size changed
- glyphs crowding on a squashed spiral, because arc length was measured on the unsquashed curve
- a stray hook where a polyline's first `move_to` wasn't its first sample

For several outputs, `contact_sheet()` tiles them so one `Read` covers all of them. For animation, extract two or three frames with `ffmpeg -ss T -i out.mp4 -frames:v 1 f.png` and read those.

## What cairokit provides

| need | call |
|---|---|
| surface + context with background | `new_image(w, h, bg)` |
| ASCII caption on a box | `label(c, text, x, y)` |
| pixels as numpy (BGRA, premultiplied, live view) | `pixels(s)`, `from_array(a)`, `from_rgb_float(rgb)` |
| blur, drop shadow, neon glow | `gauss_blur(a, sigma)`, `blurred(s, sigma)`, `glow(sharp)` |
| shaped text for any script, as outlines | `Shaper(font_path).text_path(c, text, x, y, size)` |
| text along a curve | `Shaper.text_on_curve(c, text, polyline_walker(points), size)` |
| union / intersection / difference / xor | `boolean(c, build_a, build_b, op)` |
| outline of a stroke | `stroke_to_path(c, width, cap, join)` |
| perspective, depth sort, smooth shading | `project(P)`, `painter_order(z)`, `gouraud_mesh(quads, colors, order)` |
| frames to MP4, many PNGs to one sheet | `frames_to_mp4(pattern, out)`, `contact_sheet(files, out)` |
| Pango availability | `pango()` → `(Pango, PangoCairo)` or `None` |

Find a font for a script with `fc-match -f '%{file}' 'DejaVu Sans:lang=ar'` (or `fc-list :lang=hi family file`). DejaVu Sans covers Arabic and Hebrew; FreeSans covers Devanagari.

## Measured behaviour (800×600 unless noted)

| thing | result |
|---|---|
| alpha circles, antialiased | ~58k/s (no-AA: ~139k/s) |
| one 200k-segment polyline stroke | ~1.0 s |
| ImageSurface max side | 32767; 32768 raises `cairo.Error` |
| `glow()`, two blur radii | ~240 ms |
| 10k quads, flat fill_preserve+stroke | ~160 ms |
| 10k quads, one `gouraud_mesh()` | ~125 ms (faster, and smooth) |
| animation frame, 10k-quad mesh at 640×480 | ~130 ms |
| mesh gradient → PDF | kept as vector (ShadingType 6/7) |
| mesh gradient → SVG | rasterised to an embedded `<image>` (SVG has no mesh gradient) |
| 10k flat quads → SVG vs PDF | 3.5 MB vs 0.36 MB |

Cairo renders on one CPU core. For large batches or long animations, spread frames across processes with `multiprocessing` rather than threads.

## Behaviour that trips people

**Text.** `show_text()` / `text_path()` map codepoints to glyphs one by one, left to right, with no joining, reordering, ligatures or kerning. They are fine for ASCII labels. For anything else, use Pango if `pango()` returns modules, otherwise `Shaper`. `Shaper` does no line wrapping, no bidi across mixed-direction runs, and no font fallback: one font per call, and you split runs yourself.

**Paths and the CTM.** Path coordinates are transformed when they are appended, and the path is not part of the saved state. `save(); scale(); <append>; restore(); fill()` fills the transformed shape without distorting anything later. Line width, however, is transformed at `stroke()` time. Stroking inside a non-uniform `scale()` gives calligraphic, uneven lines, so restore first.

**Pixels.** `ARGB32` memory is B,G,R,A per pixel, alpha-premultiplied, with rows `get_stride()` bytes apart. Call `flush()` before reading and `mark_dirty()` after writing. `pixels()` and `from_array()` handle this. Blurring premultiplied data is correct; un-premultiplying first gives dark fringes.

**Seams.** Two antialiased fills sharing an edge leave a faint line of background between them (conflation). Fixes: `fill_preserve()` plus a 0.5–0.7 px stroke in the same colour, or a single `MeshPattern` for the whole surface.

**MeshPattern.** Neighbouring Coons patches must use the *identical* curve for their shared edge. Generate each edge's control points in a canonical direction and reverse them for the other patch, or seams appear. Patches paint in insertion order, which is what makes `gouraud_mesh()` a painter's-algorithm renderer.

**3D.** There is no depth buffer. Sorting by mean depth fails when polygons interpenetrate or are long and thin across depth; subdividing helps. Use two-sided normals (flip toward the camera) unless the mesh orientation is known. Screen y points down, so a light "from the top left, toward the camera" is `(-x, -y, -z)` with camera-space +z pointing away.

**skia-pathops.** Round caps and joins produce conic segments, and `simplify()` rejects them; `stroke_to_path()` converts them to quadratics first. Any other pathops output passed to `append_pathops()` needs `convertConicsToQuads()` too.

**Output.** `SVGSurface` / `PDFSurface` must be `finish()`ed, or the file is truncated. `RecordingSurface` records once and replays at any scale or to any backend. Operators such as `ADD`, `SCREEN`, `MULTIPLY` and `DIFFERENCE` are on the context (`set_operator`). Float formats `FORMAT_RGB96F` / `FORMAT_RGBA128F` exist from cairo 1.18 for HDR-ish accumulation.

## Route elsewhere

| task | use |
|---|---|
| data charts | `charting` (matplotlib/seaborn) |
| photo edits, resizing, format conversion | `processing-images` |
| raster image to SVG | `image-to-svg` |
| illustrations or portraits from a prompt | `invoking-gemini` |
| real 3D (occlusion, textures, >50k polygons) | a rasteriser or ray tracer; cairo's painter approach stops being practical |
| polygon analysis (areas, buffers, spatial predicates) | shapely; use skia-pathops when the result goes back into cairo as curves |
