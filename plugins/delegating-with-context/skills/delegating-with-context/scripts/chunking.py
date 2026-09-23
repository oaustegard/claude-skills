"""Split a Claude Code session transcript (JSONL) into context chunks and scrub secrets.

A chunk is one user message, one assistant text block, or one tool call paired
with its result. Harness-injected user text (starting with '<') is skipped.
"""
import glob, json, os, re

SECRET_PATTERNS = [re.compile(p) for p in (
    r"ghp_[A-Za-z0-9]{36}", r"github_pat_[A-Za-z0-9_]{20,}", r"gh[osu]_[A-Za-z0-9]{36}",
    r"sk-[A-Za-z0-9_\-]{20,}", r"AKIA[0-9A-Z]{16}", r"eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}",
    r"xox[abp]-[A-Za-z0-9-]{10,}")]
SECRET_NAME = re.compile(r"TOKEN|KEY|SECRET|PASSWORD|PASSWD|_PAT\b|CREDENTIAL", re.I)


def _secret_values():
    vals = {v for k, v in os.environ.items() if SECRET_NAME.search(k) and len(v) >= 12}
    for f in glob.glob("/mnt/project/*.env"):
        for line in open(f, errors="ignore"):
            k, _, v = line.strip().removeprefix("export ").partition("=")
            v = v.strip().strip("'\"")
            if SECRET_NAME.search(k) and len(v) >= 12:
                vals.add(v)
    return sorted(vals, key=len, reverse=True)


_VALUES = None


def scrub(text):
    """Return (clean_text, n_replacements). Never prints or returns a secret."""
    global _VALUES
    if _VALUES is None:
        _VALUES = _secret_values()
    n = 0
    for v in _VALUES:
        if v in text:
            n += text.count(v); text = text.replace(v, "[REDACTED]")
    for p in SECRET_PATTERNS:
        text, k = p.subn("[REDACTED]", text); n += k
    return text, n


def _text(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            out.append(b.get("text", ""))
        elif b.get("type") == "tool_result":
            c = b.get("content")
            out.append(c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict)))
    return "\n".join(out)


def chunk_transcript(path):
    """Return (chunks, n_scrubbed). Each chunk: id, kind, text/tool/input/result, prompt, chars."""
    chunks, pending, prompt, scrubbed = [], {}, "", 0
    for line in open(path, errors="ignore"):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        t, c = r.get("type"), (r.get("message") or {}).get("content")
        if t == "user":
            blocks = [{"type": "text", "text": c}] if isinstance(c, str) else (c or [])
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                    ch = pending.pop(b["tool_use_id"]); ch["result"] = _text([b]); chunks.append(ch)
                elif b.get("type") == "text" and b.get("text", "").strip() and not b["text"].lstrip().startswith("<"):
                    # isMeta marks harness-injected user turns: skill bodies, stop-hook
                    # feedback, peer messages. They are scored like any chunk but are
                    # not the user's words, so they are never force-kept.
                    if r.get("isMeta"):
                        chunks.append({"kind": "harness", "text": b["text"], "prompt": prompt})
                        continue
                    prompt = b["text"][:400]
                    chunks.append({"kind": "user", "text": b["text"], "prompt": prompt})
        elif t == "assistant" and isinstance(c, list):
            for b in c:
                if b.get("type") == "text" and b.get("text", "").strip():
                    chunks.append({"kind": "assistant", "text": b["text"], "prompt": prompt})
                elif b.get("type") == "tool_use":
                    pending[b["id"]] = {"kind": "tool", "tool": b.get("name", "?"),
                                        "input": json.dumps(b.get("input", {}), ensure_ascii=False), "prompt": prompt}
    for i, ch in enumerate(chunks):
        ch["id"] = i
        for k in ("text", "input", "result", "prompt"):
            if k in ch:
                ch[k], n = scrub(ch[k]); scrubbed += n
        ch["chars"] = sum(len(ch.get(k, "")) for k in ("text", "input", "result"))
    return chunks, scrubbed


def render(chunk):
    """Full-fidelity text of a chunk, as a subagent would receive it."""
    if chunk["kind"] == "tool":
        return f"[{chunk['id']}] TOOL {chunk['tool']} input: {chunk['input']}\nresult: {chunk.get('result', '')}"
    who = {"user": "USER", "harness": "HARNESS"}.get(chunk["kind"], "ASSISTANT")
    return f"[{chunk['id']}] {who}: {chunk['text']}"
