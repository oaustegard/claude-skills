#!/usr/bin/env python3
"""Verify code-review findings: a quote check, then a decision model's verdict.

The pattern is bluesky-social/roast's: a finder proposes defects, each with a
verbatim code quote and a fix; findings whose quote is not in the file are
dropped mechanically; an independent verifier reads the cited code and
confirms or refutes every claim that remains. Here the verifier is TypeSafe's
Jev, asked typed questions with a probability per answer, so the drop rule and
the commit gate are thresholds instead of a model's yes or no.

    verify.py run findings.json [--repo DIR] [--diff FILE] [--format md]
    verify.py emit findings.json --out requests.json      # Muninn `decide` tool path
    verify.py apply requests.json answers.json
    verify.py eval eval.jsonl [--out results.jsonl]

Exit codes: 0 every finding verified and the gate (if any) passed; 1 the gate
tripped; 2 bad input or no transport; 3 some finding could not be verified
(the run is incomplete, never clean) and the gate did not trip.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = os.environ.get("VERIFY_JEV_MODEL", "jev-1.14.0")
TIMEOUT = float(os.environ.get("VERIFY_TIMEOUT", "60"))
WORKERS = int(os.environ.get("VERIFY_WORKERS", "8"))
REFUTE_AT = 0.7    # drop a finding when P(refuted) reaches this
CONFIRM_AT = 0.7   # call it confirmed when P(confirmed) reaches this
SEVERITY_AT = 0.5  # the gate counts a severity level when P(at least that level) reaches this
PAD = 12           # lines kept on each side of the quote, at least
MAX_LINES = 160    # cap on the code window sent per finding
MAX_CHARS = 14000
LEVELS = ["info", "low", "medium", "high", "critical"]
VERDICTS = {
    "confirmed": "The code shown has the defect as the finding describes it.",
    "refuted": "The code shown contradicts the finding: a guard, a bound, a lock, a handler or another "
               "fact visible in the code means the defect does not occur as described.",
    "insufficient_context": "Deciding needs code that is not shown, such as a caller, a type definition "
                            "or configuration.",
}
TASK = ("Verify one finding from an automated code review. The finder is often wrong: it misreads "
        "guards, bounds and control flow. Judge the claim only against the code shown; the finding's "
        "own description is a claim, not evidence. Lines marked '>' are the ones the finding quotes.")


class VerifyError(Exception):
    pass


# ---------------------------------------------------------------- findings

def load_findings(obj) -> list[dict]:
    """Accept a list, {"findings": [...]}, or ReportFindings-shaped items."""
    items = obj.get("findings", obj) if isinstance(obj, dict) else obj
    if not isinstance(items, list):
        raise VerifyError("findings must be a JSON list or an object with a 'findings' list")
    out = []
    for i, f in enumerate(items):
        if not isinstance(f, dict) or not f.get("file"):
            raise VerifyError(f"finding {i}: needs at least 'file'")
        desc = f.get("description") or f.get("summary") or f.get("claim") or ""
        if f.get("failure_scenario"):
            desc = f"{desc}\nFailure scenario: {f['failure_scenario']}".strip()
        out.append({
            "id": str(f.get("id") or i + 1),
            "file": f["file"],
            "line": f.get("line"),
            "description": desc,
            "code_quote": f.get("code_quote") or f.get("quote") or "",
            "fix": f.get("fix") or f.get("suggestion") or "",
            "claimed_severity": f.get("severity"),
        })
    if len({f["id"] for f in out}) != len(out):
        raise VerifyError("finding ids must be unique")
    return out


def collapse(s: str) -> str:
    return " ".join(s.split())


def fingerprint(f: dict) -> str:
    """Similarity key across runs: same file, same quoted code (whitespace-insensitive).
    Two different claims about the same lines collide; use it to match, never to suppress."""
    return hashlib.sha256(f"{f['file']}\0{collapse(f['code_quote'])}".encode()).hexdigest()[:16]


def locate(text: str, quote: str, near: int | None = None) -> tuple[int, int] | None:
    """1-based (first, last) line of the quote in text, comparing with whitespace collapsed.
    With several matches, the one nearest `near` wins."""
    q = collapse(quote)
    if not q:
        return None
    norm, line_of, line, pending_space = [], [], 1, False
    for ch in text:
        if ch.isspace():
            pending_space = bool(norm)
        else:
            if pending_space:
                norm.append(" ")
                line_of.append(line)
                pending_space = False
            norm.append(ch)
            line_of.append(line)
        if ch == "\n":
            line += 1
    flat = "".join(norm)
    hits, start = [], flat.find(q)
    while start != -1:
        hits.append((line_of[start], line_of[start + len(q) - 1]))
        start = flat.find(q, start + 1)
    if not hits:
        return None
    return min(hits, key=lambda h: abs(h[0] - near)) if near else hits[0]


def window(lines: list[str], first: int, last: int) -> tuple[int, int]:
    """The top-level block around the quote, clamped to MAX_LINES and padded by PAD.
    A top-level block starts at a non-blank line with no indentation; that covers
    Python, Go, JS/TS, shell and SQL files without a parser."""
    n = len(lines)

    def top(i):
        s = lines[i - 1]
        return bool(s.strip()) and not s[0].isspace() and not s.lstrip().startswith(("}", ")", "]"))

    lo = first
    while lo > 1 and not top(lo):
        lo -= 1
    hi = last
    while hi < n and not top(hi + 1):
        hi += 1
    lo, hi = min(lo, max(1, first - PAD)), max(hi, min(n, last + PAD))
    if hi - lo + 1 > MAX_LINES:
        mid = (first + last) // 2
        lo = max(1, min(first - PAD, mid - MAX_LINES // 2))
        hi = min(n, lo + MAX_LINES - 1)
    return lo, hi


def render(lines: list[str], lo: int, hi: int, first: int, last: int) -> str:
    width = len(str(hi))
    out = [f"{'>' if first <= i <= last else ' '} {i:>{width}} | {lines[i - 1]}" for i in range(lo, hi + 1)]
    text = "\n".join(out)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "\n[... truncated]"


def diff_hunks(diff: str | None, path: str) -> str | None:
    if not diff:
        return None
    keep, cur = [], None
    for ln in diff.splitlines():
        if ln.startswith("diff --git "):
            cur = None
        elif ln.startswith("+++ "):
            cur = ln[4:].removeprefix("b/").strip()
            continue
        if cur == path and not ln.startswith(("--- ", "diff --git", "index ")):
            keep.append(ln)
    text = "\n".join(keep).strip()
    return text[:MAX_CHARS // 2] or None


def read_source(repo: Path, path: str, ref: str | None) -> str | None:
    if ref:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    p = (repo / path).resolve()
    try:
        p.relative_to(repo.resolve())
    except ValueError:
        return None  # a path that escapes the repository is treated as missing
    return p.read_text(errors="replace") if p.is_file() else None


def ground(f: dict, repo: Path, ref: str | None, diff: str | None) -> dict:
    """Attach grounding and the Jev request, or a drop reason."""
    f["fingerprint"] = fingerprint(f)
    if not f["code_quote"].strip():
        return {**f, "status": "dropped", "reason": "missing_code_quote"}
    text = read_source(repo, f["file"], ref)
    if text is None:
        return {**f, "status": "dropped", "reason": "file_not_found"}
    near = int(f["line"]) if str(f.get("line") or "").isdigit() else None
    hit = locate(text, f["code_quote"], near)
    if hit is None:
        return {**f, "status": "dropped", "reason": "ungrounded_code_quote"}
    lines = text.splitlines()
    lo, hi = window(lines, *hit)
    f["grounding"] = {"lines": list(hit), "window": [lo, hi]}
    f["request"] = jev_request(f, render(lines, lo, hi, *hit), diff_hunks(diff, f["file"]))
    return f


def jev_request(f: dict, code: str, hunks: str | None) -> dict:
    state = {"task": TASK, "file": f["file"], "finding": f["description"],
             "claimed_severity": f["claimed_severity"], "code_quote": f["code_quote"], "code": code}
    if f["fix"]:
        state["proposed_fix"] = f["fix"]
    if hunks:
        state["diff_for_this_file"] = hunks
    questions = {
        "verdict": {"type": "choice", "instructions": "Does the code shown have the defect this finding claims?",
                    "criteria": VERDICTS},
        "severity": {"type": "score", "criteria": LEVELS,
                     "instructions": "If the defect is real, how severe is it for users of this code?"},
    }
    if f["fix"]:
        questions["fix_ok"] = {"type": "noul", "instructions": (
            "If the defect is real, would the proposed fix remove it without breaking the surrounding code?")}
    return {"state": state, "questions": questions}


# ---------------------------------------------------------------- transports

def _post(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise VerifyError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise VerifyError(f"{type(e).__name__}: {str(e)[:200]}") from None


def jev_transport(request: dict) -> dict:
    res = _post(JEV_URL, {"model": JEV_MODEL, **request},
                {"Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"]})
    return res.get("answers") or {}


def gateway_transport(request: dict) -> dict:
    """Cloudflare Workers AI. It accepts only `state` and `questions`: no model pin."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CF_ACCOUNT_ID']}/ai/run"
    headers = {"Authorization": "Bearer " + os.environ["CF_API_TOKEN"]}
    if os.environ.get("CF_GATEWAY_ID"):
        headers["cf-aig-gateway-id"] = os.environ["CF_GATEWAY_ID"]
    res = _post(url, {"model": "typesafe/jev", "input": request}, headers)
    return ((res.get("result") or {}).get("result") or {}).get("answers") or {}


