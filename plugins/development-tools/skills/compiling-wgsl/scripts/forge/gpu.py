"""Python side of harness/gpu.mjs: batch WGSL jobs through headless Chromium WebGPU."""
from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

HARNESS = Path(__file__).resolve().parents[1] / "harness" / "gpu.mjs"


def run_jobs(jobs: list[dict], timeout=1800) -> dict:
    with tempfile.TemporaryDirectory() as td:
        jp, op = Path(td) / "jobs.json", Path(td) / "out.json"
        jp.write_text(json.dumps(jobs))
        r = subprocess.run(["node", str(HARNESS), str(jp), str(op)], capture_output=True,
                           text=True, timeout=timeout)
        if not op.exists():
            raise RuntimeError(f"harness failed: {r.stderr[-2000:]}")
        res = json.loads(op.read_text())
    for v in res.values():
        if "rgba" in v:
            v["rgba"] = base64.b64decode(v["rgba"])
        if "buffers" in v:
            v["buffers"] = {k: base64.b64decode(b) for k, b in v["buffers"].items()}
    return res


def image(res: dict, width: int, height: int) -> np.ndarray:
    return np.frombuffer(res["rgba"], np.uint8).reshape(height, width, 4)


def over_white(rgba: np.ndarray, premultiplied: bool) -> np.ndarray:
    """Composite onto white; returns float RGB in 0..255."""
    a = rgba[..., 3:4].astype(np.float64) / 255
    c = rgba[..., :3].astype(np.float64)
    if premultiplied:
        return c + (1 - a) * 255
    return c * a + (1 - a) * 255


def save_png(path, rgb_or_rgba: np.ndarray):
    from PIL import Image
    arr = np.clip(np.rint(rgb_or_rgba), 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path)
