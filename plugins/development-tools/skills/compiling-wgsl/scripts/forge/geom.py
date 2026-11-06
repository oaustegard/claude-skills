"""2D geometry for the shape front-ends: affine transforms, SVG path data, flattening.

A path is parsed into subpaths of absolute segments (lines, quadratic and cubic Béziers;
arcs become cubics), transformed exactly (affine maps Bézier control points to Bézier
control points), then flattened to polylines within a distance tolerance.
"""
from __future__ import annotations

import math
import re


class Affine:
    """x' = a x + c y + e,  y' = b x + d y + f  (SVG matrix order)."""
    __slots__ = ("a", "b", "c", "d", "e", "f")

    def __init__(self, a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0):
        self.a, self.b, self.c, self.d, self.e, self.f = a, b, c, d, e, f

    @staticmethod
    def translate(tx, ty=0.0):
        return Affine(1, 0, 0, 1, tx, ty)

    @staticmethod
    def scale(sx, sy=None):
        return Affine(sx, 0, 0, sx if sy is None else sy, 0, 0)

    @staticmethod
    def rotate(deg, cx=0.0, cy=0.0):
        r = math.radians(deg)
        cs, sn = math.cos(r), math.sin(r)
        m = Affine(cs, sn, -sn, cs, 0, 0)
        if cx or cy:
            m = Affine.translate(cx, cy) @ m @ Affine.translate(-cx, -cy)
        return m

    @staticmethod
    def skew_x(deg):
        return Affine(1, 0, math.tan(math.radians(deg)), 1, 0, 0)

    @staticmethod
    def skew_y(deg):
        return Affine(1, math.tan(math.radians(deg)), 0, 1, 0, 0)

    def __matmul__(self, o: "Affine") -> "Affine":
        """self after o: (self @ o)(p) = self(o(p))."""
        return Affine(
            self.a * o.a + self.c * o.b, self.b * o.a + self.d * o.b,
            self.a * o.c + self.c * o.d, self.b * o.c + self.d * o.d,
            self.a * o.e + self.c * o.f + self.e, self.b * o.e + self.d * o.f + self.f)

    def apply(self, x, y):
        return self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f

    def inverse(self) -> "Affine":
        det = self.det
        if abs(det) < 1e-300:
            raise ZeroDivisionError("singular transform")
        a, b, c, d = self.d / det, -self.b / det, -self.c / det, self.a / det
        return Affine(a, b, c, d, -(a * self.e + c * self.f), -(b * self.e + d * self.f))

    @property
    def det(self):
        return self.a * self.d - self.b * self.c

    @property
    def scale_factor(self):
        return math.sqrt(abs(self.det))

    def is_identity(self, eps=1e-12):
        return all(abs(v - w) < eps for v, w in zip(
            (self.a, self.b, self.c, self.d, self.e, self.f), (1, 0, 0, 1, 0, 0)))

    def is_similarity(self, eps=1e-9):
        """Rotation + uniform scale (+ translation, + reflection): distances scale uniformly."""
        return (abs(self.a - self.d) < eps * max(1, abs(self.a)) and abs(self.b + self.c) < eps * max(1, abs(self.b))) or \
               (abs(self.a + self.d) < eps * max(1, abs(self.a)) and abs(self.b - self.c) < eps * max(1, abs(self.b)))

    def __repr__(self):
        return f"Affine({self.a:g},{self.b:g},{self.c:g},{self.d:g},{self.e:g},{self.f:g})"