def decider_transport(request: dict) -> dict:
    """deciding-with-confidence (Claude Haiku, k samples) in Jev's answer shape."""
    here = Path(__file__).resolve().parent
    for cand in (here.parent.parent / "deciding-with-confidence" / "scripts",
                 Path("/mnt/skills/user/deciding-with-confidence/scripts")):
        if (cand / "decide.py").is_file():
            sys.path.insert(0, str(cand))
            break
    try:
        import decide  # type: ignore
    except ImportError:
        raise VerifyError("deciding-with-confidence is not installed next to this skill") from None
    qs = []
    for name, q in request["questions"].items():
        if q["type"] == "noul":
            qs.append({"type": "predicate", "name": name, "instructions": q["instructions"]})
        elif q["type"] == "choice":
            qs.append({"type": "choice", "name": name, "instructions": q["instructions"],
                       "choices": [{"value": k, "description": d} for k, d in q["criteria"].items()]})
        else:
            qs.append({"type": "score", "name": name, "instructions": q["instructions"],
                       "levels": [{"label": lv} for lv in q["criteria"]]})
    errors: list = []
    res = decide.decide({"input": json.dumps(request["state"], indent=1), "questions": qs}, errors=errors)
    if res is None:
        raise VerifyError("decider: no usable sample" + (f"; {errors[0]}" if errors else ""))
    out = {}
    for a in res["answers"]:
        if a["type"] == "predicate":
            out[a["name"]] = {"type": "noul", "noul": a["probability"]}
        elif a["type"] == "choice":
            out[a["name"]] = {"type": "choice", "probabilities": {p["value"]: p["probability"]
                                                                 for p in a["probabilities"]}}
        elif a["type"] == "score":
            out[a["name"]] = {"type": "score", "probabilities": {str(p["value"]): p["probability"]
                                                                for p in a["probabilities"]}}
    return out


