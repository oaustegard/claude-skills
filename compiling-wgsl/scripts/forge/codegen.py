"""Scene -> WGSL. One fragment shader evaluates every shape's geometry at each pixel.

Per shape, the pixel's user-space point ``p`` is carried into the shape's local
coordinates ``q``, a signed distance is evaluated there (negative inside), scaled back
to user units, and turned into coverage over one pixel. Coverage times paint is
composited back to front with premultiplied "over". Nothing is rasterised ahead of
time, so the output is exact at any resolution.

Geometry:
  circle, ellipse, rounded rect   exact or near-exact SDF formulas
  paths                           polylines (curves flattened within the scene's
                                  tolerance) stored delta-encoded in one ``const``
                                  i32 array; a loop computes the distance to the
                                  segments, the winding number (nonzero/evenodd)
                                  and the stroke distance with butt/square/round caps
  union/subtract/intersect        min/max, or iq's polynomial smooth min with k > 0
Transforms that are static are folded into one matrix; a path under a static transform
is baked into user space so even skew and non-uniform scale stay exact. Animated
transforms run per pixel, in order.

The module's interface: ``@group(0) @binding(0) var<uniform> u: U`` with
``U { r: vec2f, t: f32 }`` (resolution in pixels, time in seconds); entry points ``vs``
(a full-screen triangle, draw 3 vertices) and ``fs``; output premultiplied RGBA.
"""
from __future__ import annotations

import math

from .geom import Affine, bbox, ellipse_path, flatten, rect_path, to_quads, transform_subpaths
from .scene import (
    Circle, Combine, Ellipse, Expr, Linear, Modify, Path, Radial, Rect, Scene, Shape, _fmt,
    is_static, ops_affine, ops_static, sadd, smul, wg,
)

PRELUDE = """struct U { r: vec2f, t: f32 }
@group(0) @binding(0) var<uniform> u: U;

@vertex fn vs(@builtin(vertex_index) i: u32) -> @builtin(position) vec4f {
    return vec4f(vec2f(f32(i % 2u), f32(i / 2u)) * 4. - 1., 0., 1.);
}

fn over(c: vec4f, s: vec4f) -> vec4f { return s + c * (1. - s.a); }
// fill coverage of a signed distance d (in pixels) under a 1-pixel box filter
fn cov(d: f32) -> f32 { return clamp(.5 - d, 0., 1.); }
// stroke coverage: distance d from the centre line, half width h, both in pixels
fn scov(d: f32, h: f32) -> f32 { return clamp(.5 + h - d, 0., 1.) - clamp(.5 - h - d, 0., 1.); }
"""