_TF = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")
_NUMS = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def parse_transform(s: str | None) -> Affine:
    m = Affine()
    if not s:
        return m
    for name, args in _TF.findall(s):
        v = [float(x) for x in _NUMS.findall(args)]
        if name == "matrix" and len(v) == 6:
            t = Affine(*v)
        elif name == "translate":
            t = Affine.translate(v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale":
            t = Affine.scale(v[0], v[1] if len(v) > 1 else None)
        elif name == "rotate":
            t = Affine.rotate(v[0], *(v[1:3] if len(v) >= 3 else ()))
        elif name == "skewX":
            t = Affine.skew_x(v[0])
        elif name == "skewY":
            t = Affine.skew_y(v[0])
        else:
            continue
        m = m @ t
    return m


# ---------------------------------------------------------------------------- path data

_PATH_TOK = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _path_tokens(d: str):
    """Tokens of an SVG path, splitting arc flags written without separators ('a1 1 0 01 1 1')."""
    toks = _PATH_TOK.findall(d)
    return toks


def parse_path(d: str):
    """SVG path data -> list of subpaths [(segments, closed)].

    A segment is ('L', p0, p1) | ('Q', p0, c, p1) | ('C', p0, c1, c2, p1), points absolute.
    """
    toks = _path_tokens(d)
    i = 0
    subpaths = []
    segs: list = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    cmd = None
    last_c = None      # last cubic control point (for S)
    last_q = None      # last quadratic control point (for T)

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    def flag():
        nonlocal i
        t = toks[i]
        # a flag is one character, so '014.9' is flag 0, flag 1, then 4.9
        if t[0] in "01" and len(t) > 1:
            toks[i] = t[1:]
            return int(t[0])
        i += 1
        return int(float(t))

    def flush(closed):
        nonlocal segs
        if segs:
            subpaths.append((segs, closed))
        segs = []

    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                if segs and (cur != start):
                    segs.append(("L", cur, start))
                flush(True)
                cur = start
                last_c = last_q = None
                continue
        elif cmd is None:
            raise ValueError("path data must start with a command")
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if c == "M":
            flush(False)
            cur = (ox + num(), oy + num())
            start = cur
            cmd = "l" if rel else "L"      # further pairs are implicit lineto
            last_c = last_q = None
        elif c == "L":
            p = (ox + num(), oy + num())
            segs.append(("L", cur, p))
            cur = p
            last_c = last_q = None
        elif c == "H":
            x = num() + (cur[0] if rel else 0.0)
            p = (x, cur[1])
            segs.append(("L", cur, p))
            cur = p
            last_c = last_q = None
        elif c == "V":
            y = num() + (cur[1] if rel else 0.0)
            p = (cur[0], y)
            segs.append(("L", cur, p))
            cur = p
            last_c = last_q = None
        elif c == "C":
            c1 = (ox + num(), oy + num())
            c2 = (ox + num(), oy + num())
            p = (ox + num(), oy + num())
            segs.append(("C", cur, c1, c2, p))
            cur, last_c, last_q = p, c2, None
        elif c == "S":
            c1 = (2 * cur[0] - last_c[0], 2 * cur[1] - last_c[1]) if last_c else cur
            c2 = (ox + num(), oy + num())
            p = (ox + num(), oy + num())
            segs.append(("C", cur, c1, c2, p))
            cur, last_c, last_q = p, c2, None
        elif c == "Q":
            q = (ox + num(), oy + num())
            p = (ox + num(), oy + num())
            segs.append(("Q", cur, q, p))
            cur, last_q, last_c = p, q, None
        elif c == "T":
            q = (2 * cur[0] - last_q[0], 2 * cur[1] - last_q[1]) if last_q else cur
            p = (ox + num(), oy + num())
            segs.append(("Q", cur, q, p))
            cur, last_q, last_c = p, q, None
        elif c == "A":
            rx, ry, rot = abs(num()), abs(num()), num()
            large, sweep = flag(), flag()
            p = (ox + num(), oy + num())
            for seg in arc_to_cubics(cur, rx, ry, rot, large, sweep, p):
                segs.append(seg)
            cur = p
            last_c = last_q = None
        else:
            raise ValueError(f"unknown path command {cmd}")
    flush(False)
    return subpaths


def arc_to_cubics(p0, rx, ry, phi_deg, large, sweep, p1):
    """SVG elliptical arc (endpoint form) as cubic Béziers (SVG 1.1 F.6.5)."""
    if p0 == p1:
        return []
    if rx == 0 or ry == 0:
        return [("L", p0, p1)]
    phi = math.radians(phi_deg % 360)
    cs, sn = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cs * dx + sn * dy, -sn * dx + cs * dy
    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    cx = cs * cx1 - sn * cy1 + (p0[0] + p1[0]) / 2
    cy = sn * cx1 + cs * cy1 + (p0[1] + p1[1]) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2) - 1e-9)))
    step = dt / n
    k = 4 / 3 * math.tan(step / 4)
    out = []

    def pt(t):
        x, y = rx * math.cos(t), ry * math.sin(t)
        return cs * x - sn * y + cx, sn * x + cs * y + cy

    def der(t):
        x, y = -rx * math.sin(t), ry * math.cos(t)
        return cs * x - sn * y, sn * x + cs * y

    t = t1
    a = p0
    for j in range(n):
        tb = t + step
        b = pt(tb) if j < n - 1 else p1
        da, db = der(t), der(tb)
        c1 = (a[0] + k * da[0], a[1] + k * da[1])
        c2 = (b[0] - k * db[0], b[1] - k * db[1])
        out.append(("C", a, c1, c2, b))
        a, t = b, tb
    return out


