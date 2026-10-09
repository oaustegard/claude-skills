#!/usr/bin/env python3
"""Typed decisions from Claude Haiku, shaped like OpenAI's Decisions API.

A decision model answers fixed-form questions about some evidence with a
probability for every option instead of text: `predicate` (P that a condition
holds), `choice` (one of N unordered values) and `score` (ordered rubric levels;
the score is the probability-weighted level index). Purpose-built decision
models read those probabilities off the network. Haiku's logits are not
exposed, so here they are estimated:

1. Every sample states a probability per option; keys it leaves out share its
   unassigned mass.
2. k samples (default 3) run in parallel with the options shuffled (choice,
   predicate) or the rubric reversed (score), which cancels position bias.
3. The answer is the mean of the samples. Disagreement flattens it, which
   lowers `confidence`; `diagnostics.agreement` reports it directly.
4. The pool is temperature-scaled per question type from a labelled eval
   (assets/calibration.json, or the file DECIDER_CALIBRATION names).

`confidence` is (k*p_max - 1)/(k - 1), the top probability's distance above
uniform. It reproduces the published examples of OpenAI's Decisions API
(0.93, 0.55) and Strands Decider (0.768).

Transports (--transport, default auto):
  api      Anthropic Messages API through the `anthropic` SDK. Picked by auto when
           ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN is set. Fastest.
  cli      `claude -p` with no tools, settings, MCP or session file. Picked by
           auto otherwise, when `claude` is on PATH. ~4 s per request.
  bedrock  Amazon Bedrock through AnthropicBedrockMantle; needs AWS_REGION and
           AWS credentials. Never picked by auto.
With none of these, `emit` prints prompts for parallel Haiku subagents and
`aggregate` pools their replies.

    python3 decide.py run request.json [-k 3] [--transport cli]
    python3 decide.py emit request.json -k 3 > batch.json
    python3 decide.py aggregate batch.json replies.json
    python3 decide.py eval ../assets/eval.jsonl --out results.jsonl
    python3 decide.py calibrate results.jsonl --out my-calibration.json

A failure is None, never a default answer: decide() returns None when no
sample produced a usable distribution for some question.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PROMPT = SKILL / "assets" / "system-prompt.md"
CALIBRATION = Path(os.environ.get("DECIDER_CALIBRATION") or SKILL / "assets" / "calibration.json")
CLI_MODEL = os.environ.get("DECIDER_CLI_MODEL", "claude-haiku-5-5")  # the model the calibration was fitted on
API_MODEL = os.environ.get("DECIDER_API_MODEL", "claude-haiku-5-5")
BEDROCK_MODEL = os.environ.get("DECIDER_BEDROCK_MODEL", "anthropic.claude-haiku-5-5")
PRICE = (0.10, 0.50)  # Haiku 5.5 first-party $/MTok in, out, for prompts under 100K tokens
K = int(os.environ.get("DECIDER_K", "3"))
TIMEOUT = float(os.environ.get("DECIDER_TIMEOUT", "60"))
WORKERS = int(os.environ.get("DECIDER_WORKERS", "8"))
MIN_CALIBRATION = 50  # labelled answers per type before a fitted temperature is trusted
FLOOR = 0.005  # mixed in before tempering so a stated 0 can still be recalibrated
TYPES = ("predicate", "choice", "score")
PREDICATE = (("true", "The condition in the instructions holds for the evidence."),
             ("false", "The condition in the instructions does not hold for the evidence."))


class DeciderError(Exception):
    pass


@dataclass
class Option:
    key: str
    value: object
    label: str | None = None
    description: str | None = None


@dataclass
class Question:
    name: str
    type: str
    instructions: str
    options: list[Option] = field(default_factory=list)


# ---------------------------------------------------------------- request

def normalize_request(req: dict) -> list[Question]:
    input_text(req)  # rejects image input early
    out, seen = [], set()
    for i, q in enumerate(req.get("questions") or []):
        qtype, name = q.get("type"), q.get("name") or f"question_{i}"
        if qtype not in TYPES:
            raise DeciderError(f"question {name}: unknown type {qtype!r}")
        if name in seen:
            raise DeciderError(f"duplicate question name {name!r}")
        seen.add(name)
        if qtype == "predicate":
            opts = [Option(k, k == "true", None, d) for k, d in PREDICATE]
        elif qtype == "choice":
            opts = [Option(str(c["value"]), c["value"], None, c.get("description")) for c in q.get("choices") or []]
        else:
            opts = [Option(str(j), j, lv["label"], lv.get("description")) for j, lv in enumerate(q.get("levels") or [])]
        if len(opts) < 2 or len({o.key for o in opts}) != len(opts):
            raise DeciderError(f"question {name}: needs two or more distinct options")
        out.append(Question(name, qtype, q.get("instructions") or "", opts))
    if not out:
        raise DeciderError("request has no questions")
    return out


def input_text(req: dict) -> str:
    inp = req.get("input")
    if isinstance(inp, str):
        return inp
    parts = []
    for msg in inp or []:
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
            continue
        for p in content or []:
            if p.get("type") == "input_text":
                parts.append(p["text"])
            else:
                raise DeciderError(f"unsupported input part {p.get('type')!r}: text only")
    return "\n".join(parts)


# ---------------------------------------------------------------- sampling

def presented_order(q: Question, i: int) -> list[str]:
    keys = [o.key for o in q.options]
    if q.type == "score":
        return keys if i % 2 == 0 else keys[::-1]
    if i:
        random.Random(f"{q.name}:{i}").shuffle(keys)
    return keys


def sample_prompt(req: dict, qs: list[Question], i: int) -> str:
    blocks = [f"<evidence>\n{input_text(req)}\n</evidence>"]
    for q in qs:
        by_key = {o.key: o for o in q.options}
        order = presented_order(q, i)
        if q.type == "score":
            head = "Levels, lowest to highest:" if order[0] == "0" else "Levels, highest to lowest:"
            lines = [f"- {k}: {by_key[k].label}" + (f" — {by_key[k].description}" if by_key[k].description else "")
                     for k in order]
        else:
            head = "Options:"
            lines = [f"- {k}" + (f": {by_key[k].description}" if by_key[k].description else "") for k in order]
        blocks.append(f'<question name="{q.name}" type="{q.type}">\n{q.instructions}\n{head}\n'
                      + "\n".join(lines) + "\n</question>")
    blocks.append("Answer every question with a probability for each option key.")
    return "\n\n".join(blocks)


def parse_reply(reply, qs: list[Question]) -> dict | None:
    """{name: {"probs": {key: p}, "refusal": bool} or None per question}; None if unparseable."""
    if isinstance(reply, str):
        m = re.search(r"\{.*\}", reply, re.DOTALL)
        try:
            reply = json.loads(m.group(0)) if m else None
        except ValueError:
            reply = None
    if not isinstance(reply, dict) or not isinstance(reply.get("answers"), dict):
        return None
    out = {}
    for q in qs:
        a = reply["answers"].get(q.name)
        probs = a.get("probabilities") if isinstance(a, dict) else None
        try:
            stated = {o.key: max(0.0, float(probs[o.key])) for o in q.options if o.key in probs}
        except (TypeError, ValueError):
            out[q.name] = None
            continue
        if not stated:
            out[q.name] = None
            continue
        # With many options Haiku leaves out the ones it rules out (14 of 520 samples,
        # all 8-way). The omission is the answer: unstated keys share what mass is left.
        missing = [o.key for o in q.options if o.key not in stated]
        rest = max(0.0, 1.0 - sum(stated.values())) / len(missing) if missing else 0.0
        vals = {o.key: stated.get(o.key, rest) for o in q.options}
        total = sum(vals.values())
        out[q.name] = ({"probs": {k: v / total for k, v in vals.items()}, "refusal": bool(a.get("refusal"))}
                       if total > 0 else None)
    return out


# ---------------------------------------------------------------- math

def confidence(probs) -> float:
    """Top probability's distance above uniform, on OpenAI's and Strands' scale."""
    p = list(probs)
    k = len(p)
    return (k * max(p) - 1) / (k - 1)