HELPERS = {
    "rot": """// rotate v by -a (the inverse of an SVG rotate(a))
fn rot(v: vec2f, a: f32) -> vec2f { let s = sin(a); let k = cos(a); return vec2f(k * v.x + s * v.y, k * v.y - s * v.x); }
""",
    "ell": """fn ell(q: vec2f, r: vec2f) -> f32 {
    let k1 = length(q / (r * r));
    if k1 < 1e-9 { return -min(r.x, r.y); }
    let k0 = length(q / r);
    return k0 * (k0 - 1.) / k1;
}
""",
    "box": """fn box(q: vec2f, h: vec2f, r: f32) -> f32 {
    let d = abs(q) - h + r;
    return length(max(d, vec2f(0.))) + min(max(d.x, d.y), 0.) - r;
}
""",
    "smin": """fn smin(a: f32, b: f32, k: f32) -> f32 {
    let h = clamp(.5 + .5 * (b - a) / k, 0., 1.);
    return mix(b, a, h) - k * h * (1. - h);
}
""",
    "pth": """// squared distance from p to the quadratic Bezier a-c-b: the closest t solves a cubic
// (Cardano; the trigonometric branch when it has three real roots)
fn qd2(p: vec2f, a: vec2f, c: vec2f, b: vec2f) -> f32 {
    let e = c - a;
    let f = a - 2. * c + b;
    let g = a - p;
    let kk = 1. / dot(f, f);
    let kx = kk * dot(e, f);
    let ky = kk * (2. * dot(e, e) + dot(g, f)) / 3.;
    let kz = kk * dot(g, e);
    let pp = ky - kx * kx;
    let q = kx * (2. * kx * kx - 3. * ky) + kz;
    let h = q * q + 4. * pp * pp * pp;
    if h >= 0. {
        let hs = sqrt(h);
        let x = (vec2f(hs, -hs) - q) * .5;
        let uv = sign(x) * pow(abs(x), vec2f(1. / 3.));
        let t = clamp(uv.x + uv.y - kx, 0., 1.);
        let v = g + (2. * e + f * t) * t;
        return dot(v, v);
    }
    let z = sqrt(-pp);
    let w = acos(q / (pp * z * 2.)) / 3.;
    let m = cos(w);
    let n = sin(w) * 1.7320508;
    let t = clamp(vec2f(m + m, -n - m) * z - kx, vec2f(0.), vec2f(1.));
    let v0 = g + (2. * e + f * t.x) * t.x;
    let v1 = g + (2. * e + f * t.y) * t.y;
    return min(dot(v0, v0), dot(v1, v1));
}

// distance to path data D[s..e): x = unsigned fill distance, y = stroke distance to the
// centre line (butt/square caps on open contours), z = winding number. Segments are
// lines or y-monotone quadratic Beziers, delta-encoded in units of Q.
fn pth(p: vec2f, s: i32, e: i32, hw: f32, cap: i32) -> vec3f {
    var k = s;
    var df = 1e30;
    var ds = 1e30;
    var w = 0;
    while k < e {
        let hd = D[k];
        let n = hd >> 1;
        let cl = (hd & 1) == 1;
        var ip = vec2i(D[k + 1], D[k + 2]);
        k += 3;
        let a0 = vec2f(ip) * Q;
        var a = a0;
        for (var j = 0; j <= n; j++) {
            var b = a0;
            var c = a0;
            var qd = false;
            if j < n {
                let v = D[k];
                qd = (v & 1) == 1;
                ip += vec2i(v >> 1, D[k + 1]);
                k += 2;
                if qd {
                    c = vec2f(ip) * Q;
                    ip += vec2i(D[k], D[k + 1]);
                    k += 2;
                }
                b = vec2f(ip) * Q;
            } else if all(a == a0) {
                break;
            }
            var d2: f32;
            var t0 = b - a;
            var t1 = b - a;
            if qd {
                d2 = qd2(p, a, c, b);
                t0 = c - a;
                t1 = b - c;
            } else {
                let ba = b - a;
                let pa = p - a;
                let dv = pa - ba * clamp(dot(pa, ba) / max(dot(ba, ba), 1e-20), 0., 1.);
                d2 = dot(dv, dv);
            }
            df = min(df, d2);
            if (a.y <= p.y) != (b.y <= p.y) {
                var x: f32;
                if qd {
                    let qa = a.y - 2. * c.y + b.y;
                    let qb = 2. * (c.y - a.y);
                    let qc = a.y - p.y;
                    var t = -qc / qb;
                    if abs(qa) > 1e-7 * abs(qb) {
                        let r = sqrt(max(qb * qb - 4. * qa * qc, 0.));
                        let r1 = (-qb + r) / (2. * qa);
                        let r2 = (-qb - r) / (2. * qa);
                        t = select(r2, r1, abs(r1 - .5) < abs(r2 - .5));
                    }
                    t = clamp(t, 0., 1.);
                    x = mix(mix(a.x, c.x, t), mix(c.x, b.x, t), t);
                } else {
                    x = mix(a.x, b.x, (p.y - a.y) / (b.y - a.y));
                }
                if x > p.x { w += select(-1, 1, b.y > a.y); }
            }
{STROKE}            a = b;
        }
    }
    return vec3f(sqrt(df), sqrt(ds), f32(w));
}
""",
}

STROKE_BLOCK = """            if j < n || cl {
                var sd = d2;
                if !cl && cap != 1 {
                    if j == 0 {
                        let u = normalize(t0);
                        let ex = -dot(p - a, u);
                        if ex > 0. {
                            let pr = abs(u.x * (p.y - a.y) - u.y * (p.x - a.x));
                            let m = select(max(pr, hw + ex), max(pr, ex), cap == 2);
                            sd = m * m;
                        }
                    }
                    if j == n - 1 {
                        let u = normalize(t1);
                        let ex = dot(p - b, u);
                        if ex > 0. {
                            let pr = abs(u.x * (p.y - b.y) - u.y * (p.x - b.x));
                            let m = select(max(pr, hw + ex), max(pr, ex), cap == 2);
                            sd = min(sd, m * m);
                        }
                    }
                }
                ds = min(ds, sd);
            }
"""

CAPS = {"butt": 0, "round": 1, "square": 2}

