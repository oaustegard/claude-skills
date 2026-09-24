#!/usr/bin/env python3
"""Exercise every cairokit function and write a 2x2 contact sheet.

    python3 selftest.py [OUT_DIR]      # default: current directory

Prints timings and the path of selftest.png. Exits 1 if a dependency or a
font is missing. Read the PNG afterwards: a clean exit does not prove the
pictures are right.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
import time

import cairo
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cairokit import (
    Shaper,
    blurred,
    boolean,
    contact_sheet,
    from_rgb_float,
    glow,
    gouraud_mesh,
    label,
    new_image,
    painter_order,
    pango,
    polyline_walker,
    project,
    stroke_to_path,
)

W, H = 800, 600


def font_for(pattern: str) -> str:
    """Return a font file path from fc-match, e.g. 'DejaVu Sans:lang=ar'."""
    out = subprocess.run(["fc-match", "-f", "%{file}", pattern], capture_output=True, text=True, check=False)
    if out.returncode != 0 or not out.stdout:
        sys.exit(f"no font for {pattern!r}; install one (fc-list :lang=ar)")
    return out.stdout


def panel_text(path: str) -> None:
    s, c = new_image(W, H)
    arabic = "مرحبا بالعالم"
    ar = Shaper(font_for("DejaVu Sans:lang=ar"))
    c.new_path()
    ar.text_path(c, arabic, 60, 120, 48)
    c.set_source_rgb(.5, .9, .6)
    c.fill()
    c.select_font_face("DejaVu Sans")
    c.set_font_size(48)
    c.move_to(420, 120)
    c.set_source_rgb(.95, .5, .45)
    c.show_text(arabic)
    ts = np.linspace(0, 4 * math.pi, 4000)
    r = 60 + 14 * ts
    walk = polyline_walker(np.stack([400 + r * np.cos(ts), 380 + r * np.sin(ts) * .55], 1))
    c.new_path()
    n = Shaper(font_for("DejaVu Serif")).text_on_curve(
        c, "text along an arbitrary polyline, spaced by true arc length. " * 3, walk, 18, start=30)
    c.set_source_rgb(.6, .75, 1)
    c.fill()
    label(c, f"A  Shaper.text_path (green) vs show_text (red); text_on_curve: {n} glyphs", 16, H - 16)
    s.write_to_png(path)


def panel_paths(path: str) -> None:
    s, c = new_image(W, H)

    def circle(cx: float):
        return lambda cc: cc.arc(cx, 170, 75, 0, 2 * math.pi)

    for i, op in enumerate(["union", "intersection", "difference", "xor"]):
        x0 = 30 + i * 190
        boolean(c, circle(x0 + 60), circle(x0 + 125), op)
        c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        c.set_source_rgb(.9, .6, .3)
        c.fill_preserve()
        c.set_source_rgb(1, 1, 1)
        c.set_line_width(1.5)
        c.stroke()
        label(c, op, x0 + 55, 285, 13, box=None)
    xs = range(80, 721, 4)
    c.new_path()
    c.move_to(80, 420 + 50 * math.sin(2))
    for x in xs:
        c.line_to(x, 420 + 50 * math.sin(x / 40))
    stroke_to_path(c, 26, cap="round")
    c.set_source_rgb(.3, .5, .9)
    c.fill_preserve()
    c.set_source_rgb(1, 1, 1)
    c.set_line_width(1.5)
    c.stroke()
    label(c, "B  boolean() via skia-pathops; stroke_to_path() outline, re-stroked", 16, H - 16)
    s.write_to_png(path)


def panel_pixels(path: str) -> None:
    yy, xx = np.mgrid[0:H, 0:W] / 90.0
    z = np.sin(xx * 1.3 + np.cos(yy * 1.7)) * np.cos(yy * 1.1 - np.sin(xx))
    bg = from_rgb_float(np.stack([.15 + .1 * z, .1 + .08 * z, .25 + .15 * z], -1))
    sharp, sc = new_image(W, H, bg=None)
    sc.set_line_width(4)
    for k, col in enumerate([(1, .2, .6), (.2, .8, 1)]):
        sc.new_path()
        for i in range(801):
            a = i / 800 * 2 * math.pi
            pt = (400 + 250 * math.sin((3 + 2 * k) * a), 200 + 120 * math.sin(2 * a + k))
            (sc.move_to if i == 0 else sc.line_to)(*pt)
        sc.set_source_rgb(*col)
        sc.stroke()
    s, c = new_image(W, H, bg=None)
    c.set_source_surface(bg)
    c.paint()
    c.set_operator(cairo.OPERATOR_ADD)
    c.set_source_surface(glow(sharp, bg=(0, 0, 0)))
    c.paint()
    c.set_operator(cairo.OPERATOR_OVER)
    card, cc = new_image(W, H, bg=None)
    cc.rectangle(250, 390, 300, 120)
    cc.set_source_rgba(0, 0, 0, .9)
    cc.fill()
    c.set_source_surface(blurred(card, 12), 10, 14)
    c.paint()
    c.rectangle(250, 390, 300, 120)
    c.set_source_rgb(.93, .92, .88)
    c.fill()
    label(c, "drop shadow via blurred()", 285, 460, 16, fg=(.1, .1, .1), box=None)
    label(c, "C  from_rgb_float shader + glow() + blurred() shadow", 16, H - 16)
    s.write_to_png(path)


def panel_3d(path: str) -> None:
    nu, nv, big, small = 120, 40, 2.0, 0.8
    u = np.linspace(0, 2 * np.pi, nu, endpoint=False)[:, None]
    v = np.linspace(0, 2 * np.pi, nv, endpoint=False)[None]
    ring = big + small * np.cos(v)
    pts = np.stack([ring * np.cos(u), ring * np.sin(u), small * np.sin(v) + 0 * u], -1)
    nrm = np.stack([np.cos(v) * np.cos(u), np.cos(v) * np.sin(u), np.sin(v) + 0 * u], -1)
    a = 1.0
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    pts, nrm = pts @ rx.T, nrm @ rx.T
    light = np.array([-.4, -.6, -.7]) / np.linalg.norm([-.4, -.6, -.7])  # toward camera = -z
    half = light + [0, 0, -1]
    half /= np.linalg.norm(half)
    diffuse = np.clip(nrm @ light, 0, 1)[..., None]
    spec = (np.clip(nrm @ half, 0, 1) ** 50)[..., None]
    col = np.clip(np.array([.9, .45, .2]) * (.15 + .85 * diffuse) + spec, 0, 1)
    xy, zz = project(pts, scale=95, cx=W / 2, cy=H / 2 - 10)
    i0, j0 = np.arange(nu), np.arange(nv)
    i1, j1 = (i0 + 1) % nu, (j0 + 1) % nv
    corners = [(i0, j0), (i1, j0), (i1, j1), (i0, j1)]

    def quadify(arr: np.ndarray) -> np.ndarray:
        return np.stack([arr[a_][:, b_] for a_, b_ in corners], 2).reshape(nu * nv, 4, *arr.shape[2:])

    quads, colors, depth = quadify(xy), quadify(col), quadify(zz).mean(1)
    s, c = new_image(W, H)
    c.set_source(gouraud_mesh(quads, colors, painter_order(depth)))
    c.paint()
    label(c, f"D  project + painter_order + gouraud_mesh: {len(quads):,} quads", 16, H - 16)
    s.write_to_png(path)


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    files, times = [], {}
    for name, fn in [("a", panel_text), ("b", panel_paths), ("c", panel_pixels), ("d", panel_3d)]:
        p = os.path.join(out, f"selftest_{name}.png")
        t = time.perf_counter()
        fn(p)
        times[name.upper()] = f"{(time.perf_counter() - t) * 1000:.0f} ms"
        files.append(p)
    sheet = contact_sheet(files, os.path.join(out, "selftest.png"), scale=.75)
    print(f"cairo {cairo.cairo_version_string()}  pycairo {cairo.version}  pango: {'yes' if pango() else 'no'}")
    print(times)
    print(sheet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
