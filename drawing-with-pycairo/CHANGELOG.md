# drawing-with-pycairo - Changelog

## 0.1.0 — 2026-09-24
- New skill. `scripts/cairokit.py`: HarfBuzz-shaped text as glyph outlines (and along curves), numpy pixel bridge with blur/glow/shadow, skia-pathops booleans and stroke-to-path, painter-ordered Gouraud shading via one MeshPattern, MP4 and contact-sheet output, Pango probe. `scripts/selftest.py` exercises all of it. SKILL.md carries measured throughput, backend behaviour (mesh gradients stay vector in PDF, rasterise in SVG) and the render-then-look loop.