def expected_level(probs) -> float:
    return sum(i * p for i, p in enumerate(probs))


def temper(p: dict, T: float) -> dict:
    if T == 1.0:
        return dict(p)
    w = {k: max(v, 1e-12) ** (1 / T) for k, v in p.items()}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def floored(p: dict) -> dict:
    k = len(p)
    return {key: (1 - FLOOR) * v + FLOOR / k for key, v in p.items()}


def nll(recs, T: float) -> float:
    return -sum(math.log(temper(floored(p), T)[y]) for p, y in recs) / len(recs)


def fit_temperature(recs) -> float:
    grid = [math.exp(math.log(0.25) + i * (math.log(8) - math.log(0.25)) / 80) for i in range(81)]
    return round(min(grid, key=lambda T: nll(recs, T)), 3)


def load_calibration() -> dict:
    try:
        data = json.loads(CALIBRATION.read_text())
    except (OSError, ValueError):
        return {}
    return {t: float(data[t]["temperature"]) for t in TYPES if t in data}


# ---------------------------------------------------------------- assembly

def _assemble(qs: list[Question], parsed: list, failed: int, calibration: dict) -> dict | None:
    answers = []
    for q in qs:
        got = [s[q.name] for s in parsed if s.get(q.name)]
        if not got:
            return None
        keys = [o.key for o in q.options]
        if sum(g["refusal"] for g in got) * 2 > len(got):
            answers.append({"type": "refusal", "name": q.name})
            continue
        raw = {k: sum(g["probs"][k] for g in got) / len(got) for k in keys}
        T = calibration.get(q.type, 1.0)
        p = temper(floored(raw), T) if T != 1.0 else raw
        top = max(keys, key=p.get)
        diag = {
            "samples": len(got), "failed": failed + sum(1 for s in parsed if not s.get(q.name)),
            "agreement": sum(max(keys, key=g["probs"].get) == max(keys, key=raw.get) for g in got) / len(got),
            "spread": round(sum(0.5 * sum(abs(g["probs"][k] - raw[k]) for k in keys) for g in got) / len(got), 4),
            "temperature": T,
            "raw": {k: round(raw[k], 4) for k in keys},
            "per_sample": [{k: round(g["probs"][k], 4) for k in keys} for g in got],
        }
        if q.type == "predicate":
            answers.append({"type": "predicate", "name": q.name, "probability": p["true"], "diagnostics": diag})
        elif q.type == "choice":
            answers.append({"type": "choice", "name": q.name,
                            "choice": next(o.value for o in q.options if o.key == top),
                            "probabilities": [{"value": o.value, "probability": p[o.key]} for o in q.options],
                            "confidence": confidence(p[k] for k in keys), "diagnostics": diag})
        else:
            answers.append({"type": "score", "name": q.name, "score": expected_level([p[k] for k in keys]),
                            "probabilities": [{"value": o.value, "label": o.label, "probability": p[o.key]}
                                              for o in q.options],
                            "confidence": confidence(p[k] for k in keys), "diagnostics": diag})
    return {"answers": answers}