def transform_subpaths(subpaths, m: Affine):
    out = []
    for segs, closed in subpaths:
        out.append(([(s[0],) + tuple(m.apply(*p) for p in s[1:]) for s in segs], closed))
    return out


def flatten(subpaths, tol: float):
    """Subpaths of segments -> [(points, closed)] with chord error below ``tol``."""
    out = []
    for segs, closed in subpaths:
        if not segs:
            continue
        pts = [segs[0][1]]
        for s in segs:
            kind = s[0]
            if kind == "L":
                pts.append(s[2])
            elif kind == "Q":
                p0, c, p1 = s[1], s[2], s[3]
                dd = math.hypot(p0[0] - 2 * c[0] + p1[0], p0[1] - 2 * c[1] + p1[1])
                n = max(1, int(math.ceil(math.sqrt(dd / (4 * tol))))) if dd > 0 else 1
                for j in range(1, n + 1):
                    t = j / n
                    u = 1 - t
                    pts.append((u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0],
                                u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]))
            else:
                p0, c1, c2, p1 = s[1], s[2], s[3], s[4]
                d1 = math.hypot(p0[0] - 2 * c1[0] + c2[0], p0[1] - 2 * c1[1] + c2[1])
                d2 = math.hypot(c1[0] - 2 * c2[0] + p1[0], c1[1] - 2 * c2[1] + p1[1])
                dd = max(d1, d2)
                # Wang's bound: n >= sqrt(3/4 * max second difference / tol) for cubics
                n = max(1, int(math.ceil(math.sqrt(0.75 * dd / tol)))) if dd > 0 else 1
                n = min(n, 512)
                for j in range(1, n + 1):
                    t = j / n
                    u = 1 - t
                    pts.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p1[0],
                                u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p1[1]))
        # drop consecutive duplicates
        clean = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - clean[-1][0]) > 1e-12 or abs(p[1] - clean[-1][1]) > 1e-12:
                clean.append(p)
        if closed and len(clean) > 1 and clean[-1] == clean[0]:
            clean.pop()
        out.append((clean, closed))
    return out


def ellipse_path(cx, cy, rx, ry):
    k = 0.5522847498307936
    return [([
        ("C", (cx + rx, cy), (cx + rx, cy + k * ry), (cx + k * rx, cy + ry), (cx, cy + ry)),
        ("C", (cx, cy + ry), (cx - k * rx, cy + ry), (cx - rx, cy + k * ry), (cx - rx, cy)),
        ("C", (cx - rx, cy), (cx - rx, cy - k * ry), (cx - k * rx, cy - ry), (cx, cy - ry)),
        ("C", (cx, cy - ry), (cx + k * rx, cy - ry), (cx + rx, cy - k * ry), (cx + rx, cy)),
    ], True)]