# A run of at least TABLE_MIN_RUN consecutive plain shapes (static path or primitive,
# solid fill and/or stroke) is drawn by one loop over a table instead of one block of
# code per shape: matplotlib output, traced images and icon sets have hundreds of them,
# and unrolled code that size crashed SwiftShader's pipeline compiler.
TABLE_MIN_RUN = 4
TABLE_ROW = 10        # s, e, fill rgba8, stroke rgba8, half width (f32 bits), flags, bbox cx cy hx hy (Q units)
# Path data and tables above this many i32 go to a storage buffer at binding 1 instead of a
# const array: Tint refuses array constructors over 32767 elements, and a big const array
# indexed at run time is copied per invocation by some backends.
CONST_LIMIT = 8192
SEGMENT_WARN = 20000

TABLE_FN = """// draw table rows D[a..b) back to front over c{DOC}
fn tbl(p: vec2f, px: f32, a: i32, b: i32, c0: vec4f{ARG}) -> vec4f {
    var c = c0;
    for (var i = a; i < b; i += 10) {{REVEAL}
        let hw = bitcast<f32>(D[i + 4]);
        let ctr = vec2f(f32(D[i + 6]), f32(D[i + 7])) * Q;
        let ext = vec2f(f32(D[i + 8]), f32(D[i + 9])) * Q + hw + 2. * px;
        if any(abs(p - ctr) > ext) { continue; }
        let fl = D[i + 5];
        let r = pth(p, D[i], D[i + 1], hw, (fl >> 3) & 3);
        if (fl & 1) != 0 {
            var inside = r.z != 0.;
            if (fl & 4) != 0 { inside = (i32(r.z) & 1) != 0; }
            let k = unpack4x8unorm(bitcast<u32>(D[i + 2]));
            c = over(c, vec4f(k.rgb * k.a, k.a){W} * cov(select(r.x, -r.x, inside) / px));
        }
        if (fl & 2) != 0 {
            let k = unpack4x8unorm(bitcast<u32>(D[i + 3]));
            c = over(c, vec4f(k.rgb * k.a, k.a){W} * scov(r.y / px, hw / px));
        }
    }
    return c;
}
"""


def table_fn(paint: bool) -> str:
    """tbl(); with paint, r0 is how many rows are revealed: later rows are not drawn yet (the
    loop stops), and the row being revealed fades in."""
    if not paint:
        return TABLE_FN.replace("{DOC}", "").replace("{ARG}", "").replace("{REVEAL}", "").replace("{W}", "")
    return (TABLE_FN.replace("{DOC}", "; rows from r0 on are not revealed yet")
            .replace("{ARG}", ", r0: f32")
            .replace("{REVEAL}", "\n        let w = clamp(r0 - f32((i - a) / 10), 0., 1.);\n        if w <= 0. { break; }")
            .replace("{W}", " * w"))


def _rgba8(rgba, alpha_mul) -> int:
    """Straight RGBA packed for unpack4x8unorm (red in the low byte), as a signed i32."""
    r, g, b, a = rgba
    a = a * alpha_mul
    v = 0
    for k, x in enumerate((r, g, b, a)):
        v |= int(round(min(max(x, 0.0), 1.0) * 255)) << (8 * k)
    return v - (1 << 32) if v >= 1 << 31 else v


def _f32_bits(x: float) -> int:
    import struct
    return struct.unpack("<i", struct.pack("<f", float(x)))[0]


def table_eligible(sh) -> bool:
    g = sh.geom
    if not isinstance(g, (Path, Circle, Ellipse, Rect)) or g.ops or sh.soft:
        return False
    if not ops_static(sh.ops) or not is_static(sh.opacity, sh.stroke_width):
        return False
    if isinstance(g, Circle) and not is_static(g.cx, g.cy, g.r):
        return False
    if isinstance(g, Ellipse) and not is_static(g.cx, g.cy, g.rx, g.ry):
        return False
    if isinstance(g, Rect) and not is_static(g.x, g.y, g.w, g.h, g.rx, g.ry):
        return False
    paints = [x for x in (sh.fill, sh.stroke) if x is not None]
    return bool(paints) and all(isinstance(x, tuple) for x in paints)


def _v2(x, y) -> str:
    return f"vec2f({wg(x)}, {wg(y)})"


def _c(v) -> str:
    """A colour channel: 4 decimals is within 5e-5, far below one 8-bit step."""
    return _fmt(round(v, 4))


def _vec4(rgba) -> str:
    r, g, b, a = rgba
    return f"vec4f({_c(r * a)}, {_c(g * a)}, {_c(b * a)}, {_c(a)})"