# ---------------------------------------------------------------- transports

def system_prompt() -> str:
    return PROMPT.read_text().strip()


def claude_argv(system: str, user: str) -> list[str]:
    # No --json-schema: structured output costs a second turn and ~3x the output
    # tokens (2.2s vs 0.8s of API time, measured 2026-10-09); parse_reply copes.
    return ["claude", "-p", "--model", CLI_MODEL, "--output-format", "json",
            "--system-prompt", system, "--tools", "", "--setting-sources", "",
            "--strict-mcp-config", "--no-session-persistence", user]


def cli_transport(system: str, user: str) -> dict:
    try:
        r = subprocess.run(claude_argv(system, user), capture_output=True, text=True, check=False,
                           timeout=TIMEOUT, cwd=tempfile.gettempdir())
        out = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, ValueError, OSError) as e:
        raise DeciderError(f"{type(e).__name__}: {str(e)[:200]}") from None
    reply = out.get("result")
    if out.get("is_error") or reply is None:
        raise DeciderError(f"claude -p: {str(out.get('result'))[:200]}")
    if isinstance(reply, str):
        reply = parse_json(reply)
    if isinstance(reply, dict):
        reply["_usage"] = {"cost_usd": out.get("total_cost_usd") or 0.0, "api_ms": out.get("duration_api_ms") or 0}
    return reply


