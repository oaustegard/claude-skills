---
name: compiling-wgsl
description: "Shrinks WGSL shaders and compiles shapes into them. Minifies a WebGPU shader (renaming, dead code, literal and type shortening) and proves the result unchanged with naga, Chrome's Tint and bit-identical compute runs; compiles an SVG file or a Python-built scene of circles, rects, paths, gradients and animated transforms into one resolution-independent WGSL fragment shader. Use for minify this WGSL, shrink my shader, make the shader smaller, compress shader source, WGSL optimizer, turn this SVG into a shader, draw this icon in WebGPU, SDF shapes in WGSL, smooth union shapes, animated vector graphics on the GPU, pretty-print WGSL."
metadata:
  version: 0.1.0
---

# Compiling WGSL

`scripts/forge` is a pure-Python WGSL toolchain (numpy is the only dependency): a parser
that follows the spec's template-list rules, a minifier, and a shape compiler. It came
from `oaustegard/experiments/wgsl-forge`, whose RESULTS.md holds the measurements quoted
here. Set `SKILL=/mnt/skills/user/compiling-wgsl` (or this directory) and run every
command with `PYTHONPATH=$SKILL/scripts`.

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| A raster image (photo, PNG) should become vector shapes | `image-to-svg`, then this skill on its SVG |
| The output is a PNG, PDF or SVG file rather than a shader | `drawing-with-pycairo` |
| Charts or dashboards | `charting`, `charting-vega-lite` |
| GLSL, HLSL or SPIR-V | this skill parses WGSL only |
| A shader whose host reads names back by reflection (a binding library that matches struct member or function names) | run with `--keep name1,name2`, or do not rename |

## Setup

```bash
export SKILL=/mnt/skills/user/compiling-wgsl
pip install --break-system-packages numpy pillow          # pillow only for --png
command -v naga || cargo install naga-cli                  # optional validator, ~3 min
node -e "require('playwright')" && echo playwright-ok      # GPU checks need it
```

The GPU checks run headless Chromium on SwiftShader. On claude.ai and Claude Code on
the web, Playwright's Chromium is already installed. Elsewhere, point `CHROME_PATH` at a
Chromium binary.

## Minify a shader

```bash
PYTHONPATH=$SKILL/scripts python3 -m forge minify in.wgsl -o out.wgsl       # prints bytes before -> after
python3 $SKILL/scripts/verify.py minify in.wgsl                             # always run this
```

`verify.py minify` validates the output with naga and compiles both versions in Tint.
It then runs every compute entry point that binds only buffers on random typed inputs:
the original twice and the minified once. It exits 1 on any failure.

Read the result lines:
- `ok compute main bit-identical`: the minified kernel computes the same bytes.
- `skip ... original disagrees with itself`: the original has a race for this dispatch
  shape. Pass the real shape with `--dispatch 64,1,1`.
- `skip ... textures or samplers bound`: that shader was compiled, not executed. To prove
  a render shader unchanged, render it in its real host before and after and compare
  pixels.

Options:
- `--no-aliases` skips the `alias a=vec4f;` pass. Use it for shaders served gzipped: on
  the 86-shader corpus that pass saves 1.7% raw bytes but adds 0.9% gzip bytes.
- `--keep a,b` protects extra names from renaming and removal.

Entry-point names, `override` names, binding numbers and attributes are never changed.
Struct members spelled like swizzles (`x`, `rgb`) or like builtin result fields (`fract`,
`exp`, `whole`) are never renamed either.

Expect 30–35% of the original bytes on typical shaders (34% on the corpus, against 56%
for LucentFlux wgsl-minifier on the files both handle). Shaders that are already terse
land nearer 50%: Tilt Rally's nine came out at 51%.

`python3 -m forge fmt out.wgsl` pretty-prints minified code for reading.

## Compile an SVG to a shader

```bash
PYTHONPATH=$SKILL/scripts python3 -m forge svg icon.svg --minify -o icon.wgsl
python3 $SKILL/scripts/verify.py svg icon.svg --size 512 --png /tmp/check.png
PYTHONPATH=$SKILL/scripts python3 -m forge html icon.svg --minify -o preview.html   # live page with host code
```

Read every `warning:` line. Skipped elements (`text`, `image`, `clipPath`, `mask`,
`filter`, `pattern`, `marker`) are missing from the shader. `verify.py svg` reports
mean error, PSNR and an ink ratio against Chromium's own SVG rendering. Then `Read` the
PNG: reference | shader | difference ×4.

The shader's interface is fixed:
- `@group(0) @binding(0) var<uniform> u: U` with `struct U { r: vec2f, t: f32 }`, which
  holds the canvas size in pixels and the time in seconds (16-byte buffer:
  `[w, h, t, 0]`).
- Vertex entry `vs`; draw 3 vertices, no vertex buffers.
- Fragment entry `fs`, which returns premultiplied RGBA (`alphaMode: "premultiplied"`).

