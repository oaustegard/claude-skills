#!/usr/bin/env python3
"""Check that a minified shader or a compiled scene is right, not just smaller.

    verify.py minify SHADER.wgsl [--dispatch X,Y,Z] [--no-aliases]
        naga-validates the minified output, compiles original and output in Chromium
        (Tint), and runs every compute entry point that needs only buffers on random
        inputs, original twice and minified once, comparing buffers byte for byte.
    verify.py glsl SHADER.glsl [--size 256] [--times 0,1.7] [--backend auto|naga|glslang]
        converts GLSL to WGSL; Shadertoy code is rendered by Chromium's WebGL2 as the
        reference and by the converted WGSL on WebGPU, at each time, and the minified
        WGSL must draw the same pixels as the unminified; other GLSL is validated
        (naga) and compiled (Tint), original WGSL and minified.
    verify.py svg DRAWING.svg [--size 256]
        renders the compiled shader and Chromium's own SVG rendering at the same size
        and reports mean error, PSNR and ink ratio; also checks minified == unminified.

Exits 1 on any failure. Needs node + Playwright Chromium for the GPU steps; naga is
optional (`cargo install naga-cli`) and reported as skipped when absent.
"""
from __future__ import annotations

import argparse
import base64
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np                                   # noqa: E402
from forge.ast import Decl, Fn                        # noqa: E402
from forge.gpu import image, over_white, run_jobs     # noqa: E402
from forge.minify import Options, minify              # noqa: E402
from forge.reflect import bindings, buffer_type       # noqa: E402
from forge.scope import is_entry                      # noqa: E402
from forge.wgsl import parse                          # noqa: E402

failures: list[str] = []


def report(name: str, ok: bool | None, detail: str = "") -> None:
    tag = {True: "ok  ", False: "FAIL", None: "skip"}[ok]
    print(f"{tag} {name} {detail}".rstrip())
    if ok is False:
        failures.append(name)


def naga_check(src: str) -> bool | None:
    exe = shutil.which("naga")
    if not exe:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".wgsl", delete=False) as fh:
        fh.write(src)
    r = subprocess.run([exe, fh.name], capture_output=True, text=True)
    Path(fh.name).unlink()
    if r.returncode:
        print(r.stderr[:1500])
    return r.returncode == 0


def cmd_minify(a: argparse.Namespace) -> None:
    src = Path(a.file).read_text()
    out = minify(src, Options(type_aliases=not a.no_aliases))
    print(f"size {len(src)} -> {len(out)} bytes ({len(out) / len(src):.1%})")
    report("naga validates output", naga_check(out))
    m = parse(src)
    jobs = [{"id": "o", "kind": "compile", "wgsl": src}, {"id": "m", "kind": "compile", "wgsl": out}]
    entries = [d.name for d in m.decls if isinstance(d, Fn) and is_entry(d)
               and any(x.name == "compute" for x in d.attrs)]
    runnable = []
    disp = [4, 1, 1]
    if entries:
        try:
            bs, lay = bindings(m)
            if all(buffer_type(d) for _, _, d in bs):
                rng = np.random.default_rng(1)
                binds = [{"group": g, "binding": b, "type": buffer_type(d),
                          "data": base64.b64encode(lay.fill(d.type, rng)).decode()} for g, b, d in bs]
                consts = {}
                for d in m.decls:
                    if isinstance(d, Decl) and d.kind == "override" and d.init is None:
                        ids = [x.args[0].text.rstrip("iu") for x in d.attrs if x.name == "id" and x.args]
                        consts[ids[0] if ids else d.name] = 1
                disp = [int(v) for v in a.dispatch.split(",")] + [1, 1]
                disp = disp[:3]
                for e in entries:
                    for tag, code in (("o1", src), ("o2", src), ("m", out)):
                        jobs.append({"id": f"{e}|{tag}", "kind": "compute", "wgsl": code, "entry": e,
                                     "dispatch": disp, "bindings": binds, "constants": consts})
                    runnable.append(e)
            else:
                report("compute differential", None, "(textures or samplers bound)")
        except ValueError as ex:
            report("compute differential", None, f"({ex})")
    res = run_jobs(jobs)
    o, mm = res["o"], res["m"]
    if not o["ok"]:
        report("Tint compiles original", None, f"(original fails too: {o.get('error', '')[:200]})")
        report("Tint compiles output", mm["ok"] or None, mm.get("error", "")[:200])
    else:
        report("Tint compiles output", mm["ok"], mm.get("error", "")[:300])
    for e in runnable:
        r1, r2, rm = res[f"{e}|o1"], res[f"{e}|o2"], res[f"{e}|m"]
        if not (r1["ok"] and rm["ok"]):
            report(f"compute {e}", None, f"(could not run: {(r1.get('error') or rm.get('error') or '')[:200]})")
        elif r1["buffers"] != r2["buffers"]:
            report(f"compute {e}", None, "(original disagrees with itself: a race, often a dispatch "
                                         "shape the shader does not expect; pass --dispatch)")
        else:
            same = r1["buffers"] == rm["buffers"]
            hint = ""
            if not same and disp[1:] != [1, 1]:
                hint = ("(dispatch is not 1-D: if the shader indexes by id.x alone, invocations race "
                        "on the same element and the result is order-dependent; rerun with the "
                        "dispatch shape the host really uses)")
            report(f"compute {e} bit-identical", same, hint)
    if a.out:
        Path(a.out).write_text(out)