_CLIENTS: dict = {}


def message_params(model: str, system: str, user: str) -> dict:
    # Haiku 5.5: thinking is on by default and may be disabled only at effort high or
    # below; temperature and assistant prefill are rejected.
    return {"model": model, "max_tokens": 1024, "system": system,
            "thinking": {"type": "disabled"}, "output_config": {"effort": "low"},
            "messages": [{"role": "user", "content": user}]}


def _sdk_transport(kind: str):
    def transport(system: str, user: str) -> dict:
        try:
            import anthropic
        except ImportError:
            raise DeciderError("pip install anthropic (the api and bedrock transports use the SDK)") from None
        if kind not in _CLIENTS:
            _CLIENTS[kind] = (anthropic.Anthropic() if kind == "api"
                              else anthropic.AnthropicBedrockMantle(aws_region=os.environ.get("AWS_REGION")))
        model = API_MODEL if kind == "api" else BEDROCK_MODEL
        t0 = time.monotonic()
        try:
            msg = _CLIENTS[kind].messages.create(**message_params(model, system, user))
        except (anthropic.APIError, TypeError) as e:  # TypeError: the SDK found no credentials
            raise DeciderError(f"{type(e).__name__}: {str(e)[:200]}") from None
        if msg.stop_reason == "refusal":
            raise DeciderError("refusal stop_reason")
        reply = parse_json("".join(b.text for b in msg.content if b.type == "text"))
        if isinstance(reply, dict):
            u = msg.usage
            tokens_in = (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0)
            reply["_usage"] = {"cost_usd": (tokens_in * PRICE[0] + (u.output_tokens or 0) * PRICE[1]) / 1e6,
                               "api_ms": round((time.monotonic() - t0) * 1000)}
        return reply
    return transport


def pick_transport(name: str = "auto"):
    if name == "auto":
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            name = "api"
        elif shutil.which("claude"):
            name = "cli"
        else:
            raise DeciderError("no transport: set ANTHROPIC_API_KEY, install the claude CLI, "
                               "or use emit/aggregate with Haiku subagents")
    if name == "cli":
        return cli_transport
    if name in ("api", "bedrock"):
        return _sdk_transport(name)
    raise DeciderError(f"unknown transport {name!r}")


def parse_json(text: str):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else text
    except ValueError:
        return text


def decide(req: dict, k: int = K, transport=None, calibration: dict | None = None,
           errors: list | None = None) -> dict | None:
    """The Decisions-API-shaped response, or None. Transport failures are appended
    to `errors` when one is passed."""
    qs = normalize_request(req)
    transport = transport or pick_transport()
    calibration = load_calibration() if calibration is None else calibration
    system = system_prompt()

    def one(i):
        try:
            return transport(system, sample_prompt(req, qs, i))
        except DeciderError as e:
            if errors is not None:
                errors.append(str(e))
            return None

    t0 = time.monotonic()
    if k == 1:
        replies = [one(0)]
    else:
        with ThreadPoolExecutor(max_workers=min(k, WORKERS)) as ex:
            replies = list(ex.map(one, range(k)))
    failed = sum(r is None for r in replies)
    parsed = [parse_reply(r, qs) for r in replies if r is not None]
    failed += sum(p is None for p in parsed)
    out = _assemble(qs, [p for p in parsed if p], failed, calibration)
    if out is None:
        return None
    usage = [r["_usage"] for r in replies if isinstance(r, dict) and "_usage" in r]
    out["usage"] = {"samples": k, "latency_ms": round((time.monotonic() - t0) * 1000),
                    "cost_usd": round(sum(u["cost_usd"] for u in usage), 6)}
    return out


