"""SVG document -> Scene.

Supported: svg/g/use/symbol nesting, viewBox and width/height, transform on any
element, rect (rx/ry), circle, ellipse, line, polyline, polygon, path (all commands,
arcs), presentation attributes and ``style=""``, simple ``<style>`` rules (``.class``,
element and ``#id`` selectors), linear and radial gradients (gradientUnits,
gradientTransform, href inheritance of stops), fill-rule, opacity / fill-opacity /
stroke-opacity, stroke-linecap, currentColor, display="none".

Approximated: group opacity multiplies into each child (true group opacity composites
the group as one layer first); stroke joins are round; a radial gradient's focal point
is taken as its centre; spreadMethod is pad. Ignored with a warning: text, image,
clipPath, mask, filter, pattern, marker.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .color import parse_color
from .geom import Affine, parse_path, parse_transform
from .scene import Linear, Radial, Scene, Stop, Path

_INHERITED = {"fill", "stroke", "stroke-width", "fill-opacity", "stroke-opacity", "fill-rule",
              "stroke-linecap", "color", "visibility"}
_UNSUPPORTED = {"text", "image", "clipPath", "mask", "filter", "pattern", "marker", "foreignObject"}
_NUM = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _tag(el):
    return el.tag.rsplit("}", 1)[-1]


def _len(v, default=0.0, ref=None):
    if v is None or v == "":
        return default
    v = v.strip()
    if v.endswith("%") and ref is not None:
        return float(v[:-1]) / 100 * ref
    m = _NUM.match(v)
    return float(m.group()) if m else default


class _Css:
    def __init__(self):
        self.rules = []      # (selector, props)

    def add(self, text):
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", text):
            props = _style_props(body)
            for s in sel.split(","):
                self.rules.append((s.strip(), props))

    def match(self, el):
        out = {}
        cls = set((el.get("class") or "").split())
        eid, tag = el.get("id"), _tag(el)
        for sel, props in self.rules:
            if (sel.startswith(".") and sel[1:] in cls) or (sel.startswith("#") and sel[1:] == eid) \
                    or sel == tag or sel == "*":
                out.update(props)
        return out


def _style_props(s):
    out = {}
    for decl in (s or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            out[k.strip()] = v.strip().replace("!important", "").strip()
    return out


class SvgReader:
    def __init__(self, text: str, width=None, height=None, tolerance=0.2):
        self.root = ET.fromstring(text)
        self.ids = {el.get("id"): el for el in self.root.iter() if el.get("id")}
        self.css = _Css()
        for el in self.root.iter():
            if _tag(el) == "style" and el.text:
                self.css.add(el.text)
        r = self.root
        vb = r.get("viewBox")
        w_attr, h_attr = r.get("width"), r.get("height")
        if vb:
            vbx = [float(v) for v in _NUM.findall(vb)]
        else:
            vbx = [0, 0, _len(w_attr, 300), _len(h_attr, 150)]
        if w_attr and not w_attr.endswith("%"):
            w = _len(w_attr)
        else:
            w = vbx[2]
        if h_attr and not h_attr.endswith("%"):
            h = _len(h_attr)
        else:
            h = vbx[3]
        self.scene = Scene(width or w, height or h, viewbox=vbx, tolerance=tolerance)
        self.warned = set()

    def warn(self, msg):
        if msg not in self.warned:
            self.warned.add(msg)
            self.scene.warnings.append(msg)

    def read(self) -> Scene:
        base = {"fill": "black", "stroke": "none", "stroke-width": "1", "fill-opacity": "1",
                "stroke-opacity": "1", "fill-rule": "nonzero", "stroke-linecap": "butt",
                "color": "black"}
        self.walk(self.root, base, Affine(), 1.0, top=True)
        return self.scene

    def style(self, el, inherited):
        st = {k: v for k, v in inherited.items() if k in _INHERITED}
        for k in ("fill", "stroke", "stroke-width", "fill-opacity", "stroke-opacity", "fill-rule",
                  "stroke-linecap", "opacity", "display", "visibility", "color", "stop-color",
                  "stop-opacity"):
            if el.get(k) is not None:
                st[k] = el.get(k)
        st.update(self.css.match(el))
        st.update(_style_props(el.get("style")))
        return st

    def walk(self, el, inherited, m: Affine, opacity, top=False):
        tag = _tag(el)
        if tag in ("defs", "style", "title", "desc", "metadata", "linearGradient",
                   "radialGradient", "symbol") and not top:
            return
        if tag in _UNSUPPORTED:
            self.warn(f"<{tag}> ignored")
            return
        st = self.style(el, inherited)
        if st.get("display") == "none":
            return
        if not top:
            m = m @ parse_transform(el.get("transform"))
        op = opacity * _len(st.get("opacity"), 1.0)
        if tag in ("svg", "g") or top:
            if tag == "svg" and not top:
                x, y = _len(el.get("x")), _len(el.get("y"))
                m = m @ Affine.translate(x, y)
            for c in el:
                self.walk(c, st, m, op)
            return
        if tag == "use":
            href = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href")
            ref = self.ids.get((href or "").lstrip("#"))
            if ref is None:
                return
            mm = m @ Affine.translate(_len(el.get("x")), _len(el.get("y")))
            if _tag(ref) == "symbol":
                for c in ref:
                    self.walk(c, st, mm, op)
            else:
                self.walk(ref, st, mm, op)
            return
        if st.get("visibility") in ("hidden", "collapse"):
            return
        geom = self.geometry(el, tag)
        if geom is None:
            return
        fill = self.paint(st.get("fill"), st, geom, tag)
        stroke = self.paint(st.get("stroke"), st, geom, tag)
        if tag in ("line", "polyline") and isinstance(geom, Path):
            # open shapes: fill still applies to polyline (SVG fills it), not to line
            if tag == "line":
                fill = None
        sw = _len(st.get("stroke-width"), 1.0)
        if fill is None and (stroke is None or sw <= 0):
            return
        self.scene.shapes.append(self._shape(geom, fill, stroke, sw, op, st, m))

    def _shape(self, geom, fill, stroke, sw, op, st, m):
        from .scene import Shape
        return Shape(geom, fill=fill, stroke=stroke if sw > 0 else None, stroke_width=sw,
                     opacity=op, fill_opacity=_len(st.get("fill-opacity"), 1.0),
                     stroke_opacity=_len(st.get("stroke-opacity"), 1.0),
                     fill_rule="evenodd" if st.get("fill-rule") == "evenodd" else "nonzero",
                     linecap=st.get("stroke-linecap", "butt"),
                     ops=[] if m.is_identity() else [("matrix", m)])

    def geometry(self, el, tag):
        from .scene import Circle, Ellipse, Rect
        g = el.get
        vb = self.scene.viewbox
        if tag == "rect":
            w, h = _len(g("width"), 0, vb[2]), _len(g("height"), 0, vb[3])
            if w <= 0 or h <= 0:
                return None
            rx, ry = g("rx"), g("ry")
            rxv = _len(rx) if rx is not None else None
            ryv = _len(ry) if ry is not None else None
            if rxv is None:
                rxv = ryv or 0.0
            if ryv is None:
                ryv = rxv
            return Rect(_len(g("x"), 0, vb[2]), _len(g("y"), 0, vb[3]), w, h,
                        min(rxv, w / 2), min(ryv, h / 2))
        if tag == "circle":
            r = _len(g("r"))
            return Circle(_len(g("cx")), _len(g("cy")), r) if r > 0 else None
        if tag == "ellipse":
            rx, ry = _len(g("rx")), _len(g("ry"))
            if rx <= 0 or ry <= 0:
                return None
            return Ellipse(_len(g("cx")), _len(g("cy")), rx, ry)
        if tag == "line":
            p0 = (_len(g("x1")), _len(g("y1")))
            p1 = (_len(g("x2")), _len(g("y2")))
            return Path([([("L", p0, p1)], False)])
        if tag in ("polyline", "polygon"):
            v = [float(x) for x in _NUM.findall(g("points") or "")]
            pts = list(zip(v[0::2], v[1::2]))
            if len(pts) < 2:
                return None
            segs = [("L", pts[k], pts[k + 1]) for k in range(len(pts) - 1)]
            closed = tag == "polygon"
            if closed:
                segs.append(("L", pts[-1], pts[0]))
            return Path([(segs, closed)])
        if tag == "path":
            d = g("d")
            if not d:
                return None
            return Path(parse_path(d))
        self.warn(f"<{tag}> ignored")
        return None

    def paint(self, v, st, geom, tag):
        if v is None or v == "none":
            return None
        v = v.strip()
        if v.startswith("url("):
            ident = re.match(r"url\(\s*['\"]?#([^)'\"]+)['\"]?\s*\)", v)
            ref = self.ids.get(ident.group(1)) if ident else None
            if ref is None:
                fallback = v[v.index(")") + 1:].strip()
                return parse_color(fallback) if fallback else None
            return self.gradient(ref)
        if v == "currentColor":
            v = st.get("color", "black")
        try:
            return parse_color(v)
        except ValueError:
            self.warn(f"colour {v!r} unsupported, painted black")
            return (0.0, 0.0, 0.0, 1.0)

    def gradient(self, el):
        tag = _tag(el)
        chain, cur = [], el
        while cur is not None and len(chain) < 8:
            chain.append(cur)
            href = cur.get("href") or cur.get("{http://www.w3.org/1999/xlink}href")
            cur = self.ids.get((href or "").lstrip("#")) if href else None

        def attr(name, default=None):
            for c in chain:
                if c.get(name) is not None:
                    return c.get(name)
            return default
        stops_el = next((c for c in chain if any(_tag(s) == "stop" for s in c)), None)
        stops = []
        for s in (stops_el if stops_el is not None else []):
            if _tag(s) != "stop":
                continue
            st = self.style(s, {})
            off = s.get("offset", "0")
            off = float(off[:-1]) / 100 if off.endswith("%") else float(off)
            col = parse_color(st.get("stop-color", "black")) or (0, 0, 0, 0)
            a = col[3] * _len(st.get("stop-opacity"), 1.0)
            stops.append(Stop(min(max(off, 0.0), 1.0), (col[0], col[1], col[2], a)))
        if not stops:
            return None
        if len(stops) == 1:
            return stops[0].color
        units = "user" if attr("gradientUnits") == "userSpaceOnUse" else "bbox"
        tf = parse_transform(attr("gradientTransform"))
        if _tag(chain[0]) == "linearGradient" or tag == "linearGradient":
            ref = 1.0 if units == "bbox" else None

            def L(name, dflt):
                v = attr(name)
                if v is None:
                    return dflt
                if v.endswith("%"):
                    return float(v[:-1]) / 100 * (1.0 if units == "bbox" else self.scene.viewbox[2])
                return float(v)
            if attr("spreadMethod") not in (None, "pad"):
                self.warn("spreadMethod other than pad treated as pad")
            return Linear(L("x1", 0.0), L("y1", 0.0), L("x2", 1.0 if units == "bbox" else self.scene.viewbox[2]),
                          L("y2", 0.0), stops, units, tf)

        def R(name, dflt):
            v = attr(name)
            if v is None:
                return dflt
            if v.endswith("%"):
                return float(v[:-1]) / 100 * (1.0 if units == "bbox" else self.scene.viewbox[2])
            return float(v)
        half = 0.5 if units == "bbox" else self.scene.viewbox[2] / 2
        if attr("fx") is not None or attr("fy") is not None:
            self.warn("radial gradient focal point approximated by its centre")
        return Radial(R("cx", half), R("cy", half if units == "bbox" else self.scene.viewbox[3] / 2),
                      R("r", half), stops, units, tf)


def read_svg(text: str, width=None, height=None, tolerance=0.2) -> Scene:
    return SvgReader(text, width, height, tolerance).read()


def svg_to_wgsl(text: str, minify=False, **kw) -> str:
    return read_svg(text, **kw).compile(minify=minify)
