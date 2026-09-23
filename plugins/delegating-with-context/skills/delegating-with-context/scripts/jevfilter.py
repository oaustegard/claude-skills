"""Select the transcript chunks a delegated task needs, using Jev.

The transcript is paged into windows that fit Jev's request limits (32k tokens
for state plus the longest question, 64k for state plus all questions). Every
window also carries the task, all user messages (clipped) and a one-line index
of the whole session, so a chunk is judged with the session's shape in view.
Each chunk in a window gets one Noul question. Chunks are then ranked by score
and packed into the subagent's token budget; user messages are always kept.

Transport: the Cloudflare AI Gateway (CF_ACCOUNT_ID, CF_GATEWAY_ID,
CF_API_TOKEN; the TypeSafe key is stored in the gateway) or TypeSafe directly
(TYPESAFE_API_KEY).

A failed window raises FilterError. Callers decide what to fall back to; the
hook passes the original prompt through unchanged.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import time
import urllib.error
import urllib.request

CHARS_PER_TOKEN = 3.3        # conservative; Jev reported ~3.8 on transcript text
STATE_TOKENS = 27_000        # per window, under the 32k state + longest-question limit
GLOBAL_TOKENS = 5_000        # task + user messages + index, repeated in every window
MAX_CHUNK_TOKENS = 6_000     # a single kept chunk is clipped to this in the output
SCORE_FLOOR = 0.15           # never pad the budget with chunks below this
CONCURRENCY = 2              # METHODS.md: the CF AI Gateway throttles hard; start at 2


class FilterError(RuntimeError):
    pass


class Blocked(FilterError):
    """TypeSafe's edge WAF rejected the request content. Deterministic: retrying the
    same bytes never helps. Through the AI Gateway it arrives as HTTP 402 'Payment
    error from model using BYOK' wrapping a Cloudflare 'Sorry, you have been blocked'
    page (diagnosed 2026-09-23 on a transcript full of shell commands)."""


def tokens(s: str) -> int:
    return int(len(s) / CHARS_PER_TOKEN) + 1


def clip(s: str | None, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: int(n * 0.75)] + " […] " + s[-int(n * 0.25):]


def view(c: dict, scale: float = 1.0) -> dict:
    """Condensed chunk for Jev's state."""
    v = {"kind": c["kind"]}
    if c["kind"] == "tool":
        v["tool"] = c.get("tool", "?")
        v["input"] = clip(c.get("input"), int(300 * scale))
        v["result"] = clip(c.get("result"), int(900 * scale))
    else:
        v["text"] = clip(c.get("text"), int(1500 * scale))
    return v


def render(c: dict, max_chars: int = int(MAX_CHUNK_TOKENS * CHARS_PER_TOKEN)) -> str:
    """Full-fidelity chunk text as the subagent receives it."""
    if c["kind"] == "tool":
        body = f"TOOL {c.get('tool', '?')} input: {c.get('input', '')}\nresult: {c.get('result', '')}"
    else:
        body = {"user": "USER: ", "harness": "HARNESS: "}.get(c["kind"], "ASSISTANT: ") + c.get("text", "")
    return f"[{c['id']}] " + clip(body, max_chars)