def emit(req: dict, k: int = K, agent: str | None = None) -> dict:
    """Prompts for k parallel Haiku subagents, for a session with no transport.
    Without `agent` the system prompt rides inside each prompt, so a stock
    general-purpose Haiku subagent can answer (~58K tokens a sample, measured).
    With `agent` (agents/decider.md, installed by the plugin) the prompt
    carries only the sample (~9K). [no-context] stops a context-appending
    PreToolUse hook (delegating-with-context) from adding transcript chunks,
    which would become evidence."""
    qs = normalize_request(req)
    head = "" if agent else system_prompt() + "\n\n---\n\n"
    return {"request": req,
            "samples": [{"subagent_type": agent or "general-purpose", "model": "haiku",
                         "prompt": head + sample_prompt(req, qs, i) + "\n\n[no-context]"} for i in range(k)]}


def aggregate(req: dict, replies: list, calibration: dict | None = None) -> dict | None:
    qs = normalize_request(req)
    calibration = load_calibration() if calibration is None else calibration
    parsed = [parse_reply(r, qs) for r in replies]
    return _assemble(qs, [p for p in parsed if p], sum(p is None for p in parsed), calibration)


# ---------------------------------------------------------------- evaluation

def label_key(q: Question, label) -> str:
    if q.type == "predicate":
        return "true" if label in (True, "true", 1) else "false"
    for o in q.options:
        if label == o.value or str(label) == o.key or label == o.label:
            return o.key
    raise DeciderError(f"label {label!r} matches no option of {q.name}")


def _auroc(scores, positives) -> float | None:
    pos = [s for s, y in zip(scores, positives) if y]
    neg = [s for s, y in zip(scores, positives) if not y]
    if not pos or not neg:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def metrics(rows: list[dict]) -> dict:
    """accuracy, Brier (sum of squared errors / 2, so a predicate's equals the binary
    score), ECE over the top probability in 10 bins, and AUROC of confidence for
    telling right answers from wrong ones."""
    if not rows:
        return {}
    acc, brier, conf, right = 0, 0.0, [], []
    for r in rows:
        p = r["probs"]
        top = max(p, key=p.get)
        ok = top == r["label"]
        acc += ok
        brier += sum((v - (k == r["label"])) ** 2 for k, v in p.items()) / 2
        conf.append(p[top])
        right.append(ok)
    n = len(rows)
    ece = 0.0
    for b in range(10):
        idx = [i for i, c in enumerate(conf) if b / 10 < c <= (b + 1) / 10 or (b == 0 and c == 0)]
        if idx:
            ece += len(idx) / n * abs(sum(right[i] for i in idx) / len(idx) - sum(conf[i] for i in idx) / len(idx))
    au = _auroc(conf, right)
    return {"n": n, "accuracy": round(acc / n, 3), "brier": round(brier / n, 4), "ece": round(ece, 4),
            "auroc": None if au is None else round(au, 3)}


