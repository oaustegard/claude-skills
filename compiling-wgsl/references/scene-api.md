# Scene API reference

Reference for `forge.scene` (run with `PYTHONPATH=$SKILL/scripts`).

## Scene

`Scene(width, height, viewbox=None, background=None, tolerance=0.2)`
- `width`, `height`: the nominal size. The shader scales to any canvas and fits the
  viewBox with "meet", centred.
- `viewbox`: `(x, y, w, h)`; defaults to `(0, 0, width, height)`.
- `tolerance`: in nominal pixels. The curve fit uses a tenth of it, so the default fits
  curves to 0.02 px.
- `compile(minify=False)`: returns the WGSL text. `to_svg(t=0, width=None,
  height=None)`: the scene at time t as SVG.

## Shapes

All shape methods return the `Shape` and accept the style and transform keywords below.
- `circle(cx, cy, r)`, `ellipse(cx, cy, rx, ry)`, `rect(x, y, w, h, rx=0, ry=None)`
- `line(x1, y1, x2, y2)` (stroke defaults to black), `polyline(points)` (no fill),
  `polygon(points)`
- `path(d)`: SVG path data, every command including arcs.
- `add(geometry)`: any geometry object, including combinations.

Geometry objects for `add`: `Circle`, `Ellipse`, `Rect`, `Path(parse_path(d))`.
Combinators:
- `union(a, b, ..., k=0)` and `smooth_union(a, b, ..., k=8)`
- `subtract(a, b, k=0)` and `intersect(a, b, k=0)`
- `rounded(g, r)`: grows the shape by r.
- `onion(g, w)`: turns the shape into a ring of half-width w.

A geometry can carry its own transform: `Circle(..).transformed(rotate=30)`.

## Style keywords

| keyword | value |
|---|---|
| `fill` | colour, `linear(...)`, `radial(...)` or `None`; default black |
| `stroke` | the same; default none |
| `stroke_width` | number or `T` expression |
| `opacity` | number or `T` expression; multiplies into groups |
| `fill_opacity`, `stroke_opacity` | number |
| `fill_rule` | `"nonzero"` or `"evenodd"` |
| `linecap` | `"butt"`, `"round"` or `"square"`; joins are always round |
| `soft` | extra edge blur in user units, for glows |

Colours: CSS names, `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`, `rgb()`/`rgba()`,
`hsl()`/`hsla()`, or a tuple of floats in 0..1 or ints in 0..255.

Gradients:
- `linear(x1, y1, x2, y2, stops, units="user"|"bbox")`
- `radial(cx, cy, r, stops, units=...)`

Stops are colours spaced evenly, or `(offset, colour)` pairs.

## Transforms

The keywords below work on any shape and on `group()`. They apply in SVG order
(translate, then rotate, then scale), outermost group first.
- `translate=(x, y)`
- `rotate=deg` or `rotate=(deg, cx, cy)`
- `scale=s` or `scale=(sx, sy)`
- `transform="matrix(...) rotate(...)"`: SVG syntax, static values only.

`with s.group(opacity=..., **style, **transform):` applies style defaults and transforms
to every shape drawn inside it.

Static transforms are folded into one matrix, and a path under one is baked into
user space, so skew and non-uniform scale stay exact. Animated transforms run per pixel.

## Time expressions

`T` is the time in seconds. Combine it with `+ - * /` and the functions `sin`, `cos`,
`fract`, `clamp`, `mix`, `smoothstep` and `tri` (absolute value). Each expression
compiles to WGSL over `u.t` and evaluates in Python for `to_svg(t)`. It works for any
geometry number, transform argument, stroke width or opacity. Colours and gradient
stops cannot be animated.
