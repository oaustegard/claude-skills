"""The shape scene: what both front-ends produce and the code generator consumes.

A Scene is an ordered list of Shapes painted back to front. A Shape is a geometry
(an exact signed-distance primitive, a path, or a combination of geometries), a fill
and/or stroke paint, and a transform. Numbers in geometry, transforms, stroke widths and
opacity may be ``Expr`` values built from ``T`` (seconds), which makes the shader
animated: they compile to WGSL expressions over the time uniform and evaluate in Python
for ``to_svg(t)``.

The Python API::

    from forge.scene import *
    s = Scene(400, 300, background="#0b1020")
    s.circle(200, 150, 60, fill=radial(200, 150, 60, ["#ffd36e", "#ff7a3d"]))
    with s.group(translate=(200, 150), rotate=T * 30):
        for k in range(12):
            s.rect(-3, -110, 6, 28, rx=3, fill="#ffd36e", rotate=k * 30)
    s.add(smooth_union(Circle(120, 220, 30), Circle(160, 220, 30), k=15), fill="hotpink")
    wgsl = s.compile()
"""
from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass, field

from .color import parse_color, to_hex
from .geom import Affine, ellipse_path, parse_path, rect_path

# ---------------------------------------------------------------------------- Expr


def _fmt(x: float) -> str:
    """Shortest WGSL literal for x at f32 precision (9 significant digits)."""
    from .minify import shorten_literal
    x = float(f"{float(x):.9g}")
    if abs(x) < 1e-12:
        x = 0.0
    if x == int(x) and abs(x) < 1e15:
        s = str(int(x))
    else:
        s = shorten_literal(repr(abs(x)))
        s = ("-" if x < 0 else "") + s
    return s


class Expr:
    """A scalar that varies with time: a WGSL expression plus a Python evaluator."""
    __slots__ = ("w", "f", "prec")

    def __init__(self, wgsl: str, f, prec=9):
        self.w, self.f, self.prec = wgsl, f, prec

    @staticmethod
    def lift(x):
        return x if isinstance(x, Expr) else Expr(_fmt(x) if x >= 0 else f"({_fmt(x)})", lambda t, x=x: x)

    def _bin(self, o, op, fn, prec):
        a, b = Expr.lift(self), Expr.lift(o)
        aw = a.w if a.prec >= prec else f"({a.w})"
        bw = b.w if b.prec > prec else f"({b.w})"
        return Expr(f"{aw}{op}{bw}", lambda t: fn(a.f(t), b.f(t)), prec)

    def __add__(self, o): return self._bin(o, "+", lambda a, b: a + b, 5)
    def __radd__(self, o): return Expr.lift(o)._bin(self, "+", lambda a, b: a + b, 5)
    def __sub__(self, o): return self._bin(o, "-", lambda a, b: a - b, 5)
    def __rsub__(self, o): return Expr.lift(o)._bin(self, "-", lambda a, b: a - b, 5)
    def __mul__(self, o): return self._bin(o, "*", lambda a, b: a * b, 6)
    def __rmul__(self, o): return Expr.lift(o)._bin(self, "*", lambda a, b: a * b, 6)
    def __truediv__(self, o): return self._bin(o, "/", lambda a, b: a / b, 6)
    def __rtruediv__(self, o): return Expr.lift(o)._bin(self, "/", lambda a, b: a / b, 6)

    def __neg__(self):
        return Expr(f"-{self.w}" if self.prec >= 7 else f"-({self.w})", lambda t: -self.f(t), 7)

    def __call__(self, t):
        return self.f(t)


def _fn(name, pyf):
    def f(*args):
        if not any(isinstance(a, Expr) for a in args):
            return pyf(*args)
        ex = [Expr.lift(a) for a in args]
        return Expr(f"{name}({','.join(e.w for e in ex)})", lambda t: pyf(*(e.f(t) for e in ex)), 9)
    f.__name__ = name
    return f