def _mat_apply(m: Affine, v: str) -> str:
    """WGSL for m applied to the vec2f expression v."""
    if m.is_identity():
        return v
    if abs(m.b) < 1e-15 and abs(m.c) < 1e-15:
        parts = []
        sx, sy = m.a, m.d
        lin = v if (sx == 1 and sy == 1) else (
            f"{v} * {_fmt(sx)}" if sx == sy else f"{v} * vec2f({_fmt(sx)}, {_fmt(sy)})")
        if m.e or m.f:
            return f"({lin} + vec2f({_fmt(m.e)}, {_fmt(m.f)}))"
        return f"({lin})"
    mat = f"mat2x2f({_fmt(m.a)}, {_fmt(m.b)}, {_fmt(m.c)}, {_fmt(m.d)})"
    if m.e or m.f:
        return f"({mat} * {v} + vec2f({_fmt(m.e)}, {_fmt(m.f)}))"
    return f"({mat} * {v})"


class Gen:
    def __init__(self, scene: Scene):
        self.scene = scene
        vx, vy, vw, vh = scene.viewbox
        # user units per output pixel at the scene's nominal size
        self.nominal_px = max(vw / scene.width, vh / scene.height)
        # cubic -> quadratic error; quadratics converge as n^-3, so a tight bound is cheap
        self.tol = scene.tolerance * self.nominal_px * 0.1
        # coordinate grid: a power of two near 1/grid of a nominal pixel (exact in f32)
        self.quantum = 2.0 ** math.floor(math.log2(self.nominal_px / getattr(scene, "grid", 64)))
        self.data: list[int] = []
        self.helpers: set[str] = set()
        self.fns: list[str] = []
        self.body: list[str] = []
        self.nvars = 0
        self.path_strokes = False
        self.data_buffer: bytes | None = None
        self.table_rows = 0
        self.segments = 0
        self.paint_in = getattr(scene, "paint_in", None)   # seconds to paint the scene in, shape by shape
        self.ordinal = 0                                    # shapes drawn so far, in paint order

    # ---------------------------------------------------------------- points
    def local(self, ops, q="p"):
        """Carry point expression q through the inverse of ops. Returns (expr, dscale expr|float)."""
        stmts, scale = [], 1.0
        cur = q
        static_run = []

        def flush():
            nonlocal cur, scale
            if static_run:
                m = Affine()
                for op in static_run:
                    m = m @ ops_affine([op])
                inv = m.inverse()
                cur = _mat_apply(inv, cur)
                scale = scale * m.scale_factor if not isinstance(scale, Expr) else scale * m.scale_factor
                static_run.clear()
        for op in ops:
            if op[0] == "matrix" or is_static(*op[1:]):
                static_run.append(op)
                continue
            flush()
            kind = op[0]
            if kind == "translate":
                cur = f"({cur} - {_v2(op[1], op[2])})"
            elif kind == "rotate":
                self.helpers.add("rot")
                ang = Expr.lift(op[1]) * (math.pi / 180)
                if is_static(op[2], op[3]) and op[2] == 0 and op[3] == 0:
                    cur = f"rot({cur}, {ang.w})"
                else:
                    c = _v2(op[2], op[3])
                    cur = f"(rot({cur} - {c}, {ang.w}) + {c})"
            elif kind == "scale":
                cur = f"({cur} / {_v2(op[1], op[2])})"
                s = Expr("sqrt(abs(" + (Expr.lift(op[1]) * op[2]).w + "))",
                         lambda t, a=op[1], b=op[2]: math.sqrt(abs((a.f(t) if isinstance(a, Expr) else a) * (b.f(t) if isinstance(b, Expr) else b))))
                scale = Expr.lift(scale) * s
        flush()
        return cur, scale

    def var(self, expr) -> str:
        self.nvars += 1
        name = f"q{self.nvars}"
        self.body.append(f"        let {name} = {expr};")
        return name

    # ---------------------------------------------------------------- geometry
    def sdf(self, g, q: str, hw: str, cap: int, baked_paths: bool):
        """Returns (signed distance expr, stroke-distance expr or None) in g's parent units."""
        if g.ops:
            gq, sc = self.local(g.ops, q)
            gq = self.var(gq)
            d, sd = self.sdf_bare(g, gq, hw, cap)
            mul = "" if sc == 1.0 else f" * {wg(sc)}"
            return (f"({d}){mul}" if mul else d), (f"({sd}){mul}" if (sd and mul) else sd)
        return self.sdf_bare(g, q, hw, cap)

    def sdf_bare(self, g, q, hw, cap):
        if isinstance(g, Circle):
            return f"(length({q} - {_v2(g.cx, g.cy)}) - {wg(g.r)})", None
        if isinstance(g, Ellipse):
            self.helpers.add("ell")
            return f"ell({q} - {_v2(g.cx, g.cy)}, {_v2(g.rx, g.ry)})", None
        if isinstance(g, Rect):
            ry = g.ry if g.ry is not None else g.rx
            if is_static(g.rx, ry) and g.rx != ry:
                return self.sdf_bare(Path(rect_path(g.x, g.y, g.w, g.h, g.rx, ry)), q, hw, cap)
            self.helpers.add("box")
            hx, hy = smul(g.w, 0.5), smul(g.h, 0.5)
            cx, cy = sadd(g.x, hx), sadd(g.y, hy)
            r = g.rx
            if is_static(r, g.w, g.h):
                r = min(r, g.w / 2, g.h / 2)
            return f"box({q} - {_v2(cx, cy)}, {_v2(hx, hy)}, {wg(r)})", None
        if isinstance(g, Path):
            self.helpers.add("pth")
            if hw != "0.":
                self.path_strokes = True
            s, e = self.encode(to_quads(g.subpaths, self.tol))
            v = self.var(f"pth({q}, {s}, {e}, {hw}, {cap})")
            return f"select({v}.x, -{v}.x, {{inside:{v}}})", f"{v}.y"
        if isinstance(g, Combine):
            a, _ = self.sdf(g.a, q, hw, cap, False)
            b, _ = self.sdf(g.b, q, hw, cap, False)
            a, b = self._resolve_inside(a, "nonzero"), self._resolve_inside(b, "nonzero")
            k = g.k
            if g.op == "union":
                if k:
                    self.helpers.add("smin")
                    return f"smin({a}, {b}, {wg(k)})", None
                return f"min({a}, {b})", None
            if g.op == "subtract":
                if k:
                    self.helpers.add("smin")
                    return f"-smin(-({a}), {b}, {wg(k)})", None
                return f"max({a}, -({b}))", None
            if g.op == "intersect":
                if k:
                    self.helpers.add("smin")
                    return f"-smin(-({a}), -({b}), {wg(k)})", None
                return f"max({a}, {b})", None
        if isinstance(g, Modify):
            d, _ = self.sdf(g.g, q, hw, cap, False)
            d = self._resolve_inside(d, "nonzero")
            if g.op == "round":
                return f"({d} - {wg(g.r)})", None
            return f"(abs({d}) - {wg(g.r)})", None
        raise TypeError(g)

    @staticmethod
    def _resolve_inside(d: str, rule: str) -> str:
        """Fill in the {inside:v} placeholder a path distance carries."""
        import re
        def rep(m):
            v = m.group(1)
            return f"{v}.z != 0." if rule == "nonzero" else f"(i32({v}.z) & 1) != 0"
        return re.sub(r"\{inside:(\w+)\}", rep, d)

    def encode(self, contours) -> tuple[int, int]:
        """Append contours of ('L', a, b) / ('Q', a, c, b) segments to D. Returns [start, end).

        Per contour: header n*2+closed (n explicit segments), the start point, then per
        segment the delta to its end point, x doubled with the low bit marking a
        quadratic, whose control point comes first and end point second. All in units of
        Q. A closed contour's closing line back to the start point is implicit."""
        Q = self.quantum
        start = len(self.data)
        for segs, closed in contours:
            q = lambda pt: (round(pt[0] / Q), round(pt[1] / Q))   # noqa: E731
            cur = q(segs[0][1])
            body, n = [], 0
            first = cur
            for sg in segs:
                b = q(sg[-1])
                if sg[0] == "Q":
                    c = q(sg[2])
                    a = cur
                    # keep the control point inside the endpoints' y range (monotone after rounding)
                    lo, hi = min(a[1], b[1]), max(a[1], b[1])
                    c = (c[0], min(max(c[1], lo), hi))
                    # straight after rounding: emit a line
                    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
                    blen = math.hypot(b[0] - a[0], b[1] - a[1])
                    if blen == 0 and c == a:
                        continue
                    if blen > 0 and abs(cross) / blen < 0.5:
                        if b == cur:
                            continue
                        body += [2 * (b[0] - cur[0]), b[1] - cur[1]]
                    else:
                        body += [2 * (c[0] - cur[0]) + 1, c[1] - cur[1], b[0] - c[0], b[1] - c[1]]
                else:
                    if b == cur:
                        continue
                    body += [2 * (b[0] - cur[0]), b[1] - cur[1]]
                n += 1
                cur = b
            if n == 0:
                continue
            self.data += [2 * n + (1 if closed else 0), first[0], first[1]] + body
            self.segments += n
        return start, len(self.data)

    # ---------------------------------------------------------------- paint
    def paint(self, p, opacity, shape_local_q: str, local_from_q: Affine | None, geom_bbox):
        """WGSL vec4f (premultiplied) for paint p at point q."""
        if isinstance(p, tuple):
            if is_static(opacity):
                r, g, b, a = p
                return _vec4((r, g, b, a * opacity))
            return f"{_vec4(p)} * {wg(opacity)}"
        idx = len(self.fns)
        # gradient space <- local space: inverse(units map @ gradientTransform)
        m = p.transform
        if p.units == "bbox":
            x0, y0, x1, y1 = geom_bbox
            m = Affine(x1 - x0, 0, 0, y1 - y0, x0, y0) @ m
        g_from_local = m.inverse()
        g_from_q = g_from_local @ local_from_q if local_from_q is not None else g_from_local
        gp = _mat_apply(g_from_q, "q")
        if isinstance(p, Linear):
            dx, dy = p.x2 - p.x1, p.y2 - p.y1
            L2 = dx * dx + dy * dy or 1e-12
            t = f"dot({gp} - vec2f({_fmt(p.x1)}, {_fmt(p.y1)}), vec2f({_fmt(dx / L2)}, {_fmt(dy / L2)}))"
        else:
            t = f"length({gp} - vec2f({_fmt(p.cx)}, {_fmt(p.cy)})) / {_fmt(p.r or 1e-12)}"
        stops = sorted(p.stops, key=lambda s: s.offset)
        lines = [f"fn g{idx}(q: vec2f) -> vec4f {{", f"    let t = clamp({t}, 0., 1.);",
                 f"    var c = vec4f({', '.join(_c(v) for v in stops[0].color)});"]
        prev = stops[0].offset
        for s in stops[1:]:
            off = max(s.offset, prev)
            span = off - prev
            col = f"vec4f({', '.join(_c(v) for v in s.color)})"
            if span <= 1e-9:
                lines.append(f"    c = select(c, {col}, t >= {_fmt(off)});")
            else:
                lines.append(f"    c = mix(c, {col}, clamp((t - {_fmt(prev)}) / {_fmt(span)}, 0., 1.));")
            prev = off
        lines.append("    return vec4f(c.rgb * c.a, c.a);")
        lines.append("}")
        self.fns.append("\n".join(lines) + "\n")
        mul = "" if (is_static(opacity) and opacity == 1) else f" * {wg(opacity)}"
        return f"g{idx}({shape_local_q}){mul}"

    # ---------------------------------------------------------------- shapes
    def table_run(self, shapes):
        """Encode a run of plain shapes as table rows; one call of tbl() draws them all."""
        rows = []
        for sh in shapes:
            g = sh.geom
            m = ops_affine(sh.ops)
            subs = g.subpaths if isinstance(g, Path) else _as_subpaths(g)
            if not m.is_identity():
                subs = transform_subpaths(subs, m)
            s0, e0 = self.encode(to_quads(subs, self.tol))
            if s0 == e0:
                continue
            pts = [pt for ss, _ in subs for sg in ss for pt in sg[1:]]
            x0, y0, x1, y1 = bbox(pts)
            Q = self.quantum
            hw = float(sh.stroke_width) * 0.5 * m.scale_factor if sh.stroke is not None else 0.0
            cap = CAPS.get(sh.linecap, 0)
            flags = (1 if sh.fill is not None else 0) | (2 if sh.stroke is not None else 0) \
                | (4 if sh.fill_rule == "evenodd" else 0) | (cap << 3)
            if sh.stroke is not None:
                self.path_strokes = True
            rows += [s0, e0,
                     _rgba8(sh.fill, sh.opacity * sh.fill_opacity) if sh.fill is not None else 0,
                     _rgba8(sh.stroke, sh.opacity * sh.stroke_opacity) if sh.stroke is not None else 0,
                     _f32_bits(hw), flags,
                     round((x0 + x1) / 2 / Q), round((y0 + y1) / 2 / Q),
                     int(math.ceil((x1 - x0) / 2 / Q)) + 1, int(math.ceil((y1 - y0) / 2 / Q)) + 1]
        if not rows:
            return
        a = len(self.data)
        self.data += rows
        n = len(rows) // TABLE_ROW
        self.table_rows += n
        self.helpers.update({"pth", "tbl"})
        reveal = f", rv - {self.ordinal}" if self.paint_in else ""
        self.body.append(f"    c = tbl(p, px, {a}, {len(self.data)}, c{reveal}); // shapes drawn from a table: {n}")
        self.ordinal += n

    def shape(self, k, sh: Shape):
        g = sh.geom
        b = self.body
        weight = ""
        if self.paint_in:
            o = self.ordinal
            self.ordinal += 1
            b.append(f"    if rv > {o} {{ // shape {k}: {type(g).__name__.lower()}, revealed {o}th")
            b.append(f"        let w = clamp(rv - {o}, 0., 1.);")
            weight = " * w"
        else:
            b.append(f"    {{ // shape {k}: {type(g).__name__.lower()}")
        cap = CAPS.get(sh.linecap, 0)
        bake = isinstance(g, (Path, Circle, Ellipse, Rect)) and ops_static(sh.ops) and not g.ops
        m = ops_affine(sh.ops) if bake else None
        local_from_q = None
        geom_box = _geom_bbox(g)
        hw_local = smul(sh.stroke_width, 0.5) if sh.stroke is not None else 0
        if bake and not m.is_identity() and (isinstance(g, Path) or not m.is_similarity()):
            # bake the static transform into the geometry: exact under skew and non-uniform scale
            subs = g.subpaths if isinstance(g, Path) else _as_subpaths(g)
            g = Path(transform_subpaths(subs, m))
            local_from_q = m.inverse()
            q, scale = "p", 1.0
            hw = smul(sh.stroke_width, 0.5 * m.scale_factor) if sh.stroke is not None else 0
        else:
            ops = sh.ops
            q, scale = self.local(ops) if ops else ("p", 1.0)
            if ops:
                if ops_static(ops):
                    local_from_q = None   # q is already local
                q = self.var(q)
            hw = hw_local
        # bounding-box early out for paths with many segments (static only)
        culled = False
        if isinstance(g, Path) and q == "p":
            segs = [sg for ss, _ in g.subpaths for sg in ss]
            nseg = len(segs)
            if nseg >= 6 and is_static(hw):
                allpts = [pt for sg in segs for pt in sg[1:]]
                if allpts:
                    x0, y0, x1, y1 = bbox(allpts)
                    pad = (hw if sh.stroke is not None else 0) + sh.soft
                    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                    hx, hy = (x1 - x0) / 2 + pad, (y1 - y0) / 2 + pad
                    b.append(f"    if all(abs(p - vec2f({_fmt(cx)}, {_fmt(cy)})) < vec2f({_fmt(hx)}, {_fmt(hy)}) + 2. * px) {{")
                    culled = True
        d, sd = self.sdf(g, q, wg(hw) if sh.stroke is not None else "0.", cap, bake)
        d = self._resolve_inside(d, sh.fill_rule)
        mul = "" if scale == 1.0 else f" * {wg(scale)}"
        soft = f" + {_fmt(sh.soft)}" if sh.soft else ""
        if sh.fill is not None:
            col = self.paint(sh.fill, _mul(sh.opacity, sh.fill_opacity), q, local_from_q, geom_box)
            b.append(f"        c = over(c, {col}{weight} * cov(({d}){mul} / (px{soft})));")
        if sh.stroke is not None:
            col = self.paint(sh.stroke, _mul(sh.opacity, sh.stroke_opacity), q, local_from_q, geom_box)
            dist = sd if sd is not None else f"abs({d})"
            b.append(f"        c = over(c, {col}{weight} * scov(({dist}){mul} / (px{soft}), {wg(smul(hw, scale))} / (px{soft})));")
        if culled:
            b.append("    }")
        b.append("    }")

    def generate(self) -> str:
        s = self.scene
        vx, vy, vw, vh = s.viewbox
        k = 0
        shapes = s.shapes
        while k < len(shapes):
            j = k
            while j < len(shapes) and table_eligible(shapes[j]):
                j += 1
            if j - k >= TABLE_MIN_RUN:
                self.table_run(shapes[k:j])
                k = j
            else:
                self.shape(k, shapes[k])
                k += 1
        out = [PRELUDE]
        if self.data:
            out.append(f"const Q = {_fmt(self.quantum)};")
            mode = getattr(s, "data_mode", "auto")
            if mode == "buffer" or (mode == "auto" and len(self.data) > CONST_LIMIT):
                import struct
                self.data_buffer = struct.pack(f"<{len(self.data)}i", *self.data)
                out.append(f"// path data: {len(self.data)} i32 ({len(self.data_buffer)} bytes), "
                           "supplied by the host as a storage buffer")
                out.append("@group(0) @binding(1) var<storage, read> D: array<i32>;\n")
            else:
                rows = []
                for i in range(0, len(self.data), 24):
                    rows.append("    " + ", ".join(str(v) for v in self.data[i:i + 24]))
                out.append(f"const D = array<i32, {len(self.data)}>(\n" + ",\n".join(rows) + "\n);\n")
        for h in ("rot", "ell", "box", "smin", "pth", "tbl"):
            if h in self.helpers:
                text = table_fn(bool(self.paint_in)) if h == "tbl" else HELPERS[h]
                if h == "pth":
                    # fill-only scenes get the path loop without stroke and cap code
                    text = text.replace("{STROKE}", STROKE_BLOCK if self.path_strokes else "")
                out.append(text)
        out.extend(self.fns)
        bg = _vec4(s.background) if s.background else "vec4f(0.)"
        out.append("@fragment fn fs(@builtin(position) f: vec4f) -> @location(0) vec4f {")
        out.append(f"    let s = min(u.r.x / {_fmt(vw)}, u.r.y / {_fmt(vh)});")
        off = f" + vec2f({_fmt(vx)}, {_fmt(vy)})" if (vx or vy) else ""
        out.append(f"    let p = (f.xy - (u.r - vec2f({_fmt(vw)}, {_fmt(vh)}) * s) * .5) / s{off};")
        out.append("    let px = 1. / s;")
        out.append(f"    var c = {bg};")
        if self.paint_in:
            # rv = shapes revealed so far; looping scenes hold the finished picture for a quarter
            # of the paint time, then start again
            dur = _fmt(self.paint_in)
            t = f"fract(u.t / ({dur} * 1.25)) * 1.25" if getattr(s, "paint_loop", False) else f"u.t / {dur}"
            out.append(f"    let rv = clamp({t}, 0., 1.) * {self.ordinal};")
        out.extend(self.body)
        out.append("    return c;")
        out.append("}")
        return "\n".join(out) + "\n"


