#!/usr/bin/env python3
"""snap — resolve free-form labels onto a closed vocabulary by embedding similarity.

The deterministic half of hallucinate-and-snap. The model writes labels in the
vocabulary's register; this snaps each one to the nearest legal value, so the output
is always in the vocabulary no matter what the model wrote.

    # 1. index the vocabulary once (fast; re-run only when the vocabulary changes)
    python3 snap.py build --vocab categories.txt --out .snap-index.pkl

    # 2. snap the model's labels
    python3 snap.py snap --index .snap-index.pkl --labels invented.txt --k 3

    # long items: also snap the items themselves and interleave both rankings
    python3 snap.py snap --index .snap-index.pkl --labels invented.txt \
        --items summaries.txt --union --k 5

Files are one entry per line. Output is JSON on stdout.

Backends: `tfidf` (default; sklearn only, no download) and `minilm` (needs
sentence-transformers and a ~90 MB model). On WANDS, minilm scored 0.564 acc@1 to
tfidf's 0.528; where items literally contain their own label words, tfidf wins.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys

import numpy as np


def _norm(a):
    return a / np.clip(np.linalg.norm(a, axis=1, keepdims=True), 1e-9, None)


class Index:
    def __init__(self, labels, backend="tfidf", model_name="all-MiniLM-L6-v2"):
        self.labels = [l for l in (x.strip() for x in labels) if l]
        if not self.labels:
            raise SystemExit("snap: vocabulary is empty")
        self.backend, self.model_name = backend, model_name
        self._enc = None
        self.matrix = self._fit()

    def _fit(self):
        if self.backend == "minilm":
            from sentence_transformers import SentenceTransformer
            self._enc = SentenceTransformer(self.model_name)
            return _norm(np.asarray(self._enc.encode(self.labels, batch_size=128,
                                                     show_progress_bar=False)))
        if self.backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            # char_wb: an invented label differs from the real one by morphology far
            # more often than by meaning ("Turquoise Pillows" / "Accent Pillows").
            self._enc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
            return _norm(self._enc.fit_transform(self.labels).toarray())
        raise SystemExit(f"snap: unknown backend {self.backend!r}")

    def encode(self, texts):
        safe = [t if t and t.strip() else " " for t in texts]
        if self.backend == "minilm":
            return _norm(np.asarray(self._enc.encode(safe, batch_size=128,
                                                     show_progress_bar=False)))
        return _norm(self._enc.transform(safe).toarray())

    def rank(self, texts, k=3):
        sims = self.encode(texts) @ self.matrix.T
        order = np.argsort(-sims, axis=1)[:, :k]
        return [[(self.labels[j], round(float(sims[i, j]), 4)) for j in row]
                for i, row in enumerate(order)]


def interleave(a, b, k):
    """Round-robin two rankings, deduped. Not a rescore: a direct-snap cosine and a
    hallucination-snap cosine are not on a common scale."""
    seen, out = set(), []
    for i in range(max(len(a), len(b))):
        for src in (a, b):
            if i < len(src) and src[i][0] not in seen:
                seen.add(src[i][0])
                out.append(src[i])
                if len(out) >= k:
                    return out
    return out


def _lines(path):
    with open(path, encoding="utf-8") as fh:
        return [l.rstrip("\n") for l in fh]


def main(argv=None):
    p = argparse.ArgumentParser(prog="snap", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="index a vocabulary file")
    b.add_argument("--vocab", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--backend", default="tfidf", choices=["tfidf", "minilm"])

    s = sub.add_parser("snap", help="snap free-form labels onto the vocabulary")
    s.add_argument("--index", required=True)
    s.add_argument("--labels", required=True, help="the model's invented labels, one per line")
    s.add_argument("--items", help="the original items, for --union")
    s.add_argument("--union", action="store_true",
                   help="also snap the items directly and interleave; use for long items")
    s.add_argument("--k", type=int, default=3)
    s.add_argument("--min-score", type=float, default=0.0,
                   help="below this, report null rather than a guess")

    a = p.parse_args(argv)

    if a.cmd == "build":
        idx = Index(_lines(a.vocab), backend=a.backend)
        with open(a.out, "wb") as fh:
            pickle.dump(idx, fh)
        print(json.dumps({"labels": len(idx.labels), "backend": idx.backend, "index": a.out}))
        return 0

    with open(a.index, "rb") as fh:
        idx = pickle.load(fh)
    labels = _lines(a.labels)
    ranked = idx.rank(labels, k=max(1, a.k))

    if a.union:
        if not a.items:
            raise SystemExit("snap: --union needs --items")
        items = _lines(a.items)
        if len(items) != len(labels):
            raise SystemExit(f"snap: {len(items)} items vs {len(labels)} labels — "
                             "they must correspond line for line")
        direct = idx.rank(items, k=max(1, a.k))
        ranked = [interleave(d, h, a.k) for d, h in zip(direct, ranked)]

    out = []
    for written, r in zip(labels, ranked):
        top, score = r[0]
        out.append({"written": written,
                    "label": top if score >= a.min_score else None,
                    "score": score,
                    "alternatives": r})
    print(json.dumps(out, indent=1, ensure_ascii=False))
    unresolved = sum(1 for o in out if o["label"] is None)
    if unresolved:
        print(f"snap: {unresolved}/{len(out)} below --min-score, reported as null",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
