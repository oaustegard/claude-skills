#!/usr/bin/env python3
"""Lexical KB searcher — pure stdlib BM25 over a portable, embedding-free index.

This is the runtime half of a `.skill` lexical knowledgebase bundle. It ships
*inside* the bundle alongside `index.json` and `chunks.jsonl`, so it has zero
third-party dependencies: any agent that can run `python3` can query the KB
with no `pip install`, no model download, no network.

The semantic layer lives in the calling agent, not here. There is no embedding
model to bridge the query<->document vocabulary gap; the agent does that by
expanding the query into `--core` (essential terms) and `--expand` (synonyms,
morphological variants, acronym expansions, adjacent concepts) before calling.
When no expansion is supplied, `--rm3` runs corpus-driven pseudo-relevance
feedback as a weaker, model-free fallback.

Index format (see build_lexkb.py for the writer):
  index.json   {params:{k1,b}, N, avgdl, doclen:[...], df:{term:df},
                postings:{term:[[doc_idx, tf], ...]}}
  chunks.jsonl one JSON object per line: {id, text, meta}; line number == doc_idx

The tokenizer defined here is the single source of truth: build_lexkb.py imports
it so the index and the query are tokenized identically.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

# --------------------------------------------------------------------------- #
# Tokenizer — single source of truth (builder imports this).
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase, split on Unicode word boundaries. No stemming, no stopwords —
    the agent supplies morphological variants in --expand."""
    return _TOKEN_RE.findall(text.lower())


# --------------------------------------------------------------------------- #
# Index loading
# --------------------------------------------------------------------------- #


class Index:
    def __init__(self, index_dir: Path):
        self.dir = index_dir
        with (index_dir / "index.json").open(encoding="utf-8") as fh:
            idx = json.load(fh)
        self.k1 = float(idx["params"]["k1"])
        self.b = float(idx["params"]["b"])
        self.N = int(idx["N"])
        self.avgdl = float(idx["avgdl"])
        self.doclen = idx["doclen"]
        self.df = idx["df"]
        self.postings = idx["postings"]
        self._idf_cache: dict[str, float] = {}
        # chunks.jsonl loaded lazily on demand
        self._chunks: list[dict] | None = None

    @property
    def chunks(self) -> list[dict]:
        if self._chunks is None:
            self._chunks = []
            with (self.dir / "chunks.jsonl").open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        self._chunks.append(json.loads(line))
        return self._chunks

    def idf(self, term: str) -> float:
        """Robust BM25 idf (always positive — Lucene/bm25+ variant)."""
        if term not in self._idf_cache:
            df = self.df.get(term, 0)
            self._idf_cache[term] = math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))
        return self._idf_cache[term]

    def _term_doc_score(self, term: str, doc_idx: int, tf: int) -> float:
        dl = self.doclen[doc_idx]
        denom = tf + self.k1 * (1.0 - self.b + self.b * dl / self.avgdl)
        return self.idf(term) * (tf * (self.k1 + 1.0)) / denom

    def score(self, weighted_terms: dict[str, float]) -> dict[int, float]:
        """Score every candidate doc against {term: weight}. Returns {doc_idx: score}."""
        scores: dict[int, float] = defaultdict(float)
        for term, weight in weighted_terms.items():
            plist = self.postings.get(term)
            if not plist:
                continue
            for doc_idx, tf in plist:
                scores[doc_idx] += weight * self._term_doc_score(term, doc_idx, tf)
        return scores


# --------------------------------------------------------------------------- #
# RM3 pseudo-relevance feedback (model-free fallback expansion)
# --------------------------------------------------------------------------- #


def rm3_expand(
    index: Index,
    seed_terms: dict[str, float],
    *,
    n_docs: int = 10,
    n_terms: int = 15,
    alpha: float = 0.5,
) -> dict[str, float]:
    """Two-pass RM3. First pass ranks with seed_terms; harvest characteristic
    terms from the top n_docs; interpolate back with the original query.

    Returns a new weighted-term dict (original terms weighted alpha, feedback
    terms weighted (1-alpha)*normalized). Weaker than agent expansion and prone
    to drift when the first pass is off-topic — strictly a no-agent fallback."""
    first = index.score(seed_terms)
    if not first:
        return seed_terms
    top = sorted(first.items(), key=lambda kv: kv[1], reverse=True)[:n_docs]
    total = sum(s for _, s in top) or 1.0

    # Feedback term mass: relevance-weighted term frequency over the top docs.
    fb: dict[str, float] = defaultdict(float)
    for doc_idx, doc_score in top:
        toks = tokenize(index.chunks[doc_idx]["text"])
        if not toks:
            continue
        w = doc_score / total
        tf_local: dict[str, int] = defaultdict(int)
        for t in toks:
            tf_local[t] += 1
        inv_len = 1.0 / len(toks)
        for t, c in tf_local.items():
            fb[t] += w * c * inv_len

    # Keep the most characteristic feedback terms, drop ones already in the seed.
    ranked = sorted(
        ((t, m) for t, m in fb.items() if t not in seed_terms),
        key=lambda kv: kv[1],
        reverse=True,
    )[:n_terms]
    fb_total = sum(m for _, m in ranked) or 1.0

    merged: dict[str, float] = {t: alpha * w for t, w in seed_terms.items()}
    for t, m in ranked:
        merged[t] = merged.get(t, 0.0) + (1.0 - alpha) * (m / fb_total)
    return merged


