"""wgsl-forge command line.

    python3 -m forge minify shader.wgsl [-o out.wgsl] [--no-aliases] [--map]
    python3 -m forge fmt shader.wgsl                 # pretty-print (parse + print)
    python3 -m forge svg drawing.svg [-o out.wgsl] [--minify] [--tolerance 0.2]
    python3 -m forge py scene.py [-o out.wgsl] [--minify]   # module with build() -> Scene
    python3 -m forge html in.(svg|py|wgsl) -o page.html     # self-contained live preview

Output goes to stdout unless -o is given. Byte counts go to stderr.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from .minify import Options, minify
from .printer import to_wgsl
from .wgsl import parse

PREVIEW = """<!doctype html><meta charset="utf-8"><title>wgsl-forge preview</title>
<style>html,body{margin:0;height:100%;background:#fff}canvas{width:100%;height:100%;display:block}</style>
<canvas></canvas><script type="module">
const code = %s;
const cv = document.querySelector("canvas");
const ad = await navigator.gpu?.requestAdapter();
if (!ad) { document.body.textContent = "WebGPU is not available in this browser."; throw 0; }
const dev = await ad.requestDevice();
const ctx = cv.getContext("webgpu"), fmt = navigator.gpu.getPreferredCanvasFormat();
ctx.configure({ device: dev, format: fmt, alphaMode: "premultiplied" });
const mod = dev.createShaderModule({ code });
const pipe = dev.createRenderPipeline({ layout: "auto", vertex: { module: mod, entryPoint: "vs" },
  fragment: { module: mod, entryPoint: "fs", targets: [{ format: fmt }] } });
const ub = dev.createBuffer({ size: 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
const bg = dev.createBindGroup({ layout: pipe.getBindGroupLayout(0), entries: [{ binding: 0, resource: { buffer: ub } }] });
const t0 = performance.now();
function frame() {
  const w = cv.width = cv.clientWidth * devicePixelRatio, h = cv.height = cv.clientHeight * devicePixelRatio;
  dev.queue.writeBuffer(ub, 0, new Float32Array([w, h, (performance.now() - t0) / 1000, 0]));
  const enc = dev.createCommandEncoder();
  const pass = enc.beginRenderPass({ colorAttachments: [{ view: ctx.getCurrentTexture().createView(), loadOp: "clear", storeOp: "store", clearValue: [0, 0, 0, 0] }] });
  pass.setPipeline(pipe); pass.setBindGroup(0, bg); pass.draw(3); pass.end();
  dev.queue.submit([enc.finish()]);
  requestAnimationFrame(frame);
}
frame();
</script>
"""


def _load_scene(path):
    spec = importlib.util.spec_from_file_location("scene_module", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec.loader.exec_module(mod)
    return mod.build()


def _emit(text, out):
    if out:
        Path(out).write_text(text)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m forge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("minify")
    m.add_argument("file")
    m.add_argument("-o", "--out")
    m.add_argument("--no-aliases", action="store_true", help="skip type aliases (better gzip)")
    m.add_argument("--keep", default="", help="comma-separated names never renamed or dropped")
    f = sub.add_parser("fmt")
    f.add_argument("file")
    f.add_argument("-o", "--out")
    for name in ("svg", "py"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("-o", "--out")
        p.add_argument("--minify", action="store_true")
        p.add_argument("--tolerance", type=float, default=None)
    h = sub.add_parser("html")
    h.add_argument("file")
    h.add_argument("-o", "--out", required=True)
    h.add_argument("--minify", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "minify":
        src = Path(a.file).read_text()
        opts = Options(type_aliases=not a.no_aliases, keep=set(filter(None, a.keep.split(","))))
        out = minify(src, opts)
        print(f"{len(src)} -> {len(out)} bytes", file=sys.stderr)
        _emit(out, a.out)
    elif a.cmd == "fmt":
        _emit(to_wgsl(parse(Path(a.file).read_text()), pretty=True), a.out)
    elif a.cmd in ("svg", "py", "html"):
        path = Path(a.file)
        if path.suffix == ".wgsl":
            src = path.read_text()
        else:
            if path.suffix == ".svg":
                from .svg import read_svg
                scene = read_svg(path.read_text(), **({"tolerance": a.tolerance} if getattr(a, "tolerance", None) else {}))
            else:
                scene = _load_scene(path)
                if getattr(a, "tolerance", None):
                    scene.tolerance = a.tolerance
            for w in scene.warnings:
                print(f"warning: {w}", file=sys.stderr)
            src = scene.compile()
        if getattr(a, "minify", False):
            src = minify(src)
        print(f"{len(src)} bytes of WGSL", file=sys.stderr)
        if a.cmd == "html":
            Path(a.out).write_text(PREVIEW % json.dumps(src))
        else:
            _emit(src, a.out)


if __name__ == "__main__":
    main()