def _mul(a, b):
    if is_static(a, b):
        return a * b
    return Expr.lift(a) * b


def _as_subpaths(g):
    if isinstance(g, Circle):
        return ellipse_path(g.cx, g.cy, g.r, g.r)
    if isinstance(g, Ellipse):
        return ellipse_path(g.cx, g.cy, g.rx, g.ry)
    if isinstance(g, Rect):
        ry = g.ry if g.ry is not None else g.rx
        return rect_path(g.x, g.y, g.w, g.h, g.rx, ry)
    raise TypeError(g)


def _geom_bbox(g):
    try:
        if isinstance(g, Circle):
            return (g.cx - g.r, g.cy - g.r, g.cx + g.r, g.cy + g.r)
        if isinstance(g, Ellipse):
            return (g.cx - g.rx, g.cy - g.ry, g.cx + g.rx, g.cy + g.ry)
        if isinstance(g, Rect):
            return (g.x, g.y, g.x + g.w, g.y + g.h)
        if isinstance(g, Path):
            pts = [p for pts, _ in flatten(g.subpaths, 0.5) for p in pts]
            return bbox(pts) if pts else (0, 0, 1, 1)
    except TypeError:
        pass
    return (0, 0, 1, 1)


def generate(scene: Scene) -> str:
    """WGSL for the scene. When the path data is too big for a const array, the shader
    reads it from a storage buffer at @group(0) @binding(1), and the bytes to upload are
    left in ``scene.data_buffer`` (None otherwise)."""
    g = Gen(scene)
    src = g.generate()
    scene.data_buffer = g.data_buffer
    scene.segments = g.segments
    if g.segments > SEGMENT_WARN:
        scene.warnings.append(
            f"{g.segments} path segments: a pixel walks every segment of every shape whose bounding box "
            f"covers it, so large overlapping shapes are slow (53,601 segments in full-canvas layers took "
            f"215 s per 512 px frame on SwiftShader; 44,888 in 880 small shapes took 8 s). If it is too "
            f"slow, simplify the paths or bake the image to a texture")
    return src