# --------------------------------------------------------------------------- #
# Metadata filtering
# --------------------------------------------------------------------------- #


def _parse_filter(expr: str) -> tuple[str, str, str]:
    """`key=value`, `key!=value`, `key>value`, `key<value`, `key~substr`."""
    for op in ("!=", ">=", "<=", "~", "=", ">", "<"):
        if op in expr:
            key, val = expr.split(op, 1)
            return key.strip(), op, val.strip()
    raise ValueError(f"unparseable filter: {expr!r}")


def _match(meta: dict, key: str, op: str, val: str) -> bool:
    actual = meta.get(key)
    if actual is None:
        return False
    a = str(actual)
    if op == "=":
        return a == val
    if op == "!=":
        return a != val
    if op == "~":
        return val.lower() in a.lower()
    # ordered comparisons: numeric if both parse, else lexicographic (ISO dates work)
    try:
        af, vf = float(a), float(val)
        if op in (">", ">="):
            return af > vf if op == ">" else af >= vf
        return af < vf if op == "<" else af <= vf
    except ValueError:
        if op in (">", ">="):
            return a > val if op == ">" else a >= val
        return a < val if op == "<" else a <= val


def apply_filters(index: Index, doc_idx: int, filters: list[tuple[str, str, str]]) -> bool:
    if not filters:
        return True
    meta = index.chunks[doc_idx].get("meta", {})
    return all(_match(meta, k, op, v) for k, op, v in filters)


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #


def build_query(
    core: list[str],
    expand: list[str],
    w_core: float,
    w_expand: float,
    backstop: list[str] | None = None,
    w_backstop: float = 0.25,
) -> dict[str, float]:
    """Tokenize term groups into one weighted-term dict; a term's weight is the
    max across the groups it appears in.

    `backstop` carries the user's *original* query terms at a low floor weight so
    expansion is strictly additive — curated synonyms can lift a result but can
    never drop a doc the literal question would have matched. (Diagnosed on the
    tiny corpus: substitutive expansion sent a gold doc to score 0.)"""
    q: dict[str, float] = {}
    groups = [(expand, w_expand), (backstop or [], w_backstop), (core, w_core)]
    for group, w in groups:
        for phrase in group:
            for tok in tokenize(phrase):
                q[tok] = max(q.get(tok, 0.0), w)
    return q


def search(
    index: Index,
    query: dict[str, float],
    *,
    k: int = 5,
    filters: list[tuple[str, str, str]] | None = None,
    use_rm3: bool = False,
    rm3_docs: int = 10,
    rm3_terms: int = 15,
    rm3_alpha: float = 0.5,
) -> list[dict]:
    if use_rm3:
        query = rm3_expand(
            index, query, n_docs=rm3_docs, n_terms=rm3_terms, alpha=rm3_alpha
        )
    scores = index.score(query)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out: list[dict] = []
    for doc_idx, sc in ranked:
        if not apply_filters(index, doc_idx, filters or []):
            continue
        chunk = index.chunks[doc_idx]
        out.append(
            {
                "id": chunk.get("id"),
                "score": round(sc, 6),
                "text": chunk["text"],
                "meta": chunk.get("meta", {}),
            }
        )
        if len(out) >= k:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default=str(Path(__file__).resolve().parent),
                    help="bundle dir holding index.json + chunks.jsonl (default: script dir)")
    ap.add_argument("--query", default="", help="raw query text (fallback / RM3 seed)")
    ap.add_argument("--core", action="append", default=[], help="essential term/phrase (repeatable)")
    ap.add_argument("--expand", action="append", default=[], help="expansion term/phrase (repeatable)")
    ap.add_argument("--w-core", type=float, default=1.0)
    ap.add_argument("--w-expand", type=float, default=0.4)
    ap.add_argument("--w-query", type=float, default=0.25, help="floor weight for --query terms when expanding")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--filter", action="append", default=[], help="meta filter, e.g. section=blog or date>=2025 (repeatable)")
    ap.add_argument("--rm3", action="store_true", help="run pseudo-relevance feedback (no-agent fallback)")
    ap.add_argument("--rm3-docs", type=int, default=10)
    ap.add_argument("--rm3-terms", type=int, default=15)
    ap.add_argument("--rm3-alpha", type=float, default=0.5)
    ap.add_argument("--text-chars", type=int, default=0, help="truncate hit text to N chars in output (0 = full)")
    args = ap.parse_args(argv)

    index = Index(Path(args.index))

    core = list(args.core)
    backstop: list[str] = []
    if args.query:
        if not core and not args.expand:
            core = [args.query]  # raw-only: the query IS the core
        else:
            backstop = [args.query]  # additive floor under core+expand

    query = build_query(core, args.expand, args.w_core, args.w_expand,
                        backstop, args.w_query)
    if not query:
        print(json.dumps({"error": "empty query: pass --core/--expand or --query"}))
        return 2

    hits = search(
        index, query, k=args.k,
        filters=[_parse_filter(f) for f in args.filter],
        use_rm3=args.rm3, rm3_docs=args.rm3_docs,
        rm3_terms=args.rm3_terms, rm3_alpha=args.rm3_alpha,
    )
    if args.text_chars > 0:
        for h in hits:
            if len(h["text"]) > args.text_chars:
                h["text"] = h["text"][: args.text_chars] + "…"
    print(json.dumps({"hits": hits}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
