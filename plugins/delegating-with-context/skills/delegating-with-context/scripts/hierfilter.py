"""Hierarchical variant of the Jev context filter, after DecisionRAG (arXiv 2610.35868).

Level 1 scores segments of the session: a segment starts at each real user
message, and a long run is cut every SEG_MAX_CHUNKS chunks. Each segment is
shown to Jev as a short digest (its user/assistant text and tool calls,
clipped), so a whole session fits one window. Level 2 scores, at a higher view
scale, only the chunks inside the segments level 1 kept. A pruned segment's
chunks are never scored (score 0), as in the paper, where "a branch dropped at
one level is not revisited for this query". Selection into the budget is the
flat filter's `select`, so the two differ only in which chunks get a score and
at what fidelity.

Keep rule at level 1: the top SEG_KEEP_FRAC of segments by score, never fewer
than MIN_SEGS (the paper's per-level budget k). An absolute threshold kept every
segment on a single-topic session, where all scored >= 0.57.
"""
from __future__ import annotations

import concurrent.futures as cf
import math
import json
import time

import jevfilter as jf

SEG_MAX_CHUNKS = 8
SEG_DIGEST_CHARS = 1_400
SEG_KEEP_FRAC = 0.40
MIN_SEGS = 3


def segments(chunks: list[dict]) -> list[list[dict]]:
    segs, cur = [], []
    for c in chunks:
        if cur and (c["kind"] == "user" or len(cur) >= SEG_MAX_CHUNKS):
            segs.append(cur); cur = []
        cur.append(c)
    if cur:
        segs.append(cur)
    return segs


def digest(seg: list[dict], chars: int = SEG_DIGEST_CHARS) -> dict:
    lines = []
    for c in seg:
        if c["kind"] == "tool":
            lines.append(f"c{c['id']} tool {c.get('tool', '?')}: {jf.clip(c.get('input'), 140)}"
                         f" -> {jf.clip(c.get('result'), 220)}")
        else:
            lines.append(f"c{c['id']} {c['kind']}: {jf.clip(c.get('text'), 320)}")
    return {"chunk_ids": f"c{seg[0]['id']}-c{seg[-1]['id']}", "digest": jf.clip("\n".join(lines), chars)}


def _question(kind: str, k: str) -> dict:
    what = "span of the session" if kind == "segments" else "transcript chunk"
    return {"type": "noul",
            "instructions": f"Does `{kind}.{k}` (a {what}) contain information that an assistant "
                            f"given `task` would need or benefit from to do that task?"}


def _pack(g: dict, kind: str, items: dict[str, dict]) -> list[dict]:
    """Pack {key: view} into windows under jf.STATE_TOKENS, each carrying the global state g."""
    room = jf.STATE_TOKENS - jf.tokens(json.dumps(g))
    out, cur, used = [], {}, 0
    for k, v in items.items():
        t = jf.tokens(json.dumps(v)) + 8
        if cur and used + t > room:
            out.append(cur); cur, used = {}, 0
        cur[k] = v; used += t
    if cur:
        out.append(cur)
    return [{"kind": kind, "state": {**g, kind: w}, "questions": {k: _question(kind, k) for k in w}} for w in out]


def _score(w: dict, depth: int = 0) -> tuple[dict, int, int, int]:
    """jf._score_window generalised to any item key; bisects on a WAF block."""
    kind = w["kind"]
    try:
        ans, u = jf._call(w["state"], w["questions"])
        return {int(k[1:]): v for k, v in ans.items()}, u, 1, 0
    except jf.Blocked:
        keys = list(w["state"][kind])
        if len(keys) == 1 or depth >= 6:
            return {int(k[1:]): jf.BLOCKED_SCORE for k in keys}, 0, 1, len(keys)
        out, used, calls, blocked = {}, 0, 1, 0
        for half in (keys[: len(keys) // 2], keys[len(keys) // 2:]):
            sub = {"kind": kind, "state": {**w["state"], kind: {k: w["state"][kind][k] for k in half}},
                   "questions": {k: w["questions"][k] for k in half}}
            s, u, c, b = _score(sub, depth + 1)
            out.update(s); used += u; calls += c; blocked += b
        return out, used, calls, blocked


def _run(ws: list[dict]) -> tuple[dict, int, int, int]:
    scores, used, calls, blocked = {}, 0, 0, 0
    with cf.ThreadPoolExecutor(jf.CONCURRENCY) as ex:
        for s, u, c, b in ex.map(_score, ws):
            scores.update(s); used += u; calls += c; blocked += b
    return scores, used, calls, blocked


def score(task: str, chunks: list[dict], scale: float = 4.0) -> tuple[dict[int, float], dict]:
    t0 = time.time()
    g = jf._global_state(task, chunks)
    segs = segments(chunks)
    w1 = _pack(g, "segments", {f"s{i}": digest(s) for i, s in enumerate(segs)})
    s1, u1, c1, b1 = _run(w1)
    ranked = sorted(s1, key=lambda i: -s1[i])
    kept = set(ranked[: max(MIN_SEGS, math.ceil(SEG_KEEP_FRAC * len(segs)))])
    cand = [c for i in sorted(kept) for c in segs[i]]
    w2 = _pack(g, "chunks", {f"c{c['id']}": jf.view(c, scale) for c in cand})
    s2, u2, c2, b2 = _run(w2)
    scores = {c["id"]: 0.0 for c in chunks}
    scores.update(s2)
    return scores, {"segments": len(segs), "segments_kept": sorted(kept),
                    "segment_scores": {str(k): round(v, 3) for k, v in s1.items()},
                    "candidates": len(cand), "windows_l1": len(w1), "windows_l2": len(w2),
                    "windows": len(w1) + len(w2),
                    "calls": c1 + c2, "blocked_chunks": b1 + b2, "jev_input_tokens": u1 + u2,
                    "seconds": round(time.time() - t0, 2)}


def build_context(task: str, chunks: list[dict], budget_tokens: int = 20_000,
                  scale: float = 4.0) -> tuple[str, dict]:
    scores, stats = score(task, chunks, scale)
    keep = jf.select(chunks, scores, budget_tokens)
    kept = [c for c in chunks if c["id"] in keep]
    body = "\n\n".join(jf.render(c, keep[c["id"]]) for c in kept)
    header = (f"Context from the parent session, selected for this task: {len(kept)} of {len(chunks)} "
              f"transcript chunks (~{jf.tokens(body)} tokens; ids in brackets). Chunks not shown were judged "
              f"irrelevant; if something you need is missing, say so in your reply.")
    stats.update({"kept_ids": [c["id"] for c in kept], "context_tokens": jf.tokens(body), "scores": scores})
    return header + "\n\n" + body, stats
