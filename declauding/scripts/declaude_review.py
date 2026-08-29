#!/usr/bin/env python3
"""Stage 2 of the register pass: judgment on the slots regex cannot reach.

declaude_lint.py is lexical. It scans for phrases. The tics it cannot see are
structural — a header that states a verdict, a closer that paraphrases the
subtext above it, an isolated line used as a drum roll. Those need a reader.

This script extracts only the structural slots (title, subtitle, every header,
the opening sentence, each section's closing sentence, isolated one-sentence
paragraphs) and sends them to a model with the matching entries from
references/register.md. Slots rather than the whole document, because that is
where the structural tics live and a small payload is cheap enough to run on
every draft.

    python3 declaude_review.py DRAFT.md                 # judge (needs an API key)
    python3 declaude_review.py DRAFT.html --emit-prompt # print the prompt instead
    python3 declaude_review.py DRAFT.md --slots         # show what was extracted

Keys, in order of preference: GEMINI_API_KEY, then ANTHROPIC_API_KEY. With
neither set the script falls back to --emit-prompt and says so.

Do not run this on your own draft in the context that wrote it. The judgment
wants a reader who did not choose the words.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REGISTER = Path(__file__).resolve().parent.parent / "references" / "register.md"

# register.md entries that describe structural tics. Loaded verbatim so the
# catalogue stays single-source; adding an entry there needs no edit here.
# 26 is here because stage 1 detects triads deterministically but cannot judge
# whether the content had three things, and a closer is where the padded ones
# land. 47 is here for the same reason: an exhaustive negative is earned when its
# scope is named, and only reading the surrounding sentences says whether it is.
# 43 to 46 are lexical and stage 1 reaches them.
STRUCTURAL_ENTRIES = (1, 2, 3, 7, 9, 12, 13, 26, 47, 50, 51, 52)
# 50 to 52 need the slots this script extracts and stage 1 cannot judge: a
# retroactive grade is only visible against the passage it grades, a totalizing
# claim is earned when the set is named nearby, and an obituary headline is a
# header. 48 and 49 are lexical and stage 1 reaches them.

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
TAG = re.compile(r"<[^>]+>")


def strip_tags(s: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&#8212;", "—"))
    return re.sub(r"[ \t]+", " ", s).strip()


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_END.split(text.strip()) if s.strip()]


def load_register(entries=STRUCTURAL_ENTRIES) -> str:
    if not REGISTER.exists():
        return ""
    blocks, current, keep = [], [], False
    for line in REGISTER.read_text(encoding="utf-8").splitlines():
        # Any h1/h2 ends the current entry. Matching only numbered headings let
        # the file's trailing "Quick self-check" section ride along with the
        # last entry whenever that entry was selected.
        if line.startswith(("## ", "# ")):
            m = re.match(r"^## (\d+)\.", line)
            if keep and current:
                blocks.append("\n".join(current).strip())
            current, keep = [], bool(m) and int(m.group(1)) in entries
        if keep:
            current.append(line)
    if keep and current:
        blocks.append("\n".join(current).strip())
    return "\n\n".join(blocks)


def extract_html(text: str) -> list[tuple[str, str]]:
    slots: list[tuple[str, str]] = []
    for cls, label in (("eyebrow", "eyebrow"), ("subtitle", "subtitle")):
        for m in re.finditer(rf'class="[^"]*\b{cls}\b[^"]*"[^>]*>(.*?)<', text, re.S):
            if strip_tags(m.group(1)):
                slots.append((label, strip_tags(m.group(1))))
    for m in re.finditer(r"<h([1-6])[^>]*>(.*?)</h\1>", text, re.S | re.I):
        slots.append((f"h{m.group(1)}", strip_tags(m.group(2))))
    paras = [strip_tags(m.group(1)) for m in
             re.finditer(r"<p[^>]*>(.*?)</p>", text, re.S | re.I)]
    slots += _prose_slots([p for p in paras if p])
    return slots


def extract_markdown(text: str) -> list[tuple[str, str]]:
    slots: list[tuple[str, str]] = []
    body: list[str] = []
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if fm:
        for line in fm.group(1).splitlines():
            if line.lower().startswith(("title:", "subtitle:", "description:")):
                k, _, v = line.partition(":")
                slots.append((k.strip().lower(), v.strip().strip("\"'")))
        text = text[fm.end():]
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            slots.append((f"h{len(m.group(1))}", m.group(2).strip()))
        else:
            body.append(line)
    paras = [p.strip().replace("\n", " ") for p in "\n".join(body).split("\n\n")]
    slots += _prose_slots([p for p in paras if p and not p.startswith(("|", ">", "-", "*"))])
    return slots


def _prose_slots(paras: list[str]) -> list[tuple[str, str]]:
    """Opening sentence, last sentence of the final paragraph, isolated lines."""
    out: list[tuple[str, str]] = []
    if not paras:
        return out
    first = sentences(paras[0])
    if first:
        out.append(("opening", first[0]))
    last = sentences(paras[-1])
    if last:
        out.append(("closer", last[-1]))
    for p in paras[1:-1]:
        s = sentences(p)
        if len(s) == 1 and len(s[0].split()) <= 18:
            out.append(("isolated-line", s[0]))
    return out


def extract(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    is_html = path.suffix.lower() in {".html", ".htm"} or "<html" in text[:2000].lower()
    slots = extract_html(text) if is_html else extract_markdown(text)
    seen, uniq = set(), []
    for kind, value in slots:
        if value and (kind, value) not in seen:
            seen.add((kind, value))
            uniq.append((kind, value))
    return uniq


def build_prompt(slots: list[tuple[str, str]]) -> str:
    listing = "\n".join(f"{i + 1}. [{k}] {v}" for i, (k, v) in enumerate(slots))
    return f"""You are checking prose for structural register tics. The catalogue below is
