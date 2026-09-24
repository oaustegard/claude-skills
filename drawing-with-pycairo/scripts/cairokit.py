"""cairokit: the pieces pycairo leaves out. Verified on pycairo 1.29.1 / cairo 1.18.0.

    pip install --break-system-packages pycairo numpy uharfbuzz fonttools skia-pathops

    import sys; sys.path.insert(0, "/mnt/skills/user/drawing-with-pycairo/scripts")
    from cairokit import *
"""
from __future__ import annotations

import math
import subprocess
from collections.abc import Callable, Iterable, Sequence

import cairo
import numpy as np

__all__ = [
    "Shaper",
    "append_pathops",
    "blurred",
    "boolean",
    "contact_sheet",
    "frames_to_mp4",
    "from_array",
    "from_rgb_float",
    "gauss_blur",
    "glow",
    "gouraud_mesh",
    "label",
    "new_image",
    "painter_order",
    "pango",
    "pixels",
    "polyline_walker",
    "project",
    "stroke_to_path",
    "to_pathops",
]

RGB = Sequence[float]
Walker = Callable[[float], tuple | None]


# ------------------------------------------------------------------ probe --
def pango() -> tuple | None:
    """Return (Pango, PangoCairo) modules, or None if unavailable.

    Pango gives paragraph layout, wrapping, bidi, font fallback and markup. It is
    often missing in containers (PyGObject built for another Python, or no
    typelibs installed); use Shaper then.
    """
    try:
        import gi
        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Pango, PangoCairo
    except (ImportError, ValueError):
        return None
    return Pango, PangoCairo


# ---------------------------------------------------------------- surfaces --
def new_image(w: int, h: int, bg: RGB | None = (0.07, 0.07, 0.09),
              fmt: cairo.Format = cairo.FORMAT_ARGB32) -> tuple[cairo.ImageSurface, cairo.Context]:
    """Return (ImageSurface, Context); the background is painted unless bg is None."""
    s = cairo.ImageSurface(fmt, w, h)
    c = cairo.Context(s)
    if bg is not None:
        c.set_source_rgb(*bg)
        c.paint()
    return s, c


def label(c: cairo.Context, text: str, x: float, y: float, size: float = 14,
          fg: RGB = (0.9, 0.9, 0.85), box: Sequence[float] | None = (0, 0, 0, 0.55)) -> None:
    """Draw an ASCII caption at baseline (x, y) on an optional RGBA box. Toy text API."""
    c.save()
    c.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(size)
    e = c.text_extents(text)
    if box:
        c.set_source_rgba(*box)
        c.rectangle(x - 6, y - size - 4, e.x_advance + 12, size + 12)
        c.fill()
    c.set_source_rgb(*fg)
    c.move_to(x, y)
    c.show_text(text)
    c.restore()


