---
name: compiling-wgsl
description: "Produces and shrinks WGSL shaders. Converts GLSL (WebGL 1 and 2, Shadertoy mainImage code, Vulkan GLSL 450, compute shaders) to WGSL and checks the port pixel by pixel against WebGL; minifies a WebGPU shader (renaming, dead code, literal and type shortening) and proves the result unchanged with naga, Chrome's Tint and bit-identical compute runs; compiles an SVG file or a Python-built scene of circles, rects, paths, gradients and animated transforms into one resolution-independent WGSL fragment shader. Use for convert GLSL to WGSL, port this Shadertoy to WebGPU, WebGL shader to WebGPU, minify this WGSL, shrink my shader, make the shader smaller, WGSL optimizer, turn this SVG into a shader, draw this icon in WebGPU, SDF shapes in WGSL, smooth union shapes, animated vector graphics on the GPU, pretty-print WGSL."
metadata:
  version: 0.2.0
---

# Compiling WGSL

`scripts/forge` is a pure-Python WGSL toolchain (numpy is the only dependency): a parser
that follows the spec's template-list rules, a minifier, a shape compiler, and a GLSL
front end that rewrites WebGL and Shadertoy GLSL for naga (and glslang) to translate. It came
from `oaustegard/experiments/wgsl-forge`, whose RESULTS.md holds the measurements quoted
here. Set `SKILL=/mnt/skills/user/compiling-wgsl` (or this directory) and run every
command with `PYTHONPATH=$SKILL/scripts`.

## When NOT to use this skill

| Situation | Use instead |
|---|---|
| A raster image (photo, PNG) should become vector shapes | `image-to-svg`, then this skill on its SVG |
| The output is a PNG, PDF or SVG file rather than a shader | `drawing-with-pycairo` |
| Charts or dashboards | `charting`, `charting-vega-lite` |
| HLSL or Metal | not covered; naga reads SPIR-V (`naga in.spv out.wgsl`), so HLSL can go through DXC to SPIR-V first |
| GLSL for desktop OpenGL with `#version 330` or older, or code using `iChannel` buffers (multi-pass Shadertoy) | converts, but the multi-pass plumbing (render targets, feedback) is host code you write |
| A shader whose host reads names back by reflection (a binding library that matches struct member or function names) | run with `--keep name1,name2`, or do not rename |

## Setup

```bash
export SKILL=/mnt/skills/user/compiling-wgsl
pip install --break-system-packages numpy pillow          # pillow only for --png
command -v naga || cargo install naga-cli                  # validator; required for GLSL, ~3 min
command -v glslangValidator || apt-get install -y glslang-tools   # GLSL fallback route
node -e "require('playwright')" && echo playwright-ok      # GPU checks need it
python3 $SKILL/scripts/selftest.py                         # ~20 s: every route on bundled fixtures
```

`selftest.py` prints `missing tools:` first if naga, glslang or node is absent. Every
other line must read `ok`.

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

## Convert GLSL to WGSL

```bash
PYTHONPATH=$SKILL/scripts python3 -m forge glsl shader.frag -o shader.wgsl [--minify]
python3 $SKILL/scripts/verify.py glsl shader.frag --png /tmp/port.png               # always run this
PYTHONPATH=$SKILL/scripts python3 -m forge html toy.glsl -o preview.html            # Shadertoy only
```

The input kind is detected automatically:

| input | detected by | output |
|---|---|---|
| Shadertoy | `mainImage` and no `main` | the same interface as compiled scenes: uniform `{r, t}` at binding 0, `vs` and `fs` entries; y flipped to Shadertoy's bottom-left origin, alpha forced to 1 |
| WebGL 2 (`#version 300 es`) or WebGL 1 (no version) | version line | one WGSL entry point `main`; loose uniforms gathered into one std140 block at binding 0, each `sampler2D` split into a texture and a sampler from binding 1 |
| Vulkan GLSL 450 | `#version 450` | passed through as written |