TRANSPORTS = {
    "jev": (lambda: bool(os.environ.get("TYPESAFE_API_KEY")), jev_transport),
    "gateway": (lambda: bool(os.environ.get("CF_API_TOKEN") and os.environ.get("CF_ACCOUNT_ID")),
                gateway_transport),
    "decider": (lambda: True, decider_transport),
}


def pick_transport(name: str):
    if name != "auto":
        if not TRANSPORTS[name][0]():
            raise VerifyError(f"transport {name}: its credentials are not set")
        return name, TRANSPORTS[name][1]
    for key in ("jev", "gateway"):
        if TRANSPORTS[key][0]():
            return key, TRANSPORTS[key][1]
    raise VerifyError("no Jev transport: set TYPESAFE_API_KEY (or CF_ACCOUNT_ID + CF_API_TOKEN), "
                      "use `emit` with the Muninn decide tool, or pass --transport decider")


# ---------------------------------------------------------------- policy

def read_answers(ans: dict) -> dict:
    """Probabilities from a Jev answers object; raises VerifyError on a shape it does not expect."""
    try:
        v = {k: float(ans["verdict"]["probabilities"].get(k, 0.0)) for k in VERDICTS}
        sev_raw = ans["severity"]["probabilities"]
        sev = [float(sev_raw.get(str(i), sev_raw.get(lv, 0.0))) for i, lv in enumerate(LEVELS)]
        fix = float(ans["fix_ok"]["noul"]) if "fix_ok" in ans else None
    except (KeyError, TypeError, ValueError, AttributeError):
        raise VerifyError(f"unexpected answer shape: {json.dumps(ans)[:200]}") from None
    if sum(v.values()) <= 0:
        raise VerifyError("verdict probabilities are all zero")
    return {"verdict": v, "severity": sev, "fix_ok": fix}


