#!/usr/bin/env python3
"""Run every check in verify.py over the bundled fixtures (about 1 minute).

    python3 selftest.py

Fixtures in selftest/: four Shadertoy-style shaders (plasma, raymarcher, fbm noise,
switch/out-params/matrices), WebGL 1 and 2 fragment shaders, a WebGL 2 vertex shader,
two GLSL compute shaders (one needs the glslang route), an SVG exercising every path
command (also checked as a self-painting shader), and naga's collatz compute test. All fixtures except collatz.wgsl
(gfx-rs/wgpu, MIT OR Apache-2.0) were written for this skill.
Exits 1 if any check fails; prints which tools were missing (those checks are skipped).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "selftest"
RUNS = ([("glsl", f) for f in sorted(FIX.glob("*.glsl"))]
        + [("glsl", f) for f in sorted(FIX.glob("*.frag")) + sorted(FIX.glob("*.vert")) + sorted(FIX.glob("*.comp"))]
        + [("svg", FIX / "paths.svg"), ("minify", FIX / "collatz.wgsl")])
EXTRA = {("svg", "paths.svg"): ["--paint-in", "3"]}   # also the self-painting checks

missing = [t for t in ("naga", "glslangValidator", "node") if not shutil.which(t)]
if missing:
    print(f"missing tools: {', '.join(missing)} (their checks are skipped or the run fails)")
bad = 0
for cmd, f in RUNS:
    r = subprocess.run([sys.executable, str(HERE / "verify.py"), cmd, str(f)] + EXTRA.get((cmd, f.name), []),
                       capture_output=True, text=True)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("ok", "FAIL", "skip"))]
    fails = [ln for ln in lines if ln.startswith("FAIL")]
    ok = r.returncode == 0
    bad += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {cmd:<6} {f.name:<18} {sum(ln.startswith('ok') for ln in lines)} checks passed"
          + (f"; {'; '.join(fails)[:300]}" if fails else "") + (f"\n{r.stderr[-800:]}" if r.returncode and not fails else ""))
print("all passed" if not bad else f"{bad} fixture(s) failed")
sys.exit(1 if bad else 0)