T = Expr("u.t", lambda t: t)
sin = _fn("sin", math.sin)
cos = _fn("cos", math.cos)
tri = _fn("abs", abs)
fract = _fn("fract", lambda x: x - math.floor(x))
smoothstep = _fn("smoothstep", lambda a, b, x: (lambda u: u * u * (3 - 2 * u))(min(max((x - a) / (b - a), 0), 1)))
clamp = _fn("clamp", lambda x, a, b: min(max(x, a), b))
mix = _fn("mix", lambda a, b, k: a + (b - a) * k)


def smul(a, b):
    return a * b if is_static(a, b) else Expr.lift(a) * b


def sadd(a, b):
    return a + b if is_static(a, b) else Expr.lift(a) + b


def at(x, t):
    return x.f(t) if isinstance(x, Expr) else x


def wg(x) -> str:
    """WGSL text for a number or Expr, safe to use as an operand of any operator."""
    if isinstance(x, Expr):
        return x.w if x.prec >= 9 else f"({x.w})"
    return _fmt(x) if x >= 0 else f"({_fmt(x)})"


def is_static(*xs):
    return not any(isinstance(x, Expr) for x in xs)


# ---------------------------------------------------------------------------- paint

@dataclass
class Stop:
    offset: float
    color: tuple


@dataclass
class Linear:
    x1: float
    y1: float
    x2: float
    y2: float
    stops: list
    units: str = "user"            # 'user' (local coordinates) | 'bbox'
    transform: Affine = field(default_factory=Affine)


@dataclass
class Radial:
    cx: float
    cy: float
    r: float
    stops: list
    units: str = "user"
    transform: Affine = field(default_factory=Affine)


def _stops(stops):
    out = []
    n = len(stops)
    for k, s in enumerate(stops):
        if isinstance(s, Stop):
            out.append(s)
        elif isinstance(s, (tuple, list)) and len(s) == 2 and isinstance(s[0], (int, float)):
            out.append(Stop(float(s[0]), parse_color(s[1])))
        else:
            out.append(Stop(k / max(1, n - 1), parse_color(s)))
    return out


def linear(x1, y1, x2, y2, stops, units="user"):
    return Linear(x1, y1, x2, y2, _stops(stops), units)


def radial(cx, cy, r, stops, units="user"):
    return Radial(cx, cy, r, _stops(stops), units)


def paint(p):
    if p is None or isinstance(p, (Linear, Radial)):
        return p
    return parse_color(p)


# ---------------------------------------------------------------------------- geometry

class Geom:
    """Base class. ``ops`` is this geometry's own transform (list, SVG order)."""
    ops: list = ()

    def transformed(self, **tf):
        self.ops = list(self.ops) + _ops(tf)
        return self


@dataclass(eq=False)
class Circle(Geom):
    cx: object
    cy: object
    r: object


@dataclass(eq=False)
class Ellipse(Geom):
    cx: object
    cy: object
    rx: object
    ry: object


@dataclass(eq=False)
class Rect(Geom):
    x: object
    y: object
    w: object
    h: object
    rx: object = 0
    ry: object = None


@dataclass(eq=False)
class Path(Geom):
    subpaths: list        # [(segments, closed)] from geom.parse_path, local coordinates


@dataclass(eq=False)
class Combine(Geom):
    op: str               # union | subtract | intersect
    a: Geom
    b: Geom
    k: float = 0.0


@dataclass(eq=False)
class Modify(Geom):
    op: str               # round | onion
    g: Geom
    r: object


def union(a, b, *more, k=0.0):
    g = Combine("union", a, b, k)
    for m in more:
        g = Combine("union", g, m, k)
    return g


def smooth_union(a, b, *more, k=8.0):
    return union(a, b, *more, k=k)


def subtract(a, b, k=0.0):
    return Combine("subtract", a, b, k)


def intersect(a, b, k=0.0):
    return Combine("intersect", a, b, k)


def rounded(g, r):
    return Modify("round", g, r)


def onion(g, w):
    return Modify("onion", g, w)


# ---------------------------------------------------------------------------- transforms

