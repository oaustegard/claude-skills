"""GLSL -> WGSL, with naga doing the translation.

naga's GLSL front end reads only Vulkan-flavoured GLSL 4.40/4.50. Most GLSL in the
wild is WebGL's (GLSL ES 3.00 or 1.00) or Shadertoy's, so this module first rewrites
the source into the dialect naga accepts:

  - ``#version 300 es`` / ``100`` / none          -> ``#version 450``; precision lines dropped
  - loose ``uniform T name;``                       -> members of one uniform block at
                                                       set 0, binding 0 (std140 order kept)
  - ``uniform sampler2D s;`` (and Cube, 3D, Array)  -> ``texture2D s_t; sampler s_s;`` with
                                                       every ``texture*(s, ...)`` rewritten
  - ``in``/``out``/``varying``/``attribute`` with
    no ``layout(location=N)``                       -> numbered locations, in order
  - GLSL ES 1.00: ``gl_FragColor``, ``texture2D``,
    ``textureCube``                                 -> an ``out vec4``, ``texture``

Shadertoy code (a ``mainImage`` and no ``main``) is wrapped so the result has the same
interface as the shape compiler's scenes: ``@group(0) @binding(0)`` uniform
``{ r: vec2f, t: f32 }`` (pixels, seconds), entry points ``vs`` (full-screen triangle,
draw 3) and ``fs``. ``iResolution``, ``iTime``, ``iTimeDelta`` (1/60), ``iFrame``
(t*60) and ``iMouse`` (zero) are provided; ``fragCoord`` is flipped to Shadertoy's
bottom-left origin and alpha forced to 1, as Shadertoy displays it. ``iChannel0..3``
become texture/sampler pairs at bindings 1-8, which the host must supply.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SAMPLER_TYPES = {"sampler2D": "texture2D", "samplerCube": "textureCube", "sampler3D": "texture3D",
                 "sampler2DArray": "texture2DArray", "isampler2D": "itexture2D",
                 "usampler2D": "utexture2D", "sampler2DShadow": "texture2D"}

SHADERTOY_HEADER = """layout(set = 0, binding = 0) uniform ForgeU { vec2 r; float t; } forge_u;
#define iResolution vec3(forge_u.r, 1.0)
#define iTime forge_u.t
#define iTimeDelta (1.0 / 60.0)
#define iFrame int(forge_u.t * 60.0)
#define iFrameRate 60.0
#define iMouse vec4(0.0)
#define iDate vec4(0.0)
layout(location = 0) out vec4 forge_fragColor;
"""
SHADERTOY_MAIN = """
void main() {
    vec4 forge_c = vec4(0.0, 0.0, 0.0, 1.0);
    mainImage(forge_c, vec2(gl_FragCoord.x, forge_u.r.y - gl_FragCoord.y));
    forge_fragColor = vec4(forge_c.rgb, 1.0);
}
"""
# the same wrapper in WebGL2 GLSL, used as the reference renderer by verify.py
WEBGL_HEADER = """#version 300 es
precision highp float;
precision highp int;
uniform vec3 iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int iFrame;
uniform float iFrameRate;
uniform vec4 iMouse;
uniform vec4 iDate;
out vec4 forge_fragColor;
"""
WEBGL_MAIN = """
void main() {
    vec4 forge_c = vec4(0.0, 0.0, 0.0, 1.0);
    mainImage(forge_c, gl_FragCoord.xy);
    forge_fragColor = vec4(forge_c.rgb, 1.0);
}
"""
VS = """
@vertex fn vs(@builtin(vertex_index) i: u32) -> @builtin(position) vec4f {
    return vec4f(vec2f(f32(i % 2u), f32(i / 2u)) * 4. - 1., 0., 1.);
}
"""


class GLSLError(Exception):
    pass


@dataclass
class Converted:
    wgsl: str
    stage: str
    shadertoy: bool
    glsl450: str                      # the normalised GLSL the back end read
    backend: str                      # 'naga' (GLSL front end) or 'glslang' (via SPIR-V)
    notes: list[str] = field(default_factory=list)


def is_shadertoy(src: str) -> bool:
    body = _strip_comments(src)
    return bool(re.search(r"\bvoid\s+mainImage\s*\(", body)) and not re.search(r"\bvoid\s+main\s*\(", body)


def detect_stage(src: str, filename: str | None = None) -> str:
    if filename:
        ext = Path(filename).suffix.lower()
        for k, v in ((".vert", "vert"), (".vs", "vert"), (".frag", "frag"), (".fs", "frag"),
                     (".comp", "compute"), (".cs", "compute")):
            if ext == k:
                return v
    body = _strip_comments(src)
    if "local_size_x" in body:
        return "compute"
    if re.search(r"\bgl_Position\b", body):
        return "vert"
    return "frag"


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def webgl_reference_source(src: str) -> str:
    """The Shadertoy code wrapped for WebGL2, for rendering a reference image."""
    return WEBGL_HEADER + _strip_version_and_precision(src) + WEBGL_MAIN


def _strip_version_and_precision(src: str) -> str:
    src = re.sub(r"^\s*#\s*version[^\n]*\n?", "", src, flags=re.M)
    src = re.sub(r"^\s*precision\s+\w+\s+\w+\s*;[^\n]*\n?", "", src, flags=re.M)
    src = re.sub(r"^\s*#\s*extension[^\n]*\n?", "", src, flags=re.M)
    return src


def normalize(src: str, stage: str, shadertoy: bool) -> tuple[str, list[str]]:
    """Rewrite WebGL / Shadertoy GLSL into the GLSL 4.50 naga reads."""
    notes: list[str] = []
    m = re.search(r"^\s*#\s*version\s+(\d+)\s*(\w*)", src, flags=re.M)
    version = (m.group(1), m.group(2)) if m else None
    es100 = version is None and not shadertoy or (version and version[0] == "100")
    body = _strip_version_and_precision(src)
    header = ""
    body = re.sub(r"\b(highp|mediump|lowp)\s+", "", body)
    # naga reads a case that ends in `return x;` as falling through to the next label
    body = re.sub(r"(\breturn\b[^;]*;)(\s*)(?=(case\b|default\b))", r"\1 break;\2", body)

    if shadertoy:
        body = _split_samplers(body, notes, channel_mode=True)
        return "#version 450\n" + SHADERTOY_HEADER + body + SHADERTOY_MAIN, notes

    if es100:
        if stage == "frag" and re.search(r"\bgl_FragColor\b", body):
            body = re.sub(r"\bgl_FragColor\b", "forge_fragColor", body)
            header += "layout(location = 0) out vec4 forge_fragColor;\n"
        body = re.sub(r"\bvarying\b", "in" if stage == "frag" else "out", body)
        body = re.sub(r"\battribute\b", "in", body)
        body = re.sub(r"\btexture2D\s*\(", "texture(", body)
        body = re.sub(r"\btextureCube\s*\(", "texture(", body)
        body = re.sub(r"\btexture2DLod\s*\(", "textureLod(", body)

    binds = _Bindings()
    body = _split_samplers(body, notes, binds=binds)
    body = _block_loose_uniforms(body, notes, binds)
    body = _number_locations(body)
    return "#version 450\n" + header + body, notes


_LOOSE = re.compile(r"^([ \t]*)uniform\s+(\w+)\s+([^;{]+);", flags=re.M)
_BLOCK = re.compile(r"^([ \t]*)uniform\s+(\w+)\s*\{", flags=re.M)


class _Bindings:
    """Binding 0 is the gathered loose-uniform block (or Shadertoy's ForgeU);
    samplers and named blocks count up from 1 in source order."""

    def __init__(self):
        self.n = 1

    def next(self) -> int:
        b = self.n
        self.n += 1
        return b


def _split_samplers(body: str, notes: list[str], channel_mode=False, binds: _Bindings | None = None) -> str:
    binds = binds or _Bindings()
    names = []          # (name, combined sampler type)

    def rep(m):
        ind, ty, rest = m.group(1), m.group(2), m.group(3)
        if ty not in SAMPLER_TYPES:
            return m.group(0)
        out = []
        for name in [n.strip() for n in rest.split(",")]:
            names.append((name, ty))
            shadow = "Shadow" if "Shadow" in ty else ""
            out.append(f"{ind}layout(set = 0, binding = {binds.next()}) uniform {SAMPLER_TYPES[ty]} {name}_t;")
            out.append(f"{ind}layout(set = 0, binding = {binds.next()}) uniform sampler{shadow} {name}_s;")
        return "\n".join(out)

    body = _LOOSE.sub(rep, body)
    if channel_mode:
        used = sorted(set(re.findall(r"\biChannel([0-3])\b", body)))
        decls = []
        for c in used:
            name = f"iChannel{c}"
            names.append((name, "sampler2D"))
            decls.append(f"layout(set = 0, binding = {binds.next()}) uniform texture2D {name}_t;")
            decls.append(f"layout(set = 0, binding = {binds.next()}) uniform sampler {name}_s;")
        if used:
            notes.append(f"iChannel{','.join(used)} need textures from the host: "
                         f"texture/sampler pairs from binding 1 in channel order")
            body = "\n".join(decls) + "\n" + body
    for name, ty in names:
        # every sampling call names the sampler first: texture(s, uv) -> texture(sampler2D(s_t, s_s), uv)
        body = re.sub(rf"\b(texture\w*)\s*\(\s*{name}\b", rf"\1({ty}({name}_t, {name}_s)", body)
    left = [n for n, _ in names if re.search(rf"\b{n}\b(?!_[ts]\b)", body)]
    if left:
        notes.append(f"sampler(s) {', '.join(left)} are used outside a texture*() call "
                     f"(passed to a function?); naga needs separate texture and sampler there")
    return body


def _block_loose_uniforms(body: str, notes: list[str], binds: _Bindings) -> str:
    members = []

    def rep(m):
        for name in [n.strip() for n in m.group(3).split(",")]:
            members.append(f"    {m.group(2)} {name};")
        return ""
    body = _LOOSE.sub(lambda m: m.group(0) if m.group(2) in SAMPLER_TYPES else rep(m), body)
    body = _BLOCK.sub(lambda m: f"{m.group(1)}layout(std140, set = 0, binding = {binds.next()}) uniform {m.group(2)} {{", body)
    if members:
        notes.append("loose uniforms gathered into one std140 block at set 0, binding 0: "
                     + " ".join(x.strip() for x in members))
        body = "layout(std140, set = 0, binding = 0) uniform ForgeUniforms {\n" + "\n".join(members) + "\n};\n" + body
    return body


def _number_locations(body: str) -> str:
    counters = {"in": 0, "out": 0}

    def rep(m):
        q = m.group(2)
        n = counters[q]
        counters[q] += 1
        return f"{m.group(1)}layout(location = {n}) {q} "
    return re.sub(r"^(\s*)(in|out)\s+(?=\w+\s+\w+\s*;)", rep, body, flags=re.M)


def _naga(glsl: str, stage: str) -> str:
    exe = shutil.which("naga")
    if not exe:
        raise GLSLError("naga is required for GLSL input: cargo install naga-cli")
    with tempfile.TemporaryDirectory() as td:
        inp, out = Path(td) / "in.glsl", Path(td) / "out.wgsl"
        inp.write_text(glsl)
        r = subprocess.run([exe, "--input-kind", "glsl", "--shader-stage", stage, str(inp), str(out)],
                           capture_output=True, text=True)
        if r.returncode or not out.exists():
            msg = re.sub(r"\x1b\[[0-9;]*m", "", r.stderr or r.stdout)
            raise GLSLError(f"naga could not translate the GLSL:\n{msg.strip()[:3000]}")
        return out.read_text()


def _post(wgsl: str, shadertoy: bool, notes: list[str]) -> str:
    """Fix naga's output for browsers; for Shadertoy, rename the entry and add `vs`."""
    from .ast import Block, Call, ExprStmt, Fn, walk
    from .printer import to_wgsl
    from .scope import is_entry, resolve
    from .wgsl import parse
    m = parse(wgsl)
    resolve(m)
    # naga's GLSL reader turns barrier() into storage+workgroup+subgroup+texture barriers.
    # subgroupBarrier needs `enable subgroups` (Chrome rejects it otherwise) and GLSL's
    # barrier() only promises the workgroup one.
    has_rw_tex = "read_write" in wgsl and "texture_storage" in wgsl
    drop = {"subgroupBarrier"} | (set() if has_rw_tex else {"textureBarrier"})
    if "enable subgroups" in wgsl:
        drop.discard("subgroupBarrier")
    dropped = 0
    for n in walk(m):
        if isinstance(n, Block):
            keep = []
            for st in n.stmts:
                if isinstance(st, ExprStmt) and isinstance(st.expr, Call) and st.expr.callee.name in drop:
                    dropped += 1
                    continue
                keep.append(st)
            n.stmts = keep
    if dropped:
        notes.append(f"removed {dropped} subgroupBarrier/textureBarrier call(s) naga adds for GLSL barrier()")
    if shadertoy:
        for d in m.decls:
            if isinstance(d, Fn) and is_entry(d) and d.name == "main":
                d.name = "fs"
    out = to_wgsl(m, pretty=True)
    return out + VS if shadertoy else out


def _glslang(glsl: str, stage: str) -> str:
    """GLSL -> SPIR-V with glslang, then SPIR-V -> WGSL with naga."""
    gv = shutil.which("glslangValidator")
    exe = shutil.which("naga")
    if not gv or not exe:
        raise GLSLError("the glslang route needs glslangValidator (apt-get install glslang-tools) and naga")
    st = {"frag": "frag", "vert": "vert", "compute": "comp"}[stage]
    with tempfile.TemporaryDirectory() as td:
        inp, spv, out = Path(td) / f"in.{st}", Path(td) / "out.spv", Path(td) / "out.wgsl"
        inp.write_text(glsl)
        r = subprocess.run([gv, "-V", "--target-env", "vulkan1.1", "-S", st, str(inp), "-o", str(spv)],
                           capture_output=True, text=True)
        if r.returncode or not spv.exists():
            raise GLSLError(f"glslang could not compile the GLSL:\n{(r.stdout + r.stderr).strip()[:3000]}")
        r = subprocess.run([exe, str(spv), str(out)], capture_output=True, text=True)
        if r.returncode or not out.exists():
            msg = re.sub(r"\x1b\[[0-9;]*m", "", r.stderr or r.stdout)
            raise GLSLError(f"naga could not translate glslang's SPIR-V:\n{msg.strip()[:3000]}")
        return out.read_text()


def glsl_to_wgsl(src: str, stage: str | None = None, shadertoy: bool | None = None,
                 filename: str | None = None, backend: str = "auto") -> Converted:
    """Translate GLSL (Vulkan 4.50, WebGL ES 3.00/1.00, or Shadertoy) to WGSL.

    backend: 'naga' uses naga's GLSL front end (readable output); 'glslang' compiles to
    SPIR-V with glslang first (accepts more GLSL, mangled names); 'auto' tries naga and
    falls back to glslang when naga rejects the source."""
    if shadertoy is None:
        shadertoy = is_shadertoy(src)
    stage = "frag" if shadertoy else (stage or detect_stage(src, filename))
    glsl450, notes = normalize(src, stage, shadertoy)
    used = backend
    if backend == "glslang":
        wgsl = _glslang(glsl450, stage)
    else:
        try:
            wgsl = _naga(glsl450, stage)
            used = "naga"
        except GLSLError as first:
            if backend == "naga" or not shutil.which("glslangValidator"):
                raise
            wgsl = _glslang(glsl450, stage)
            used = "glslang"
            notes.append("naga's GLSL front end refused this source ("
                         + str(first).splitlines()[1 if len(str(first).splitlines()) > 1 else 0][:120]
                         + "); translated through glslang and SPIR-V instead")
    wgsl = _post(wgsl, shadertoy, notes)
    return Converted(wgsl, stage, shadertoy, glsl450, used, notes)