def evaluate(items: list[dict], k: int, transport) -> list[dict]:
    def run(item):
        req = {"input": item["input"], "questions": item["questions"]}
        return item, decide(req, k=k, transport=transport)

    rows = []
    with ThreadPoolExecutor(max_workers=max(1, WORKERS // k)) as ex:
        for item, res in ex.map(run, items):
            qs = {q.name: q for q in normalize_request(item)}
            if res is None:
                rows.append({"id": item.get("id"), "error": True})
                continue
            for a in res["answers"]:
                q = qs[a["name"]]
                if a["type"] == "refusal":
                    rows.append({"id": item.get("id"), "name": q.name, "type": q.type, "refusal": True})
                    continue
                if q.type == "predicate":
                    probs = {"true": a["probability"], "false": 1 - a["probability"]}
                else:
                    probs = {o.key: e["probability"] for o, e in zip(q.options, a["probabilities"])}
                rows.append({"id": item.get("id"), "name": q.name, "type": q.type, "probs": probs,
                             "raw": a["diagnostics"]["raw"], "label": label_key(q, item["labels"][q.name]),
                             "agreement": a["diagnostics"]["agreement"], "per_sample": a["diagnostics"]["per_sample"],
                             "usage": res["usage"]})
    return rows


def report(rows: list[dict]) -> dict:
    scored = [r for r in rows if "probs" in r]
    out = {"overall": metrics(scored)}
    for t in TYPES:
        sub = [r for r in scored if r["type"] == t]
        if sub:
            out[t] = metrics(sub)
    lat = sorted(r["usage"]["latency_ms"] for r in scored)
    cost = [r["usage"]["cost_usd"] for r in scored if r["usage"]["cost_usd"] is not None]
    out["errors"] = sum(1 for r in rows if r.get("error") or r.get("refusal"))
    out["latency_ms_p50"] = lat[len(lat) // 2] if lat else None
    out["latency_ms_p90"] = lat[int(len(lat) * 0.9)] if lat else None
    out["cost_usd_per_request"] = round(sum(cost) / len({r["id"] for r in scored}), 6) if cost else None
    return out


# ---------------------------------------------------------------- CLI

def _read(path: str):
    return json.load(sys.stdin) if path == "-" else json.loads(Path(path).read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "eval"):
        p = sub.add_parser(name)
        p.add_argument("request" if name == "run" else "items",
                       help="request JSON, or - for stdin" if name == "run"
                       else "JSONL of {id, input, questions, labels: {name: value}}")
        p.add_argument("-k", type=int, default=K)
        p.add_argument("--transport", choices=["auto", "api", "cli", "bedrock"], default="auto")
        if name == "eval":
            p.add_argument("--out", required=True)
    p = sub.add_parser("emit")
    p.add_argument("request")
    p.add_argument("-k", type=int, default=K)
    p.add_argument("--agent", help="subagent type of the installed agents/decider.md, e.g. decider")
    p = sub.add_parser("aggregate")
    p.add_argument("batch")
    p.add_argument("replies", help="JSON list of the subagents' reply texts")
    p = sub.add_parser("calibrate")
    p.add_argument("results", help="JSONL written by eval")
    p.add_argument("--out", required=True, help="calibration JSON to write; point DECIDER_CALIBRATION at it")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "run":
            errors: list = []
            res = decide(_read(a.request), k=a.k, transport=pick_transport(a.transport), errors=errors)
            if res is None:
                print(f"decide: no usable sample; first error: {errors[0] if errors else 'unparseable replies'}",
                      file=sys.stderr)
                return 1
            print(json.dumps(res, indent=2))
            return 0
        if a.cmd == "emit":
            print(json.dumps(emit(_read(a.request), a.k, a.agent), indent=2))
            return 0
        if a.cmd == "aggregate":
            res = aggregate(_read(a.batch)["request"], _read(a.replies))
            print(json.dumps(res, indent=2))
            return 0 if res is not None else 1
        if a.cmd == "eval":
            items = [json.loads(line) for line in Path(a.items).read_text().splitlines() if line.strip()]
            rows = evaluate(items, a.k, pick_transport(a.transport))
            Path(a.out).write_text("".join(json.dumps(r) + "\n" for r in rows))
            print(json.dumps(report(rows), indent=2))
            return 0
    except DeciderError as e:
        print(f"decide: {e}", file=sys.stderr)
        return 2
    rows = [json.loads(line) for line in Path(a.results).read_text().splitlines() if line.strip()]
    data = {}
    for t in TYPES:
        recs = [(r["raw"], r["label"]) for r in rows if r.get("type") == t and "raw" in r]
        if len(recs) < MIN_CALIBRATION:
            print(f"{t}: {len(recs)} labelled answers, fewer than {MIN_CALIBRATION}; keeping T = 1", file=sys.stderr)
            continue
        T = fit_temperature(recs)
        before = metrics([{"probs": p, "label": y} for p, y in recs])
        after = metrics([{"probs": temper(floored(p), T), "label": y} for p, y in recs])
        data[t] = {"temperature": T, "n": len(recs), "nll_before": round(nll(recs, 1.0), 4),
                   "nll_after": round(nll(recs, T), 4), "ece_before": before["ece"], "ece_after": after["ece"]}
    data["fitted"] = time.strftime("%Y-%m-%d")
    data["source"] = os.path.basename(a.results)
    Path(a.out).write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