def _ops(tf: dict) -> list:
    """Transform keywords -> op list in SVG order (translate, rotate, scale, then matrix)."""
    ops = []
    if tf.get("transform") is not None:
        t = tf["transform"]
        from .geom import parse_transform
        ops.append(("matrix", parse_transform(t) if isinstance(t, str) else t))
    if tf.get("translate") is not None:
        tx, ty = tf["translate"]
        ops.append(("translate", tx, ty))
    if tf.get("rotate") is not None:
        r = tf["rotate"]
        if isinstance(r, (tuple, list)):
            ops.append(("rotate", r[0], r[1], r[2]))
        else:
            ops.append(("rotate", r, 0, 0))
    if tf.get("scale") is not None:
        s = tf["scale"]
        sx, sy = (s, s) if not isinstance(s, (tuple, list)) else s
        ops.append(("scale", sx, sy))
    return ops


def ops_static(ops) -> bool:
    return all(is_static(*op[1:]) for op in ops if op[0] != "matrix")


def ops_affine(ops, t=0.0) -> Affine:
    m = Affine()
    for op in ops:
        kind = op[0]
        if kind == "matrix":
            m = m @ op[1]
        elif kind == "translate":
            m = m @ Affine.translate(at(op[1], t), at(op[2], t))
        elif kind == "rotate":
            m = m @ Affine.rotate(at(op[1], t), at(op[2], t), at(op[3], t))
        elif kind == "scale":
            m = m @ Affine.scale(at(op[1], t), at(op[2], t))
    return m


# ---------------------------------------------------------------------------- shapes

@dataclass(eq=False)
class Shape:
    geom: Geom
    fill: object = (0, 0, 0, 1)        # rgba tuple | Linear | Radial | None
    stroke: object = None
    stroke_width: object = 1.0
    opacity: object = 1.0
    fill_opacity: float = 1.0
    stroke_opacity: float = 1.0
    fill_rule: str = "nonzero"
    linecap: str = "butt"
    soft: float = 0.0                  # extra edge softness in user units (glows)
    ops: list = field(default_factory=list)   # shape transform, SVG order, outermost first


_STYLE_KEYS = {"fill", "stroke", "stroke_width", "opacity", "fill_opacity", "stroke_opacity",
               "fill_rule", "linecap", "soft"}
_TF_KEYS = {"transform", "translate", "rotate", "scale"}


