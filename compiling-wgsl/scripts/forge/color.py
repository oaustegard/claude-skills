"""CSS colour parsing: #rgb #rgba #rrggbb #rrggbbaa, rgb()/rgba(), hsl()/hsla(), names."""
from __future__ import annotations

import colorsys
import re

_NAMED = dict(x.split(":") for x in """aliceblue:f0f8ff antiquewhite:faebd7 aqua:00ffff
aquamarine:7fffd4 azure:f0ffff beige:f5f5dc bisque:ffe4c4 black:000000 blanchedalmond:ffebcd
blue:0000ff blueviolet:8a2be2 brown:a52a2a burlywood:deb887 cadetblue:5f9ea0 chartreuse:7fff00
chocolate:d2691e coral:ff7f50 cornflowerblue:6495ed cornsilk:fff8dc crimson:dc143c cyan:00ffff
darkblue:00008b darkcyan:008b8b darkgoldenrod:b8860b darkgray:a9a9a9 darkgreen:006400
darkgrey:a9a9a9 darkkhaki:bdb76b darkmagenta:8b008b darkolivegreen:556b2f darkorange:ff8c00
darkorchid:9932cc darkred:8b0000 darksalmon:e9967a darkseagreen:8fbc8f darkslateblue:483d8b
darkslategray:2f4f4f darkslategrey:2f4f4f darkturquoise:00ced1 darkviolet:9400d3
deeppink:ff1493 deepskyblue:00bfff dimgray:696969 dimgrey:696969 dodgerblue:1e90ff
firebrick:b22222 floralwhite:fffaf0 forestgreen:228b22 fuchsia:ff00ff gainsboro:dcdcdc
ghostwhite:f8f8ff gold:ffd700 goldenrod:daa520 gray:808080 grey:808080 green:008000
greenyellow:adff2f honeydew:f0fff0 hotpink:ff69b4 indianred:cd5c5c indigo:4b0082 ivory:fffff0
khaki:f0e68c lavender:e6e6fa lavenderblush:fff0f5 lawngreen:7cfc00 lemonchiffon:fffacd
lightblue:add8e6 lightcoral:f08080 lightcyan:e0ffff lightgoldenrodyellow:fafad2
lightgray:d3d3d3 lightgreen:90ee90 lightgrey:d3d3d3 lightpink:ffb6c1 lightsalmon:ffa07a
lightseagreen:20b2aa lightskyblue:87cefa lightslategray:778899 lightslategrey:778899
lightsteelblue:b0c4de lightyellow:ffffe0 lime:00ff00 limegreen:32cd32 linen:faf0e6
magenta:ff00ff maroon:800000 mediumaquamarine:66cdaa mediumblue:0000cd mediumorchid:ba55d3
mediumpurple:9370db mediumseagreen:3cb371 mediumslateblue:7b68ee mediumspringgreen:00fa9a
mediumturquoise:48d1cc mediumvioletred:c71585 midnightblue:191970 mintcream:f5fffa
mistyrose:ffe4e1 moccasin:ffe4b5 navajowhite:ffdead navy:000080 oldlace:fdf5e6 olive:808000
olivedrab:6b8e23 orange:ffa500 orangered:ff4500 orchid:da70d6 palegoldenrod:eee8aa
palegreen:98fb98 paleturquoise:afeeee palevioletred:db7093 papayawhip:ffefd5 peachpuff:ffdab9
peru:cd853f pink:ffc0cb plum:dda0dd powderblue:b0e0e6 purple:800080 rebeccapurple:663399
red:ff0000 rosybrown:bc8f8f royalblue:4169e1 saddlebrown:8b4513 salmon:fa8072
sandybrown:f4a460 seagreen:2e8b57 seashell:fff5ee sienna:a0522d silver:c0c0c0 skyblue:87ceeb
slateblue:6a5acd slategray:708090 slategrey:708090 snow:fffafa springgreen:00ff7f
steelblue:4682b4 tan:d2b48c teal:008080 thistle:d8bfd8 tomato:ff6347 turquoise:40e0d0
violet:ee82ee wheat:f5deb3 white:ffffff whitesmoke:f5f5f5 yellow:ffff00
yellowgreen:9acd32""".split())

_NUM = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?%?"


def _chan(v: str, scale=255.0):
    if v.endswith("%"):
        return float(v[:-1]) / 100
    return float(v) / scale


def parse_color(c) -> tuple[float, float, float, float] | None:
    """Colour -> straight (r, g, b, a) floats in 0..1; None for 'none'/'transparent'."""
    if c is None:
        return None
    if isinstance(c, (tuple, list)):
        v = [float(x) for x in c]
        if max(v[:3]) > 1:
            v[:3] = [x / 255 for x in v[:3]]
        return (v[0], v[1], v[2], v[3] if len(v) > 3 else 1.0)
    s = str(c).strip().lower()
    if s in ("none", ""):
        return None
    if s == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if s in _NAMED:
        s = "#" + _NAMED[s]
    if s.startswith("#"):
        h = s[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) == 6:
            h += "ff"
        if len(h) != 8:
            raise ValueError(f"bad colour {c!r}")
        v = [int(h[k:k + 2], 16) / 255 for k in (0, 2, 4, 6)]
        return tuple(v)
    m = re.fullmatch(r"(rgba?|hsla?)\((.*)\)", s)
    if m:
        parts = re.findall(_NUM, m.group(2))
        if m.group(1).startswith("rgb"):
            r, g, b = (_chan(p) for p in parts[:3])
        else:
            hue = float(parts[0].rstrip("%")) / 360 % 1
            sat, lig = _chan(parts[1], 100), _chan(parts[2], 100)
            r, g, b = colorsys.hls_to_rgb(hue, lig, sat)
        a = _chan(parts[3], 1.0) if len(parts) > 3 else 1.0
        return (min(max(r, 0), 1), min(max(g, 0), 1), min(max(b, 0), 1), min(max(a, 0), 1))
    raise ValueError(f"unsupported colour {c!r}")


def to_hex(rgba) -> str:
    r, g, b, a = rgba
    return "#%02x%02x%02x" % tuple(round(x * 255) for x in (r, g, b))
