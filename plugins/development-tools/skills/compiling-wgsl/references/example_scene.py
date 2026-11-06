"""An animated scene in the Python shape API: sun on a pulse, rotating rays, rolling hills,
a bobbing boat. Everything static except what depends on T (seconds)."""
# Run with the skill's scripts/ on PYTHONPATH:
#   PYTHONPATH=$SKILL/scripts python3 -m forge py example_scene.py -o sunrise.wgsl
from forge.scene import Scene, T, sin, linear, radial


def build():
    s = Scene(320, 200, background="#0b1630")
    s.rect(0, 0, 320, 200, fill=linear(0, 0, 0, 200, ["#0b1630", "#3b2a5c", "#f08a5d"]))
    with s.group(translate=(160, 130)):
        with s.group(rotate=T * 12):
            for k in range(12):
                s.rect(-2.5, -95, 5, 26, rx=2.5, fill="#ffd36e", opacity=0.7, rotate=k * 30)
        s.circle(0, 0, 44 + 3 * sin(T * 2), fill=radial(0, 0, 50, ["#fff7d6", "#ffd36e", "#ff8a3d"]))
    s.path("M0 150 C 60 120, 110 170, 170 145 S 280 120, 320 150 L 320 200 L 0 200 Z", fill="#2d4a3e")
    s.path("M0 170 C 80 150, 140 190, 220 168 S 300 160, 320 172 L 320 200 L 0 200 Z", fill="#1b2f27")
    with s.group(translate=(90 + 20 * sin(T * 0.7), 166 + 2 * sin(T * 3)), rotate=4 * sin(T * 3)):
        s.path("M-22 0 L 22 0 L 15 9 L -15 9 Z", fill="#6b3e26", stroke="#2a160c", stroke_width=1.2)
        s.line(0, 0, 0, -26, stroke="#2a160c", stroke_width=1.5)
        s.polygon([(1, -25), (1, -4), (16, -4)], fill="#f4efe6")
    return s


if __name__ == "__main__":
    print(build().compile())