`forge html` writes a working host page to copy from.

## Build a scene in Python

Use this when the shapes come from code, need animation, or need operations SVG lacks.
`references/scene-api.md` lists the whole API; `references/example_scene.py` is a
complete animated scene.

```python
from forge.scene import Scene, T, sin, radial, smooth_union, Circle
s = Scene(320, 200, background="#101418")
s.circle(160, 100, 40 + 4 * sin(T * 2), fill=radial(160, 100, 50, ["#fff7d6", "#ff8a3d"]))
with s.group(translate=(160, 100), rotate=T * 30):
    s.rect(-2, -80, 4, 20, rx=2, fill="#ffd36e")
s.add(smooth_union(Circle(60, 150, 25), Circle(90, 150, 20), k=12), fill="hotpink")
open("scene.wgsl", "w").write(s.compile(minify=True))
open("frame.svg", "w").write(s.to_svg(t=1.3))     # reference frame for checking
```

Any number can be an expression in `T`. Check an animated scene at a time where its
animated terms are large, not just at t=0: render the shader with `time` set and compare it
with Chromium rendering `to_svg(t)`. `scripts/forge/gpu.py`'s `run_jobs` takes `render`
and `svg` jobs with a `time` field. SDF-only features (`smooth_union`, `subtract`,
`intersect`, `rounded`, `onion`, `soft`) make `to_svg` raise, because SVG cannot express
them. Check those by rendering and reading the image.

## When to abandon it

- **The SVG relies on unsupported features.** If warnings list `text`, `clipPath`,
  `mask` or `filter` and those carry the design, the shader will be wrong. Rasterise
  instead, or convert text to paths first.
- **The shader is too slow.** Every pixel loops over every path segment. A scene with
  thousands of segments (a detailed illustration, a map) is too heavy as one shader:
  draw it as triangles, or bake it to a texture.
- **A shader under 1 KB.** Expect only small gains, so minify only if bytes really matter.

## Failure modes

- **`naga` says `expected array<i32, 2>, but got array<i32, 2>`** → this is naga 30's
  quirk with an alias inside a template argument. The alias pass already avoids it; if
  it appears, rerun with `--no-aliases` and report the input.
- **Tint compiles the minified shader but not the original** → expected when dead-code
  removal drops unused code that Tint rejects; the reachable code is unchanged. Two naga
  test files do this.
- **`compute ... bit-identical` FAILs with a 2-D or 3-D `--dispatch`** → probably a race
  in the original: invocations that share `id.x` write the same element, and two original
  runs happened to agree. Rerun with the host's real dispatch shape before believing it.
  Diagnosed 2026-11-02 on Tilt Rally's `SMOKE_SIM`: 4×4 failed, while 4×1 was identical
  on three seeds.
- **The harness prints `harness failed` or every GPU job errors** → Chromium or WebGPU is
  unavailable. Check `node -e "require('playwright')"`, set `CHROME_PATH`, and keep the
  `--enable-unsafe-webgpu --use-webgpu-adapter=swiftshader` flags that
  `scripts/harness/gpu.mjs` passes.
- **The ink ratio is below 0.97 or above 1.03 at large sizes** → a geometry error, not
  antialiasing: antialiasing error shrinks as size grows, and geometry error does not.
  Compare `verify.py svg --size 128` with `--size 768`.
- **Curves look faceted at extreme zoom** → curves are fitted to 0.02 of the SVG's own
  pixel, which holds to about 50× magnification. Lower it with `--tolerance 0.02`; the
  default is 0.2, of which a tenth goes to the curve fit.

## Verification

- **Minifier:** `verify.py minify` must print no FAIL. A good result passes naga, compiles
  in Tint and gives bit-identical compute buffers. A *bad success* compiles but computes
  something else: a renamed name the host looks up, or a shader with textures that was
  only compiled. For the second case, render it in its host before and after and compare
  pixels.
- **SVG:** `verify.py svg` must print no FAIL, and the PNG must look right. A *bad
  success* is a high PSNR on an SVG whose `warning:` lines show that elements were
  dropped. A missing element still scores well when it is small.

## Diagnosed failures (fixed, kept as signals)

- 2026-11-01, **line segments**: flattening curves to line segments at the SVG's size left
  icons 1.8% too light at 512 px (ink ratio 0.982), and the error never shrank with size.
  The fix was to keep curves as quadratic Béziers with exact distance. The signal was the
  ink ratio at two sizes.
- 2026-11-01, **missing parentheses**: an animated radius compiled without parentheses,
  `- 44+3*sin(..)`. Frames at t=0 and t=4.7 still matched closely, because the animated
  term was near zero there, and t=1.3 diverged visibly. The lesson: test animation at
  large values of its animated terms.
- 2026-11-01, **packed arc flags**: `0 014.907` was misread, and two Simple Icons logos
  failed to parse. No hand-written test packed flags that way.