def _global_state(task: str, chunks: list[dict]) -> dict:
    users = [clip(c["text"], 400) for c in chunks if c["kind"] == "user"]
    index = [f"c{c['id']} {c['kind']}{' ' + c.get('tool', '') if c['kind'] == 'tool' else ''}: "
             + clip((c.get("text") or c.get("input") or "").replace("\n", " "), 70) for c in chunks]
    g = {"task": task, "user_messages": users, "session_index": index}
    while tokens(json.dumps(g)) > GLOBAL_TOKENS and len(g["session_index"]) > 0:
        g["session_index"] = [clip(x, max(20, len(x) // 2)) for x in g["session_index"]]
        if tokens(json.dumps(g)) > GLOBAL_TOKENS:
            g["user_messages"] = [clip(u, 150) for u in g["user_messages"]]
        if all(len(x) <= 24 for x in g["session_index"]):
            break
    return g


def _question(cid: int) -> dict:
    return {"type": "noul",
            "instructions": f"Does `chunks.c{cid}` contain information that an assistant given `task` "
                            f"would need or benefit from to do that task?"}


def windows(task: str, chunks: list[dict], scale: float = 1.0) -> list[dict]:
    """Pack condensed chunks into states that fit STATE_TOKENS."""
    g = _global_state(task, chunks)
    room = STATE_TOKENS - tokens(json.dumps(g))
    out, cur, used = [], {}, 0
    for c in chunks:
        v = view(c, scale)
        t = tokens(json.dumps(v)) + 8
        if cur and used + t > room:
            out.append(cur); cur, used = {}, 0
        cur[f"c{c['id']}"] = v; used += t
    if cur:
        out.append(cur)
    return [{"state": {**g, "chunks": w}, "questions": {k: _question(int(k[1:])) for k in w}} for w in out]


def _call(state: dict, questions: dict, timeout: int = 60) -> tuple[dict, int]:
    if os.environ.get("CF_API_TOKEN") and os.environ.get("CF_ACCOUNT_ID"):
        url = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CF_ACCOUNT_ID']}/ai/run"
        body = {"model": "typesafe/jev", "input": {"state": state, "questions": questions}}
        headers = {"Authorization": f"Bearer {os.environ['CF_API_TOKEN']}", "Content-Type": "application/json"}
        if os.environ.get("CF_GATEWAY_ID"):
            headers["cf-aig-gateway-id"] = os.environ["CF_GATEWAY_ID"]
        unwrap = lambda r: r["result"]["result"]
    elif os.environ.get("TYPESAFE_API_KEY"):
        url = "https://api.typesafe.ai/v1/systemone"
        body = {"model": "jev-latest", "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}", "Content-Type": "application/json"}
        unwrap = lambda r: r
    else:
        raise FilterError("no Jev transport: set CF_ACCOUNT_ID+CF_API_TOKEN(+CF_GATEWAY_ID) or TYPESAFE_API_KEY")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    last = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = unwrap(json.load(r))
            return {k: a["noul"] for k, a in res["answers"].items()}, res.get("usage", {}).get("input_tokens", 0)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if "you have been blocked" in body or "Attention Required" in body:
                raise Blocked(f"HTTP {e.code}: request content blocked by the provider's WAF")
            last = f"HTTP {e.code}: {body[:300]}"
            # the gateway's own rate limit (code 2003) needs real backoff; honour Retry-After
            wait = float(e.headers.get("Retry-After") or 0) or min(30, 2 * 2 ** attempt)
            time.sleep(wait)
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
            last = f"{type(e).__name__}: {str(e)[:200]}"
            time.sleep(1.5 * 2 ** attempt)
    raise FilterError(f"Jev call failed after retries: {last}")


BLOCKED_SCORE = 0.5          # a chunk the WAF will not let Jev see is ranked as a coin flip


def _score_window(w: dict, depth: int = 0) -> tuple[dict, int, int, int]:
    """Score one window; on a WAF block, bisect it until the offending chunks are isolated.

    Returns (scores, jev_tokens, calls, blocked_chunks)."""
    try:
        ans, u = _call(w["state"], w["questions"])
        return {int(k[1:]): v for k, v in ans.items()}, u, 1, 0
    except Blocked:
        keys = list(w["state"]["chunks"])
        if len(keys) == 1 or depth >= 6:
            return {int(k[1:]): BLOCKED_SCORE for k in keys}, 0, 1, len(keys)
        out, used, calls, blocked = {}, 0, 1, 0
        for half in (keys[: len(keys) // 2], keys[len(keys) // 2:]):
            sub = {"state": {**w["state"], "chunks": {k: w["state"]["chunks"][k] for k in half}},
                   "questions": {k: w["questions"][k] for k in half}}
            s, u, c, b = _score_window(sub, depth + 1)
            out.update(s); used += u; calls += c; blocked += b
        return out, used, calls, blocked


def score(task: str, chunks: list[dict], scale: float = 1.0) -> tuple[dict[int, float], dict]:
    """Return ({chunk_id: P(needed)}, stats)."""
    t0 = time.time()
    ws = windows(task, chunks, scale)
    scores, used, calls, blocked = {}, 0, 0, 0
    with cf.ThreadPoolExecutor(CONCURRENCY) as ex:
        for s, u, c, b in ex.map(_score_window, ws):
            scores.update(s); used += u; calls += c; blocked += b
    return scores, {"windows": len(ws), "calls": calls, "blocked_chunks": blocked,
                    "jev_input_tokens": used, "seconds": round(time.time() - t0, 2)}


USER_CLIP_CHARS = 1_500      # force-kept user messages are clipped to this
USER_SHARE = 0.25            # and never take more than this share of the budget


def select(chunks: list[dict], scores: dict[int, float], budget_tokens: int) -> dict[int, int]:
    """Return {chunk_id: max_chars} to render.

    User messages are kept first, clipped, newest first, up to USER_SHARE of the
    budget: they carry intent and corrections. Everything else, including a user
    message whose full text scores high, competes on score for the rest.
    """
    keep, spent = {}, 0
    for c in sorted((c for c in chunks if c["kind"] == "user"), key=lambda c: -c["id"]):
        t = tokens(render(c, USER_CLIP_CHARS))
        if spent + t > budget_tokens * USER_SHARE:
            break
        keep[c["id"]] = USER_CLIP_CHARS; spent += t
    full = int(MAX_CHUNK_TOKENS * CHARS_PER_TOKEN)
    for c in sorted(chunks, key=lambda c: -scores.get(c["id"], 0)):
        s = scores.get(c["id"], 0)
        if s < SCORE_FLOOR:
            break
        if keep.get(c["id"]) == full:
            continue
        had = tokens(render(c, keep[c["id"]])) if c["id"] in keep else 0
        t = tokens(render(c, full)) - had
        if spent + t <= budget_tokens:
            keep[c["id"]] = full; spent += t
    return keep


def build_context(task: str, chunks: list[dict], budget_tokens: int = 20_000,
                  scale: float = 4.0) -> tuple[str, dict]:
    """scale multiplies how much of each chunk Jev sees; larger scale means more windows."""
    scores, stats = score(task, chunks, scale)
    keep = select(chunks, scores, budget_tokens)
    kept = [c for c in chunks if c["id"] in keep]
    body = "\n\n".join(render(c, keep[c["id"]]) for c in kept)
    header = (f"Context from the parent session, selected for this task: {len(kept)} of {len(chunks)} "
              f"transcript chunks (~{tokens(body)} tokens; ids in brackets). Chunks not shown were judged "
              f"irrelevant; if something you need is missing, say so in your reply.")
    stats.update({"kept_ids": [c["id"] for c in kept], "context_tokens": tokens(body), "scores": scores})
    return header + "\n\n" + body, stats