class Scene:
    def __init__(self, width, height, viewbox=None, background=None, tolerance=0.2, grid=64):
        self.width, self.height = width, height
        self.viewbox = tuple(viewbox) if viewbox else (0.0, 0.0, float(width), float(height))
        self.background = parse_color(background) if background else None
        self.tolerance = tolerance      # path flattening error, in output pixels at width x height
        # path coordinates are stored in steps of 1/grid nominal pixel (rounded to a power of 2).
        # Measured on Twemoji's lion at 512 px: 16 -> 33.2 dB, 64 -> 37.8 dB, 128 -> 38.4 dB,
        # gzip bytes 2595 / 2889 / 3003. Coarser grids pay off only for small, simple icons.
        self.grid = grid
        self.shapes: list[Shape] = []
        self._ops: list = []
        self._style: dict = {}
        self._opacity = 1.0
        self.warnings: list[str] = []
        self.data_mode = "auto"         # 'auto' | 'const' | 'buffer': where path data goes
        self.data_buffer: bytes | None = None   # set by compile() when data_mode lands on 'buffer'

    @contextlib.contextmanager
    def group(self, opacity=1.0, **kw):
        saved = (self._ops, self._style, self._opacity)
        self._ops = self._ops + _ops({k: kw[k] for k in _TF_KEYS if k in kw})
        self._style = {**self._style, **{k: v for k, v in kw.items() if k in _STYLE_KEYS}}
        self._opacity = self._opacity * opacity if is_static(self._opacity, opacity) else Expr.lift(self._opacity) * opacity
        try:
            yield self
        finally:
            self._ops, self._style, self._opacity = saved

    def add(self, geom: Geom, **kw) -> Shape:
        style = {**self._style, **{k: v for k, v in kw.items() if k in _STYLE_KEYS}}
        unknown = set(kw) - _STYLE_KEYS - _TF_KEYS
        if unknown:
            raise TypeError(f"unknown style keys {sorted(unknown)}")
        op = style.pop("opacity", 1.0)
        op = op * self._opacity if is_static(op, self._opacity) else Expr.lift(op) * self._opacity
        sh = Shape(geom,
                   fill=paint(style.get("fill", (0, 0, 0, 1))),
                   stroke=paint(style.get("stroke")),
                   stroke_width=style.get("stroke_width", 1.0),
                   opacity=op,
                   fill_opacity=style.get("fill_opacity", 1.0),
                   stroke_opacity=style.get("stroke_opacity", 1.0),
                   fill_rule=style.get("fill_rule", "nonzero"),
                   linecap=style.get("linecap", "butt"),
                   soft=style.get("soft", 0.0),
                   ops=self._ops + _ops({k: kw[k] for k in _TF_KEYS if k in kw}))
        self.shapes.append(sh)
        return sh

    # primitives
    def circle(self, cx, cy, r, **kw):
        return self.add(Circle(cx, cy, r), **kw)

    def ellipse(self, cx, cy, rx, ry, **kw):
        return self.add(Ellipse(cx, cy, rx, ry), **kw)

    def rect(self, x, y, w, h, rx=0, ry=None, **kw):
        return self.add(Rect(x, y, w, h, rx, ry), **kw)

    def path(self, d, **kw):
        return self.add(Path(parse_path(d) if isinstance(d, str) else d), **kw)

    def polygon(self, points, **kw):
        segs = [("L", points[k], points[(k + 1) % len(points)]) for k in range(len(points))]
        return self.add(Path([(segs, True)]), **kw)

    def polyline(self, points, **kw):
        segs = [("L", points[k], points[k + 1]) for k in range(len(points) - 1)]
        kw.setdefault("fill", None)
        return self.add(Path([(segs, False)]), **kw)

    def line(self, x1, y1, x2, y2, **kw):
        kw.setdefault("fill", None)
        kw.setdefault("stroke", "black")
        return self.add(Path([([("L", (x1, y1), (x2, y2))], False)]), **kw)

    def compile(self, minify=False) -> str:
        """WGSL text. Check ``data_buffer`` afterwards: when it is not None the shader
        reads its path data from a storage buffer at binding 1 and the host uploads it."""
        from .codegen import generate
        src = generate(self)
        if minify:
            from .minify import minify as _m
            src = _m(src)
        return src

    # ------------------------------------------------------------------ SVG export
    def to_svg(self, t=0.0, width=None, height=None) -> str:
        """The scene at time t as SVG (no SDF combinations or soft edges)."""
        vb = " ".join(_svgnum(v) for v in self.viewbox)
        w, h = width or self.width, height or self.height
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{vb}">']
        defs = []
        if self.background:
            x, y, vw, vh = self.viewbox
            out.append(f'<rect x="{_svgnum(x - vw)}" y="{_svgnum(y - vh)}" width="{_svgnum(3 * vw)}" '
                       f'height="{_svgnum(3 * vh)}" {_svgpaint("fill", self.background)}/>')
        for k, sh in enumerate(self.shapes):
            out.append(_shape_svg(sh, t, k, defs))
        if defs:
            out.insert(1, "<defs>" + "".join(defs) + "</defs>")
        out.append("</svg>")
        return "\n".join(out)


def _svgnum(v):
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:.6g}"