def judge(f: dict, ans: dict, refute_at: float, confirm_at: float) -> dict:
    a = read_answers(ans)
    v, sev = a["verdict"], a["severity"]
    if v["refuted"] >= refute_at:
        status, reason = "dropped", "refuted_by_verifier"
    elif v["confirmed"] >= confirm_at:
        status, reason = "confirmed", None
    else:
        status, reason = "uncertain", ("needs_more_context" if v["insufficient_context"] >= max(v.values())
                                       else "split_verdict")
    f.update(status=status, reason=reason, verdict={k: round(p, 3) for k, p in v.items()},
             severity={"probabilities": dict(zip(LEVELS, (round(p, 3) for p in sev))),
                       "expected": LEVELS[min(len(LEVELS) - 1, round(sum(i * p for i, p in enumerate(sev))))]},
             fix_ok=None if a["fix_ok"] is None else round(a["fix_ok"], 3))
    return f


def p_at_least(f: dict, level: str) -> float:
    probs = f.get("severity", {}).get("probabilities", {})
    return sum(probs.get(lv, 0.0) for lv in LEVELS[LEVELS.index(level):])


def report(findings: list[dict], transport: str, fail_on: str | None, severity_at: float) -> dict:
    for f in findings:
        f.pop("request", None)
    tripped = []
    if fail_on:
        tripped = [f["id"] for f in findings
                   if f["status"] == "confirmed" and p_at_least(f, fail_on) >= severity_at]
    counts = {}
    for f in findings:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    return {"complete": not any(f["status"] == "unverified" for f in findings),
            "transport": transport, "model": JEV_MODEL if transport == "jev" else None,
            "counts": counts,
            "gate": {"fail_on": fail_on, "severity_at": severity_at, "tripped": tripped} if fail_on else None,
            "findings": findings}


def exit_code(rep: dict) -> int:
    if rep["gate"] and rep["gate"]["tripped"]:
        return 1
    return 0 if rep["complete"] else 3


def markdown(rep: dict) -> str:
    order = {"confirmed": 0, "uncertain": 1, "unverified": 2, "dropped": 3}
    rows = ["| id | status | P(confirmed) | P(refuted) | severity | file:line | finding |",
            "|---|---|---|---|---|---|---|"]
    for f in sorted(rep["findings"], key=lambda f: order.get(f["status"], 9)):
        v = f.get("verdict") or {}
        loc = f"{f['file']}:{(f.get('grounding') or {}).get('lines', [f.get('line') or '?'])[0]}"
        status = f["status"] + (f" ({f['reason']})" if f.get("reason") else "")
        desc = collapse(f["description"])[:90].replace("|", "\\|")
        rows.append(f"| {f['id']} | {status} | {v.get('confirmed', '')} | {v.get('refuted', '')} | "
                    f"{(f.get('severity') or {}).get('expected', '')} | {loc} | {desc} |")
    head = f"**{', '.join(f'{n} {s}' for s, n in rep['counts'].items())}** via {rep['transport']}"
    if not rep["complete"]:
        head += " — INCOMPLETE: some findings were not verified"
    if rep["gate"]:
        g = rep["gate"]
        head += f"\n\nGate (fail on {g['fail_on']}): " + (f"TRIPPED by {', '.join(g['tripped'])}"
                                                           if g["tripped"] else "passed")
    return head + "\n\n" + "\n".join(rows)