the standard; apply it and nothing else.

{load_register()}

Below are the structural slots pulled from a draft: its headers, its opening
and closing sentences, and any isolated one-sentence paragraphs. You are not
seeing the body prose, and you do not need it — judge each slot on its own
terms.

For a header, apply the table-of-contents test: read it alone. Does it name
what the section contains, or does it state a verdict, hide its contents, or
carry a comma-clause? Only the first is acceptable. A header you could agree or
disagree with is a verdict, however plainly it is worded — "Sales fell in Q3"
asserts, "Q3 sales" labels. A comma joining parts of a proper name is fine; a
comma introducing an appositive, participle or relative clause is not.

For a closer, ask whether it paraphrases the subtext of what came before or
compresses the piece into a contrast or a moral. Either is a button; cut it.

For an isolated line, ask whether it marks a real pivot — new actor, category
shift, time jump — or supplies a drum roll.

SLOTS:
{listing}

Return JSON only, no prose around it, no code fences:
{{"findings": [{{"n": <slot number>, "tic": "<catalogue name>", "why": "<one sentence>", "fix": "<the replacement text>"}}]}}

Return an empty findings list if every slot is clean. Do not invent facts: a
suggested fix may only rearrange or delete words already present, or use a
plainly descriptive label drawn from the slot itself."""


def call_gemini(prompt: str, key: str) -> str:
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-3.6-flash:generateContent?key={key}")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_anthropic(prompt: str, key: str) -> str:
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": "claude-sonnet-4-6", "max_tokens": 2000,
                         "temperature": 0,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data["content"])


def parse_findings(raw: str) -> list[dict]:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON object in model reply: {raw[:200]}")
    return json.loads(raw[start:end + 1]).get("findings", [])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="file to review (.md or .html)")
    ap.add_argument("--emit-prompt", action="store_true", help="print the prompt, do not call a model")
    ap.add_argument("--slots", action="store_true", help="print the extracted slots and stop")
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    args = ap.parse_args()

    slots = extract(Path(args.path))
    if not slots:
        print("no structural slots found — check the file parsed as expected")
        return 0

    if args.slots:
        for i, (k, v) in enumerate(slots, 1):
            print(f"{i:>3}. [{k}] {v}")
        return 0

    prompt = build_prompt(slots)
    gem, ant = os.environ.get("GEMINI_API_KEY"), os.environ.get("ANTHROPIC_API_KEY")
    if args.emit_prompt or not (gem or ant):
        if not (gem or ant) and not args.emit_prompt:
            print("no GEMINI_API_KEY or ANTHROPIC_API_KEY set — emitting the prompt "
                  "for a separate call instead\n", file=sys.stderr)
        print(prompt)
        return 0

    raw = call_gemini(prompt, gem) if gem else call_anthropic(prompt, ant)
    findings = parse_findings(raw)

    if args.json:
        print(json.dumps({"slots": [{"n": i + 1, "kind": k, "text": v}
                                    for i, (k, v) in enumerate(slots)],
                          "findings": findings}, indent=2))
        return 1 if findings else 0

    if not findings:
        print(f"{len(slots)} slots reviewed, none flagged")
        return 0

    print(f"{len(findings)} of {len(slots)} slots flagged\n")
    for f in findings:
        n = f.get("n", 0)
        kind, text = slots[n - 1] if 1 <= n <= len(slots) else ("?", "?")
        print(f"  [{kind}] {text}")
        print(f"      {f.get('tic', '?')} — {f.get('why', '')}")
        print(f"      -> {f.get('fix', '')}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