def _svgpaint(attr, p, defs=None, gid=None):
    if p is None:
        return f'{attr}="none"'
    if isinstance(p, (Linear, Radial)):
        stops = "".join(f'<stop offset="{s.offset:g}" stop-color="{to_hex(s.color)}" '
                        f'stop-opacity="{s.color[3]:g}"/>' for s in p.stops)
        units = ' gradientUnits="userSpaceOnUse"' if p.units == "user" else ""
        tf = p.transform
        gt = "" if tf.is_identity() else f' gradientTransform="matrix({tf.a:g} {tf.b:g} {tf.c:g} {tf.d:g} {tf.e:g} {tf.f:g})"'
        if isinstance(p, Linear):
            defs.append(f'<linearGradient id="{gid}" x1="{p.x1:g}" y1="{p.y1:g}" x2="{p.x2:g}" '
                        f'y2="{p.y2:g}"{units}{gt}>{stops}</linearGradient>')
        else:
            defs.append(f'<radialGradient id="{gid}" cx="{p.cx:g}" cy="{p.cy:g}" r="{p.r:g}"'
                        f'{units}{gt}>{stops}</radialGradient>')
        return f'{attr}="url(#{gid})"'
    return f'{attr}="{to_hex(p)}" {attr}-opacity="{p[3]:g}"' if p[3] < 1 else f'{attr}="{to_hex(p)}"'


def _shape_svg(sh: Shape, t, k, defs):
    g = sh.geom
    if isinstance(g, (Combine, Modify)) or sh.soft:
        raise NotImplementedError("SDF combinations and soft edges have no SVG equivalent")
    m = ops_affine(sh.ops, t) @ ops_affine(getattr(g, "ops", []), t)
    attrs = [_svgpaint("fill", sh.fill, defs, f"f{k}"), _svgpaint("stroke", sh.stroke, defs, f"s{k}")]
    if sh.stroke is not None:
        attrs.append(f'stroke-width="{_svgnum(at(sh.stroke_width, t))}"')
        if sh.linecap != "butt":
            attrs.append(f'stroke-linecap="{sh.linecap}"')
        attrs.append('stroke-linejoin="round"')
    op = at(sh.opacity, t)
    if op != 1:
        attrs.append(f'opacity="{op:g}"')
    if sh.fill_opacity != 1:
        attrs.append(f'fill-opacity="{sh.fill_opacity:g}"')
    if sh.stroke_opacity != 1:
        attrs.append(f'stroke-opacity="{sh.stroke_opacity:g}"')
    if sh.fill_rule != "nonzero":
        attrs.append(f'fill-rule="{sh.fill_rule}"')
    if not m.is_identity():
        attrs.append(f'transform="matrix({m.a:.9g} {m.b:.9g} {m.c:.9g} {m.d:.9g} {m.e:.9g} {m.f:.9g})"')
    a = " ".join(attrs)
    if isinstance(g, Circle):
        return f'<circle cx="{_svgnum(at(g.cx, t))}" cy="{_svgnum(at(g.cy, t))}" r="{_svgnum(at(g.r, t))}" {a}/>'
    if isinstance(g, Ellipse):
        return (f'<ellipse cx="{_svgnum(at(g.cx, t))}" cy="{_svgnum(at(g.cy, t))}" '
                f'rx="{_svgnum(at(g.rx, t))}" ry="{_svgnum(at(g.ry, t))}" {a}/>')
    if isinstance(g, Rect):
        ry = g.ry if g.ry is not None else g.rx
        return (f'<rect x="{_svgnum(at(g.x, t))}" y="{_svgnum(at(g.y, t))}" width="{_svgnum(at(g.w, t))}" '
                f'height="{_svgnum(at(g.h, t))}" rx="{_svgnum(at(g.rx, t))}" ry="{_svgnum(at(ry, t))}" {a}/>')
    if isinstance(g, Path):
        d = []
        for segs, closed in g.subpaths:
            if not segs:
                continue
            d.append(f"M{segs[0][1][0]:.9g} {segs[0][1][1]:.9g}")
            for s in segs:
                pts = " ".join(f"{x:.9g} {y:.9g}" for x, y in s[2:])
                d.append(f"{s[0]}{pts}")
            if closed:
                d.append("Z")
        return f'<path d="{"".join(d)}" {a}/>'
    raise TypeError(g)