# ---------------------------------------------------------------- commands

def prepare(findings: list[dict], repo: Path, ref: str | None, diff: str | None) -> list[dict]:
    return [ground(dict(f), repo, ref, diff) for f in findings]


def verify(findings: list[dict], transport_name: str, call, refute_at: float, confirm_at: float) -> list[dict]:
    def one(f):
        if "request" not in f:
            return f
        try:
            return judge(f, call(f["request"]), refute_at, confirm_at)
        except (VerifyError, KeyError) as e:
            f.update(status="unverified", reason=f"verifier_error: {e}")
            return f

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        return list(ex.map(one, findings))


def parse_reply(text) -> dict:
    """A Muninn decide reply: the answers JSON, possibly followed by a usage line."""
    if isinstance(text, dict):
        return text.get("answers", text)
    m = re.search(r"\{.*\}", str(text), re.S)
    if not m:
        raise VerifyError("reply holds no JSON object")
    obj = json.loads(m.group(0))
    return obj.get("answers", obj)


def cmd_run(a) -> int:
    findings = prepare(load_findings(_read(a.findings)), Path(a.repo), a.ref,
                       Path(a.diff).read_text() if a.diff else None)
    name, call = pick_transport(a.transport)
    t0 = time.monotonic()
    out = verify(findings, name, call, a.refute_at, a.confirm_at)
    rep = report(out, name, a.fail_on, a.severity_at)
    rep["latency_ms"] = round((time.monotonic() - t0) * 1000)
    _write(rep, a.format)
    return exit_code(rep)


def cmd_emit(a) -> int:
    findings = prepare(load_findings(_read(a.findings)), Path(a.repo), a.ref,
                       Path(a.diff).read_text() if a.diff else None)
    Path(a.out).write_text(json.dumps({"findings": findings}, indent=1))
    calls = [{"id": f["id"], **f["request"]} for f in findings if "request" in f]
    print(json.dumps({"calls": len(calls), "dropped_before_verify": len(findings) - len(calls),
                      "requests": calls}, indent=1))
    return 0


def cmd_apply(a) -> int:
    findings = _read(a.batch)["findings"]
    replies = _read(a.answers)
    if not isinstance(replies, dict):
        raise VerifyError("answers must be a JSON object keyed by finding id")
    for f in findings:
        if "request" not in f:
            continue
        if f["id"] not in replies:
            f.update(status="unverified", reason="no_answer")
            continue
        try:
            judge(f, parse_reply(replies[f["id"]]), a.refute_at, a.confirm_at)
        except (VerifyError, ValueError) as e:
            f.update(status="unverified", reason=f"verifier_error: {e}")
    rep = report(findings, "muninn-decide", a.fail_on, a.severity_at)
    _write(rep, a.format)
    return exit_code(rep)


def cmd_eval(a) -> int:
    """Labelled items: {id, files: {path: text}, finding, label: confirmed|refuted|ungrounded}."""
    items = [json.loads(ln) for ln in Path(a.items).read_text().splitlines() if ln.strip()]
    name, call = pick_transport(a.transport)
    rows = []
    with tempfile.TemporaryDirectory() as d:
        batch = []
        for it in items:
            root = Path(d) / it["id"]
            for p, text in it["files"].items():
                (root / p).parent.mkdir(parents=True, exist_ok=True)
                (root / p).write_text(text)
            f = load_findings([{**it["finding"], "id": it["id"]}])[0]
            batch.append(ground(f, root, None, None))
        out = verify(batch, name, call, a.refute_at, a.confirm_at)
    for it, f in zip(items, out):
        f.pop("request", None)
        rows.append({"id": it["id"], "label": it["label"], "kind": it.get("kind"),
                     "true_severity": it.get("true_severity"), "status": f["status"],
                     "reason": f.get("reason"), "verdict": f.get("verdict"),
                     "severity": (f.get("severity") or {}).get("probabilities")})
    if a.out:
        Path(a.out).write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(json.dumps(metrics(rows, a.refute_at, a.confirm_at), indent=1))
    return 0