The stage comes from the extension (`.vert`, `.frag`, `.comp`) or from the content
(`gl_Position`, `local_size_x`). `--stage` overrides it.

`forge glsl` prints the `binding` lines the host must now supply, with byte offsets. A
WebGL program set uniforms by name; WebGPU writes one buffer at those offsets, and
std140 puts a `vec3` or `mat3` column on a 16-byte boundary. `note:` lines report every
rewrite the converter made.

Translation goes through naga's GLSL reader. When naga refuses the source, it is
compiled to SPIR-V with glslang and naga translates that instead (`--backend` forces
either). The glslang route accepts more GLSL but mangles function names; minifying
renames them anyway.

`verify.py glsl` validates and compiles both the WGSL and its minified form.
- **Shadertoy code** is also rendered by Chrome's WebGL2 as the reference and by the
  WGSL on WebGPU, at t=0 and t=1.7. It must reach 30 dB PSNR, and the minified version
  must draw identically.
- **Other GLSL** has no reference renderer, so it is compiled only. To check a compute
  port, run the WGSL with `scripts/forge/gpu.py` `run_jobs` (kind `compute`) and compare
  the result with a numpy version of the algorithm.

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

- **`naga could not translate the GLSL` and glslang also fails** → read glslang's message.
  It is usually real GLSL that Vulkan forbids, such as a sampler passed as a function
  argument (a `note:` names it). Rewrite that part by hand: pass the texture and sampler
  separately.
- **`Tint compiles WGSL` FAILs with `unresolved call target 'subgroupBarrier'`** → the
  WGSL came from an older copy of this converter. Since 0.2.0 it strips the subgroup and
  texture barriers that naga adds for GLSL `barrier()`, keeping `workgroupBarrier()`.
- **A WebGL port renders but the colours or positions are wrong** → check the uniform
  buffer against the `binding` offsets that `forge glsl` printed. The usual mistake is a
  `vec3` written tightly packed instead of on its 16-byte boundary.
- **A Shadertoy port renders upside down in your own host** → you dropped the
  `fragCoord` flip. The shader expects the uniform `r` to hold the canvas size in pixels.
- **Integer `%` or division differs from WebGL for negative operands** → GLSL leaves
  these undefined, and the WGSL takes one definite answer. Rewrite the GLSL to stay
  non-negative.

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
- **GLSL:** `verify.py glsl` must print no FAIL, and for Shadertoy code the PNG rows
  (WebGL | WGSL | difference ×8) must show the same picture. A *bad success* is two blank
  images that match: check that the picture has content. Another is a non-Shadertoy port
  that compiles but was never run against anything.
- **SVG:** `verify.py svg` must print no FAIL, and the PNG must look right. A *bad
  success* is a high PSNR on an SVG whose `warning:` lines show that elements were
  dropped. A missing element still scores well when it is small.

## Diagnosed failures (fixed, kept as signals)

- 2026-11-02, **a switch case that returns**: naga's GLSL reader rejected
  `switch (i) { case 0: return a; ... }` ("fall-through switch case block"), even with a
  `break;` after the `return`. The auto backend now falls back to glslang.
- 2026-11-02, **subgroupBarrier**: GLSL `barrier()` came out of naga as four barriers,
  `subgroupBarrier()` among them, and Tint rejects that call. naga validated the output,
  so only the Tint compile in `verify.py` caught it.
- 2026-11-02, **html preview**: `forge html` had never worked in 0.1.0. A `%` in its CSS
  broke the `%`-formatting of the page template, and nothing ran the command until the
  GLSL work. `selftest.py` now covers every route.
- 2026-11-02, **zero error that looked suspicious**: every Shadertoy fixture matched WebGL
  at 0 error. The images were checked and are real: WebGL and WebGPU both run on
  SwiftShader in the container. Expect small floating-point differences on real GPUs,
  hence the 30 dB bar rather than exact equality.

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