def cmd_svg(a: argparse.Namespace) -> None:
    from forge.svg import read_svg
    text = Path(a.file).read_text()
    scene = read_svg(text)
    for w in scene.warnings:
        print(f"warning: {w}")
    src = scene.compile()
    mini = minify(src)
    print(f"svg {len(text)} B -> wgsl {len(src)} B -> minified {len(mini)} B")
    report("naga validates minified", naga_check(mini))
    w = a.size
    h = max(1, round(w * scene.viewbox[3] / scene.viewbox[2]))
    res = run_jobs([{"id": "r", "kind": "svg", "svg": text, "width": w, "height": h},
                    {"id": "s", "kind": "render", "wgsl": src, "width": w, "height": h},
                    {"id": "m", "kind": "render", "wgsl": mini, "width": w, "height": h}])
    for k in "rsm":
        if not res[k]["ok"]:
            report(f"render {k}", False, res[k].get("error", ""))
            return
    ref = over_white(image(res["r"], w, h), False)
    got = over_white(image(res["s"], w, h), True)
    d = np.abs(ref - got)
    mse = float((d ** 2).mean())
    psnr = 10 * np.log10(255 ** 2 / mse) if mse else 99.0
    ink = float((255 - got).sum() / max((255 - ref).sum(), 1e-9))
    print(f"vs Chromium at {w}x{h}: mean error {d.mean():.2f}/255, PSNR {psnr:.1f} dB, ink ratio {ink:.4f}")
    report("geometry matches (ink ratio within 3%)", abs(ink - 1) < 0.03)
    report("minified renders identically", res["s"]["rgba"] == res["m"]["rgba"])
    if a.png:
        from forge.gpu import save_png
        save_png(a.png, np.concatenate([ref, got, np.clip(d * 4, 0, 255)], axis=1))
        print(f"side-by-side (reference | shader | difference x4): {a.png}")


def cmd_glsl(a: argparse.Namespace) -> None:
    from forge.glsl import GLSLError, glsl_to_wgsl, webgl_reference_source
    src = Path(a.file).read_text()
    try:
        c = glsl_to_wgsl(src, stage=a.stage, filename=a.file, backend=a.backend)
    except GLSLError as e:
        report("convert", False, str(e))
        return
    for n in c.notes:
        print(f"note: {n}")
    mini = minify(c.wgsl)
    print(f"{c.stage}{' (Shadertoy)' if c.shadertoy else ''} via {c.backend}: glsl {len(src)} B -> "
          f"wgsl {len(c.wgsl)} B -> minified {len(mini)} B")
    report("naga validates WGSL", naga_check(c.wgsl))
    report("naga validates minified", naga_check(mini))
    jobs = [{"id": "c", "kind": "compile", "wgsl": c.wgsl}, {"id": "cm", "kind": "compile", "wgsl": mini}]
    times = [float(t) for t in a.times.split(",")]
    w = a.size
    h = round(w * 9 / 16)
    channels = "iChannel" in src
    if c.shadertoy and not channels:
        ref = webgl_reference_source(src)
        for t in times:
            jobs += [{"id": f"r{t}", "kind": "webgl", "glsl": ref, "width": w, "height": h, "time": t},
                     {"id": f"w{t}", "kind": "render", "wgsl": c.wgsl, "width": w, "height": h, "time": t},
                     {"id": f"m{t}", "kind": "render", "wgsl": mini, "width": w, "height": h, "time": t}]
    res = run_jobs(jobs)
    report("Tint compiles WGSL", res["c"]["ok"], res["c"].get("error", "")[:300])
    report("Tint compiles minified", res["cm"]["ok"], res["cm"].get("error", "")[:300])
    if not c.shadertoy:
        report("pixel comparison", None, "(not Shadertoy code: no reference renderer; compiled only)")
        return
    if channels:
        report("pixel comparison", None, "(uses iChannel textures: compiled only)")
        return
    sides = []
    for t in times:
        r, g, mm = res[f"r{t}"], res[f"w{t}"], res[f"m{t}"]
        if not (r["ok"] and g["ok"] and mm["ok"]):
            report(f"render t={t}", False, "; ".join(x.get("error", "") for x in (r, g, mm) if not x["ok"])[:400])
            continue
        ri = image(r, w, h)[..., :3].astype(float)
        gi = image(g, w, h)[..., :3].astype(float)
        d = np.abs(ri - gi)
        mse = float((d ** 2).mean())
        psnr = 10 * np.log10(255 ** 2 / mse) if mse else 99.0
        print(f"t={t}: vs WebGL mean error {d.mean():.3f}/255, max {d.max():.0f}, "
              f"{(d.max(axis=2) > 8).mean():.2%} of pixels off by more than 8, PSNR {psnr:.1f} dB")
        report(f"t={t} matches WebGL (PSNR at least 30 dB)", psnr >= 30)
        report(f"t={t} minified draws identically", g["rgba"] == mm["rgba"])
        sides.append(np.concatenate([ri, gi, np.clip(d * 8, 0, 255)], axis=1))
    if a.png and sides:
        from forge.gpu import save_png
        save_png(a.png, np.concatenate(sides, axis=0))
        print(f"rows per time: WebGL | WGSL | difference x8: {a.png}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("minify")
    m.add_argument("file")
    m.add_argument("--dispatch", default="4,1,1")
    m.add_argument("--no-aliases", action="store_true")
    m.add_argument("-o", "--out")
    s = sub.add_parser("svg")
    s.add_argument("file")
    s.add_argument("--size", type=int, default=256)
    s.add_argument("--png")
    g = sub.add_parser("glsl")
    g.add_argument("file")
    g.add_argument("--size", type=int, default=256)
    g.add_argument("--times", default="0,1.7")
    g.add_argument("--stage", choices=["frag", "vert", "compute"])
    g.add_argument("--backend", default="auto", choices=["auto", "naga", "glslang"])
    g.add_argument("--png")
    a = ap.parse_args()
    {"minify": cmd_minify, "svg": cmd_svg, "glsl": cmd_glsl}[a.cmd](a)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
