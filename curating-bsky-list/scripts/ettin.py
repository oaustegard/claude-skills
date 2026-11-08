"""Ettin-17m sentence embeddings on CPU: onnxruntime + tokenizers, no torch.

The model is Oskar's, served from oaustegard.github.io (bsky/embedders/models/ettin/). It is downloaded on first
use into a cache directory and never bundled with the skill. Pooling happens inside the ONNX graph (the browser
engine's `pool` + `dense` steps); this side only truncates to 128 tokens and L2-normalises, as
oaustegard.github.io scripts/answer-search/refresh.py does.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

FILES = ("model.onnx", "tokenizer.json", "meta.json")
SOURCES = (
    "https://raw.githubusercontent.com/oaustegard/oaustegard.github.io/main/bsky/embedders/models/ettin/",
    "https://austegard.com/bsky/embedders/models/ettin/",
)
MAX_SEQ = 128
DIM = 768


def cache_dir() -> Path:
    base = os.environ.get("CURATE_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "curating-bsky-list")
    return Path(base) / "ettin"


def fetch_model(dest: Path | None = None) -> Path:
    """Download the three model files once; later calls return the cached directory."""
    dest = dest or cache_dir()
    dest.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = dest / name
        if target.exists() and target.stat().st_size > 0:
            continue
        last = None
        for base in SOURCES:
            try:
                req = urllib.request.Request(base + name, headers={"User-Agent": "curating-bsky-list"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                if name == "model.onnx" and len(data) < 1_000_000:
                    raise OSError(f"{base}{name} is {len(data)} bytes, not a model")
                tmp = target.with_suffix(target.suffix + ".part")
                tmp.write_bytes(data)
                tmp.replace(target)
                last = None
                break
            except OSError as e:   # URLError and HTTPError are OSErrors
                last = e
        if last is not None:
            raise RuntimeError(f"could not download {name}: {last}")
    return dest


class Ettin:
    def __init__(self, d: Path | None = None, threads: int | None = None):
        import numpy as np  # noqa: F401  (imported here so the module loads without deps)
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = d or fetch_model()
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads or min(4, os.cpu_count() or 1)
        self.sess = ort.InferenceSession(str(d / "model.onnx"), so, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.out = self.sess.get_outputs()[0].name
        self.prefix = (json.loads((d / "meta.json").read_text()).get("prompts") or {}).get("document", "")

    def embed(self, texts, batch: int = 64):
        """Unit vectors, one row per text, in input order."""
        import numpy as np

        enc = []
        for t in texts:
            ids = self.tok.encode(self.prefix + t).ids
            enc.append(ids if len(ids) <= MAX_SEQ else ids[:MAX_SEQ - 1] + ids[-1:])
        X = np.empty((len(texts), DIM), np.float32)
        order = np.argsort([len(e) for e in enc], kind="stable")
        for s in range(0, len(order), batch):
            rows = order[s:s + batch]
            S = max(len(enc[r]) for r in rows)
            ids = np.zeros((len(rows), S), np.int64)
            att = np.zeros((len(rows), S), np.int64)
            for b, r in enumerate(rows):
                ids[b, :len(enc[r])] = enc[r]
                att[b, :len(enc[r])] = 1
            v = self.sess.run([self.out], {"input_ids": ids, "attention_mask": att})[0]
            X[rows] = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
        return X