def metrics(rows: list[dict], refute_at: float = REFUTE_AT, confirm_at: float = CONFIRM_AT) -> dict:
    """Recall of real defects kept, share of false findings dropped, and accuracy at the thresholds."""
    real = [r for r in rows if r["label"] == "confirmed"]
    false = [r for r in rows if r["label"] == "refuted"]
    ungrounded = [r for r in rows if r["label"] == "ungrounded"]
    verified = [r for r in real + false if r.get("verdict")]

    def top(r):
        return max(r["verdict"], key=r["verdict"].get)

    return {
        "items": len(rows),
        "unverified": sum(r["status"] == "unverified" for r in rows),
        "real_kept": f"{sum(r['status'] != 'dropped' for r in real)}/{len(real)}",
        "real_confirmed": f"{sum(r['status'] == 'confirmed' for r in real)}/{len(real)}",
        "false_dropped": f"{sum(r['status'] == 'dropped' for r in false)}/{len(false)}",
        "false_confirmed": f"{sum(r['status'] == 'confirmed' for r in false)}/{len(false)}",
        "ungrounded_dropped": f"{sum(r['reason'] == 'ungrounded_code_quote' for r in ungrounded)}/{len(ungrounded)}",
        "top_answer_accuracy": round(sum(top(r) == r["label"] for r in verified) / len(verified), 3)
        if verified else None,
        "thresholds": {"refute_at": refute_at, "confirm_at": confirm_at},
    }


def _read(path: str):
    return json.load(sys.stdin if path == "-" else open(path))


def _write(rep: dict, fmt: str) -> None:
    print(markdown(rep) if fmt == "md" else json.dumps(rep, indent=1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def thresholds(p):
        p.add_argument("--refute-at", type=float, default=REFUTE_AT)
        p.add_argument("--confirm-at", type=float, default=CONFIRM_AT)

    def gate(p):
        p.add_argument("--fail-on", choices=LEVELS, help="exit 1 when a confirmed finding reaches this severity")
        p.add_argument("--severity-at", type=float, default=SEVERITY_AT)
        p.add_argument("--format", choices=["json", "md"], default="json")

    def source(p):
        p.add_argument("findings", help="findings JSON, or - for stdin")
        p.add_argument("--repo", default=".", help="checkout the findings' paths are relative to")
        p.add_argument("--ref", help="read files at this git ref instead of the working tree")
        p.add_argument("--diff", help="unified diff whose hunks are shown with each finding")

    p = sub.add_parser("run")
    source(p), thresholds(p), gate(p)
    p.add_argument("--transport", choices=["auto", *TRANSPORTS], default="auto")
    p = sub.add_parser("emit")
    source(p)
    p.add_argument("--out", required=True, help="batch file to pass to `apply`")
    p = sub.add_parser("apply")
    p.add_argument("batch", help="file written by emit --out")
    p.add_argument("answers", help="JSON object {finding id: decide reply}")
    thresholds(p), gate(p)
    p = sub.add_parser("eval")
    p.add_argument("items", help="labelled JSONL")
    p.add_argument("--out", help="per-item results JSONL")
    p.add_argument("--transport", choices=["auto", *TRANSPORTS], default="auto")
    thresholds(p)
    a = ap.parse_args(argv)
    try:
        return {"run": cmd_run, "emit": cmd_emit, "apply": cmd_apply, "eval": cmd_eval}[a.cmd](a)
    except VerifyError as e:
        print(f"verify: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