def rect_path(x, y, w, h, rx=0.0, ry=0.0):
    if rx <= 0 and ry <= 0:
        return [([("L", (x, y), (x + w, y)), ("L", (x + w, y), (x + w, y + h)),
                  ("L", (x + w, y + h), (x, y + h)), ("L", (x, y + h), (x, y))], True)]
    rx = min(rx or ry, w / 2)
    ry = min(ry or rx, h / 2)
    k = 0.5522847498307936
    segs = [
        ("L", (x + rx, y), (x + w - rx, y)),
        ("C", (x + w - rx, y), (x + w - rx + k * rx, y), (x + w, y + ry - k * ry), (x + w, y + ry)),
        ("L", (x + w, y + ry), (x + w, y + h - ry)),
        ("C", (x + w, y + h - ry), (x + w, y + h - ry + k * ry), (x + w - rx + k * rx, y + h), (x + w - rx, y + h)),
        ("L", (x + w - rx, y + h), (x + rx, y + h)),
        ("C", (x + rx, y + h), (x + rx - k * rx, y + h), (x, y + h - ry + k * ry), (x, y + h - ry)),
        ("L", (x, y + h - ry), (x, y + ry)),
        ("C", (x, y + ry), (x, y + ry - k * ry), (x + rx - k * rx, y), (x + rx, y)),
    ]
    return [(segs, True)]


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def _quad_split_y(a, c, b):
    """Split a quadratic at its y extremum so each piece is monotone in y."""
    den = a[1] - 2 * c[1] + b[1]
    if den != 0:
        t = (a[1] - c[1]) / den
        if 1e-9 < t < 1 - 1e-9:
            m1, m2 = _lerp(a, c, t), _lerp(c, b, t)
            mid = _lerp(m1, m2, t)
            # at a y extremum both control points share the midpoint's y exactly
            return [(a, (m1[0], mid[1]), mid), (mid, (m2[0], mid[1]), b)]
    return [(a, c, b)]


def _cubic_to_quads(p0, c1, c2, p3, tol):
    """Cubic -> quadratics with error below tol (midpoint approximation, n^-3 convergence)."""
    d3 = math.hypot(p3[0] - 3 * c2[0] + 3 * c1[0] - p0[0], p3[1] - 3 * c2[1] + 3 * c1[1] - p0[1])
    n = max(1, int(math.ceil((math.sqrt(3) / 36 * d3 / tol) ** (1 / 3))))
    n = min(n, 64)
    out = []

    def pt(t):
        u = 1 - t
        return (u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
                u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1])

    def der(t):
        u = 1 - t
        return (3 * (u * u * (c1[0] - p0[0]) + 2 * u * t * (c2[0] - c1[0]) + t * t * (p3[0] - c2[0])),
                3 * (u * u * (c1[1] - p0[1]) + 2 * u * t * (c2[1] - c1[1]) + t * t * (p3[1] - c2[1])))
    for j in range(n):
        t0, t1 = j / n, (j + 1) / n
        a, b = pt(t0), pt(t1)
        h = (t1 - t0) / 3
        da, db = der(t0), der(t1)
        q1 = (a[0] + h * da[0], a[1] + h * da[1])      # sub-cubic control points
        q2 = (b[0] - h * db[0], b[1] - h * db[1])
        c = ((3 * (q1[0] + q2[0]) - a[0] - b[0]) / 4, (3 * (q1[1] + q2[1]) - a[1] - b[1]) / 4)
        out.append((a, c, b))
    return out


def to_quads(subpaths, tol):
    """Subpaths -> [(segments, closed)] where a segment is ('L', a, b) or ('Q', a, c, b),
    every quadratic monotone in y. Cubics are approximated within tol."""
    out = []
    for segs, closed in subpaths:
        res = []
        for s in segs:
            if s[0] == "L":
                res.append(s)
            elif s[0] == "Q":
                for a, c, b in _quad_split_y(s[1], s[2], s[3]):
                    res.append(("Q", a, c, b))
            else:
                for a, c, b in _cubic_to_quads(s[1], s[2], s[3], s[4], tol):
                    for a2, c2, b2 in _quad_split_y(a, c, b):
                        res.append(("Q", a2, c2, b2))
        if res:
            out.append((res, closed))
    return out