# ----------------------------------------------------- numpy pixel bridge --
def pixels(s: cairo.ImageSurface) -> np.ndarray:
    """Return a live (h, w, 4) uint8 view of an ARGB32 surface.

    Channel order is B, G, R, A with alpha premultiplied. Call s.mark_dirty()
    after writing through the view.
    """
    s.flush()
    a = np.ndarray((s.get_height(), s.get_stride() // 4, 4), np.uint8, s.get_data())
    return a[:, : s.get_width(), :]


def from_array(bgra: np.ndarray) -> cairo.ImageSurface:
    """Return a new ARGB32 surface from an (h, w, 4) BGRA premultiplied 0-255 array."""
    h, w, _ = bgra.shape
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    pixels(s)[:] = np.clip(bgra, 0, 255).astype(np.uint8)
    s.mark_dirty()
    return s


def from_rgb_float(rgb: np.ndarray) -> cairo.ImageSurface:
    """Return an opaque surface from an (h, w, 3) float RGB array in 0..1 (numpy 'shaders')."""
    h, w, _ = rgb.shape
    out = np.empty((h, w, 4), np.float32)
    out[..., 0], out[..., 1], out[..., 2] = rgb[..., 2], rgb[..., 1], rgb[..., 0]
    out[..., :3] *= 255
    out[..., 3] = 255
    return from_array(out)


def _box(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    cs = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
    n = cs.shape[axis]
    hi = np.take(cs, range(2 * r + 1, n), axis=axis)
    lo = np.take(cs, range(n - 2 * r - 1), axis=axis)
    return (hi - lo) / (2 * r + 1)


def gauss_blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Return a float32 approximately gaussian blur (three box passes per axis).

    Blur premultiplied data as-is: that is correct and avoids dark fringes.
    """
    r = max(1, round(math.sqrt(4 * sigma * sigma + 1) / 2))
    a = a.astype(np.float32)
    for ax in (0, 1):
        for _ in range(3):
            a = _box(a, r, ax)
    return a


def blurred(s: cairo.ImageSurface, sigma: float, gain: float = 1.0) -> cairo.ImageSurface:
    """Return a blurred copy of s (drop shadows, glows, soft masks)."""
    return from_array(gauss_blur(pixels(s), sigma) * gain)


def glow(sharp: cairo.ImageSurface,
         radii: Iterable[tuple[float, float]] = ((6, 2.2), (22, 2.5)),
         bg: RGB | None = (0.03, 0.02, 0.06)) -> cairo.ImageSurface:
    """Return a neon composite: blurred halos (sigma, gain) under the sharp layer, ADDed.

    About 240 ms at 800x600 for two radii.
    """
    px = pixels(sharp)
    acc = sum(gauss_blur(px, sg) * g for sg, g in radii)
    out, c = new_image(sharp.get_width(), sharp.get_height(), bg)
    c.set_source_surface(from_array(acc))
    c.paint()
    c.set_operator(cairo.OPERATOR_ADD)
    c.set_source_surface(sharp)
    c.paint()
    c.set_operator(cairo.OPERATOR_OVER)
    return out


# ------------------------------------------ shaped text (HarfBuzz + outlines) --
def _cairo_pen(glyphs, c: cairo.Context):
    """fontTools BasePen writing into a cairo path. BasePen decomposes composite
    glyphs and implied on-curve points; quadratics are converted to cubics."""
    from fontTools.pens.basePen import BasePen

    class _Pen(BasePen):
        def _moveTo(self, p):
            c.move_to(*p)

        def _lineTo(self, p):
            c.line_to(*p)

        def _curveToOne(self, a, b, p):
            c.curve_to(*a, *b, *p)

        def _qCurveToOne(self, q, p):
            x0, y0 = c.get_current_point()
            c.curve_to(x0 + 2 / 3 * (q[0] - x0), y0 + 2 / 3 * (q[1] - y0),
                       p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]), *p)

        def _closePath(self):
            c.close_path()

    return _Pen(glyphs)


class Shaper:
    """Correctly shaped text for any script, emitted as glyph OUTLINES on a cairo path.

    cairo's show_text() does no shaping: Arabic comes out disjoint and left to
    right, Indic conjuncts fall apart, and there is no kerning. Outlines also
    stay vector on PDF/SVG surfaces and can be bent along curves.
    """

    def __init__(self, font_path: str, features: dict | None = None) -> None:
        import uharfbuzz as hb
        from fontTools.ttLib import TTFont
        self.hb = hb
        self.font = hb.Font(hb.Face(hb.Blob.from_file_path(font_path)))
        self.upem = self.font.face.upem
        tt = TTFont(font_path)
        self.glyphs = tt.getGlyphSet()
        self.order = tt.getGlyphOrder()
        self.features = features or {"kern": True, "liga": True}

    def shape(self, text: str, direction: str | None = None, script: str | None = None,
              language: str | None = None) -> list[tuple[int, int, int, int]]:
        """Return [(glyph_id, x_advance, x_offset, y_offset)] in font units, visual order."""
        buf = self.hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        if direction:
            buf.direction = direction
        if script:
            buf.script = script
        if language:
            buf.language = language
        self.hb.shape(self.font, buf, self.features)
        return [(i.codepoint, p.x_advance, p.x_offset, p.y_offset)
                for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def glyph_path(self, c: cairo.Context, gid: int) -> None:
        """Append one glyph outline in font units, y-up. The caller sets the CTM."""
        self.glyphs[self.order[gid]].draw(_cairo_pen(self.glyphs, c))

    def width(self, text: str, size: float) -> float:
        """Return the advance width of the shaped run in px."""
        return sum(a for _, a, _, _ in self.shape(text)) * size / self.upem

    def text_path(self, c: cairo.Context, text: str, x: float, y: float, size: float) -> float:
        """Append the shaped run at baseline (x, y); return its advance in px.

        Follow with c.fill(), c.stroke() or c.clip() as usual.
        """
        k = size / self.upem
        pen = 0
        for gid, adv, xo, yo in self.shape(text):
            c.save()
            c.translate(x + (pen + xo) * k, y - yo * k)
            c.scale(k, -k)
            self.glyph_path(c, gid)
            c.restore()          # the path survives restore; the CTM applied on append
            pen += adv
        return pen * k

    def text_on_curve(self, c: cairo.Context, text: str, walker: Walker, size: float,
                      start: float = 0.0) -> int:
        """Append glyphs along a curve; return how many fitted.

        walker(dist) returns (x, y, angle) or None past the end (see
        polyline_walker). Each glyph is centred on its arc position.
        """
        k = size / self.upem
        pen = start
        n = 0
        for gid, adv, xo, yo in self.shape(text):
            a = adv * k
            p = walker(pen + a / 2)
            if p is None:
                break
            x, y, ang = p
            c.save()
            c.translate(x, y)
            c.rotate(ang)
            c.translate(-a / 2 + xo * k, -yo * k)
            c.scale(k, -k)
            self.glyph_path(c, gid)
            c.restore()
            pen += a
            n += 1
        return n


def polyline_walker(points: Sequence[Sequence[float]]) -> Walker:
    """Return an arc-length walker over a sampled curve: walker(dist) -> (x, y, angle) | None.

    Sample densely (1-2 px) in the SAME space you draw in (after any squash or
    scale), or glyph spacing drifts. walker.length holds the total length.
    """
    pts = np.asarray(points, float)
    seg = np.diff(pts, axis=0)
    seg_len = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0], np.cumsum(seg_len)])

    def at(d: float) -> tuple | None:
        if d < 0 or d > cum[-1]:
            return None
        i = min(int(np.searchsorted(cum, d, side="right")) - 1, len(seg) - 1)
        t = (d - cum[i]) / (seg_len[i] or 1)
        x, y = pts[i] + seg[i] * t
        return float(x), float(y), math.atan2(seg[i, 1], seg[i, 0])

    at.length = float(cum[-1])
    return at


# --------------------------------------------- path geometry (skia-pathops) --
def to_pathops(c: cairo.Context):
    """Return the context's current path as a pathops.Path (fill rule from the context)."""
    import pathops
    p = pathops.Path()
    p.fillType = (pathops.FillType.EVEN_ODD if c.get_fill_rule() == cairo.FILL_RULE_EVEN_ODD
                  else pathops.FillType.WINDING)
    for kind, pts in c.copy_path():
        if kind == cairo.PATH_MOVE_TO:
            p.moveTo(*pts)
        elif kind == cairo.PATH_LINE_TO:
            p.lineTo(*pts)
        elif kind == cairo.PATH_CURVE_TO:
            p.cubicTo(*pts)
        elif kind == cairo.PATH_CLOSE_PATH:
            p.close()
    return p


def append_pathops(c: cairo.Context, p) -> None:
    """Append a pathops.Path to the context's current path."""
    import pathops
    for verb, pts in p:
        if verb == pathops.PathVerb.MOVE:
            c.move_to(*pts[0])
        elif verb == pathops.PathVerb.LINE:
            c.line_to(*pts[0])
        elif verb == pathops.PathVerb.CUBIC:
            c.curve_to(*pts[0], *pts[1], *pts[2])
        elif verb == pathops.PathVerb.QUAD:
            x0, y0 = c.get_current_point()
            (qx, qy), (x, y) = pts
            c.curve_to(x0 + 2 / 3 * (qx - x0), y0 + 2 / 3 * (qy - y0),
                       x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y), x, y)
        elif verb == pathops.PathVerb.CLOSE:
            c.close_path()
        else:
            raise ValueError(f"unexpected path verb {verb}; call convertConicsToQuads() first")


def boolean(c: cairo.Context, build_a: Callable[[cairo.Context], None],
            build_b: Callable[[cairo.Context], None], op: str = "union") -> None:
    """Replace the current path with a real path boolean of two shapes.

    cairo itself only clips. build_a / build_b each append one shape to c.
    op: union | intersection | difference | xor.
    """
    import pathops
    ops = {"union": pathops.PathOp.UNION, "intersection": pathops.PathOp.INTERSECTION,
           "difference": pathops.PathOp.DIFFERENCE, "xor": pathops.PathOp.XOR}
    c.new_path()
    build_a(c)
    a = to_pathops(c)
    c.new_path()
    build_b(c)
    b = to_pathops(c)
    c.new_path()
    append_pathops(c, pathops.op(a, b, ops[op]))


def stroke_to_path(c: cairo.Context, width: float, cap: str = "round", join: str = "round",
                   miter: float = 4.0) -> None:
    """Replace the current path with the outline of its stroke (cairo has no stroke-to-path).

    cap: butt | round | square. join: miter | round | bevel.
    """
    import pathops
    caps = {"butt": pathops.LineCap.BUTT_CAP, "round": pathops.LineCap.ROUND_CAP,
            "square": pathops.LineCap.SQUARE_CAP}
    joins = {"miter": pathops.LineJoin.MITER_JOIN, "round": pathops.LineJoin.ROUND_JOIN,
             "bevel": pathops.LineJoin.BEVEL_JOIN}
    p = to_pathops(c)
    p.stroke(width, caps[cap], joins[join], miter)
    p.convertConicsToQuads()     # round caps/joins emit conics; simplify() rejects them
    p.simplify()
    c.new_path()
    append_pathops(c, p)


# ------------------------------------------------ 2.5D: painter + Gouraud --
def painter_order(depth: Sequence[float]) -> np.ndarray:
    """Return indices far-to-near. depth: (N,) camera-space z, larger = farther."""
    return np.argsort(-np.asarray(depth))


def gouraud_mesh(quads: np.ndarray, colors: np.ndarray,
                 order: Sequence[int] | None = None) -> cairo.MeshPattern:
    """Return one MeshPattern with a straight-edged Coons patch and 4 corner colours per quad.

    That is Gouraud shading. Patches paint in insertion order, so pass the
    painter order. quads: (N, 4, 2) screen xy. colors: (N, 4, 3 or 4) in 0..1.
    10k quads take ~130 ms, faster than 10k flat fills. PDF keeps the mesh as
    vector shading; the SVG backend rasterises it.
    """
    m = cairo.MeshPattern()
    rgba = colors.shape[-1] == 4
    for q in (range(len(quads)) if order is None else order):
        m.begin_patch()
        m.move_to(*quads[q, 0])
        for k in (1, 2, 3):
            m.line_to(*quads[q, k])
        for k in range(4):
            if rgba:
                m.set_corner_color_rgba(k, *colors[q, k])
            else:
                m.set_corner_color_rgb(k, *colors[q, k])
        m.end_patch()
    return m


def project(pts: np.ndarray, f: float = 9.0, scale: float = 100.0, cx: float = 0.0,
            cy: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Perspective-project (..., 3) points; camera at z=-f looking +z.

    Return (screen xy (..., 2), camera z (...)). Screen y points down.
    """
    z = pts[..., 2] + f
    k = scale * f / z
    return np.stack([cx + pts[..., 0] * k, cy + pts[..., 1] * k], -1), z


# ----------------------------------------------------------------- output --
def frames_to_mp4(pattern: str, out: str, fps: int = 30, crf: int = 20) -> None:
    """Encode numbered PNGs (e.g. 'frames/f%04d.png') to H.264 MP4. Keep w and h even."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(fps), "-i", pattern,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), out], check=True)


def contact_sheet(files: Sequence[str], out: str, cols: int = 2, scale: float = 0.5,
                  gap: int = 8, bg: RGB = (0.02, 0.02, 0.03)) -> str:
    """Tile PNGs into one image so a single Read shows them all; return out."""
    imgs = [cairo.ImageSurface.create_from_png(f) for f in files]
    w = int(max(i.get_width() for i in imgs) * scale)
    h = int(max(i.get_height() for i in imgs) * scale)
    rows = math.ceil(len(imgs) / cols)
    s, c = new_image(cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap, bg)
    for k, img in enumerate(imgs):
        c.save()
        c.translate(gap + (k % cols) * (w + gap), gap + (k // cols) * (h + gap))
        c.scale(scale, scale)
        c.set_source_surface(img)
        c.get_source().set_filter(cairo.FILTER_BEST)
        c.paint()
        c.restore()
    s.write_to_png(out)
    return out
