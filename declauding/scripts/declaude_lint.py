#!/usr/bin/env python3
"""Mechanical scan for LLM prose tics.

Finds candidates. Does not decide. Every hit still needs the sentence-level
test in references/register.md, and the structural tics (fragment cadence,
drama line breaks, staged paragraph shape) are only partly reachable by regex.
A clean report means nothing on its own.

    python3 declaude_lint.py DRAFT.md [--json] [--quiet-slop]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# (category, regex, note). Case-insensitive unless the pattern needs case.
RULES: list[tuple[str, str, str]] = [
    # --- negation-first -----------------------------------------------------
    ("negation-first", r"\b(?:is|it's|its|was|it was)\s+not\s+(?:that\s+)?[^.;]{2,60}[.;—-]\s*(?:it|that)\s+(?:is|was|'s)\b", "is-not / it-is pair"),
    ("negation-first", r"\bnot\s+because\b[^.]{0,80}—\s*because\b", "not-because / because"),
    ("negation-first", r"\b(?:doesn't|does not|didn't|did not)\s+just\b[^.]{0,60}\b(?:it|they)\b", "doesn't just X, it Y's"),
    ("negation-first", r"\bthe\s+(?:problem|failure|issue|point|question|bug|risk)\s+(?:wasn't|isn't|was not|is not)\b", "the problem wasn't X"),
    ("negation-first", r"[.!?]\s+Not\s+(?:that|because|a|an|the)\b[^.]{0,60}\.", "trailing 'Not X.' fragment"),
    ("negation-first", r",\s*not\s+[a-z][^.]{0,40}\.\s*$", "X, not Y closer"),

    # --- significance designation -------------------------------------------
    ("significance", r"\bthe\s+(?:real|actual|true|useful|interesting|important|key)\s+(?:question|problem|issue|point|reason|answer|finding|story|move|tool|test|variable|number)\b", "the real/actual X"),
    ("significance", r"\bthe\s+(?:part|thing|bit|piece|detail|one|leg|row|line|number|question)\s+that\s+(?:matters|counts|transfers|makes the point|does the work|answers|explains)\b", "the part that matters"),
    ("significance", r"\b(?:here'?s|this is)\s+(?:the thing|where it gets interesting|what)\b", "here's the thing"),
    ("significance", r"\band\s+(?:that'?s|it has)\s+(?:the interesting part|a name here)\b", "manufactured reveal"),
    ("significance", r"\bthe\s+(?:one|only)\s+thing\s+(?:nobody|no one)\b", "the one thing nobody"),
    ("significance", r"\b(?:most|more)\s+(?:interesting|telling|revealing|surprising)\s+(?:part|thing|number|finding)\b", "significance tag"),
    ("significance", r"\bNobody\s+(?:had\s+)?(?:checked|noticed|asked|mentioned|said|looked)\b", "unfalsifiable 'nobody' claim — earned only with a named mechanism"),

    # --- abstraction agency --------------------------------------------------
    ("agency", r"\b(?:the\s+)?(?:table|chart|graph|data|numbers?|median|mean|metric|figure|plot|log|code|result|headline)\s+(?:shows?|hides?|tells?|reveals?|says?|proves?|admits?|knows?|wants?)\b", "inanimate subject acting"),
    ("agency", r"\b(?:is|are|was|were)\s+doing\s+the\s+work\b", "X is doing the work"),
    ("agency", r"\b(?:earns?|demands?|wants?|buys?|deserves?)\s+(?:its|their|the)\s+\w+", "abstraction earning something"),
    ("agency", r"\b(?:truncation|quantization|rescoring|compression|optimization|abstraction|complexity|scalability)\s+(?:cuts?|adds?|breaks?|solves?|reranks?|is a concern)\b", "nominalization as agent"),
    ("agency", r"\b(?:about to|going to)\s+discover\b", "tool personified"),

    # --- deferred noun -------------------------------------------------------
    ("deferred-noun", r"\bOne\s+thing\s+(?:is|isn't|is not|that)\b", "One thing ..."),
    ("deferred-noun", r"\bThe\s+(?:second|third|fourth|fifth|sixth|seventh|other|last)\s+(?:is|isn't|is not|does|doesn't)\b\s*[.,]", "pointer instead of name"),
    ("deferred-noun", r"\bThere\s+(?:was|is)\s+(?:just\s+)?one\s+(?:problem|catch|issue|wrinkle)\b", "there was just one problem"),

    # --- structural-metaphor locator ----------------------------------------
    ("locator", r"\bthe\s+(?:seam|hinge|joint|fault[- ]line|crux|linchpin|leg|place)\s+where\b", "structural-metaphor locator"),
    ("locator", r"\bload[- ]bearing\b", "load-bearing as metaphor"),

    # --- suspense / staging --------------------------------------------------
    ("staging", r"\b(?:but\s+)?here'?s\s+where\s+it\s+gets\b", "here's where it gets"),
    ("staging", r"\bwhat\s+(?:I|we|you)\s+(?:didn't|did not)\s+(?:realize|know|expect)\b", "movie-trailer voiceover"),
    ("staging", r"\bthis\s+is\s+the\s+story\s+of\b", "trailer opener"),
    ("staging", r"\band\s+that'?s\s+(?:when|where|why)\b", "and that's when"),
    ("staging", r"^\s*(?:So|Then|And)\s+(?:the|here|now)\b[^.\n]{0,40}:\s*$", "colon-staged section lead"),
    ("staging", r"\bthe\s+(?:defensible|honest|short|real)\s+(?:statement|answer|version)\s*:", "noun-phrase colon stage"),

    # --- rhetorical question -------------------------------------------------
    ("rhetorical-q", r"^\s*(?:So\s+)?(?:how|why|what|where|when|does|is|can|should)\b[^?\n]{0,70}\?\s*$", "standalone rhetorical question — check if you answer your own question next"),

    # --- self-grading --------------------------------------------------------
    ("self-grading", r"\b(?:earned,?\s+not\s+asserted|not\s+a\s+relabel|to be clear,\s*this is)\b", "grading own rigor"),
    ("self-grading", r"\b(?:that|this)\s+is\s+what\s+the\s+(?:data|numbers?|table|evidence)\s+shows?\b", "that is what the data shows"),
    ("self-grading", r"\b(?:it'?s|it is)\s+(?:worth|important)\s+(?:noting|mentioning|pointing out)\b", "worth noting"),
    ("self-grading", r"\ba\s+distinction\s+worth\b", "grading the distinction"),
    ("self-grading", r"\bgenuinely\s+(?:useful|interesting|hard|novel|different|new)\b", "intensifier as self-grade"),

    # --- performed humility --------------------------------------------------
    ("humility", r"\b(?:better|sharper|cleaner)\s+than\s+mine\b", "ranking others above yourself"),
    ("humility", r"\b(?:this\s+might\s+be\s+a\s+small\s+thing|probably\s+nobody\s+cares|not\s+sure\s+this\s+is\s+worth)\b", "apologizing for the piece"),
    ("humility", r"\bclassic\s+me\b", "self-deprecation as performance"),

    # --- throat-clearing / process narration ---------------------------------
    ("throat-clearing", r"\b(?:in this (?:post|article|piece),?\s*(?:I|we)'?ll|I want to talk about|let me explain|first,? some background|before I get into)\b", "preamble"),
    ("throat-clearing", r"\b(?:let me|I'?ll)\s+(?:consult|check|search|pull up|recall)\s+my\b", "AI self-narration"),

    # --- RTFM ----------------------------------------------------------------
    ("rtfm", r"\b(?:it turns out|I finally (?:discovered|realized|found)|hidden in the|buried in the (?:docs|api))\b", "RTFM as revelation"),

    # --- dev cliché ----------------------------------------------------------
    ("dev-cliche", r"\b(?:footgun|shot itself in the foot|rabbit hole|yak[- ]shav\w*|belt[- ]and[- ]suspenders|moving the needle|first[- ]class citizen|under the hood|just works|sane defaults|almost killed it)\b", "generic developer vocabulary"),

    # --- slop ----------------------------------------------------------------
    ("slop", r"\b(?:delve|tapestry|testament to|navigate the complexities|in today'?s fast[- ]paced|realm of|robust|seamless|leverage|utilize|crucial|pivotal|myriad|plethora|elevate|unlock the|harness the|embark|dive deep|at the end of the day)\b", "slop vocabulary"),

    # --- editorializing ------------------------------------------------------
    ("editorializing", r"\b(?:collapse[sd]?|catastrophic|dramatic(?:ally)?|brutal|staggering|remarkable|impressive)\b", "check the number justifies the adjective"),

    # --- time inflation ------------------------------------------------------
    ("time-inflation", r"\b(?:a (?:month|few months|while) ago|for a long time|all year|recently|these days)\b", "ground the duration or drop it"),
    # --- aphoristic closer ---------------------------------------------------
    ("aphorism", r"\bthe\s+kind\s+of\s+\w+\s+that\b[^.]{0,60}\band\s+is\s+not\b", "X that looks like Y and is not"),
    ("aphorism", r"\bthe\s+\w+\s+that\s+looks\s+like\s+\w+", "X that looks like Y"),
    ("aphorism", r"\b(?:by\s+a\s+wide\s+margin|was\s+the\s+move|is\s+the\s+whole\s+(?:point|bug|story))\b", "quotable closer"),

    # --- staging (more) ------------------------------------------------------
    ("staging", r"\b(?:here|this)\s+is\s+what\s+[^.]{0,60}\blooks?\s+like\b", "here is what X looks like"),
    ("staging", r"\bthen\s+the\s+(?:useful|real|interesting)\s+question\b", "heralding your own question"),
]

HEADER_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
COY_HEADER_RE = re.compile(r"^(?:what|why|how)\b(?!.*\?$)", re.I)
VERDICT_HEADER_RE = re.compile(r"\b(?:is|are|isn'?t|aren'?t|was|wasn'?t|does|doesn'?t|actually|really|wrong|right|matters|counts)\b", re.I)

CATEGORY_ORDER = [
    "negation-first", "significance", "agency", "deferred-noun", "locator",
    "staging", "rhetorical-q", "self-grading", "humility", "throat-clearing",
    "rtfm", "dev-cliche", "slop", "editorializing", "time-inflation",
    "header", "cadence", "density",
]

COMPILED = [(cat, re.compile(pat, re.I | re.M), note) for cat, pat, note in RULES]


def scan_lines(text: str) -> list[dict]:
    hits: list[dict] = []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        for cat, rx, note in COMPILED:
            for m in rx.finditer(line):
                hits.append({
                    "line": i, "category": cat, "note": note,
                    "match": m.group(0).strip()[:90],
                })

        # headers
        h = HEADER_RE.match(line)
        if h:
            title = h.group(2).strip().rstrip("#").strip()
            if "," in title:
                hits.append({"line": i, "category": "header",
                             "note": "comma-clause header — no real person puts sentence clauses in a headline",
                             "match": title[:90]})
            if COY_HEADER_RE.match(title):
                hits.append({"line": i, "category": "header",
                             "note": "coy header — could top three different sections; name the content",
                             "match": title[:90]})
            elif not title.endswith("?") and VERDICT_HEADER_RE.search(title) and len(title.split()) > 3:
                hits.append({"line": i, "category": "header",
                             "note": "thesis-shaped header — states a verdict instead of labelling",
                             "match": title[:90]})

        # drama line break: very short standalone paragraph
        if stripped and not stripped.startswith(("#", "-", "*", ">", "|", "`")):
            prev_blank = i == 1 or not lines[i - 2].strip()
            next_blank = i >= len(lines) or not lines[i].strip()
            words = len(stripped.split())
            if prev_blank and next_blank and words <= 8 and stripped.endswith((".", "!")):
                hits.append({"line": i, "category": "cadence",
                             "note": "one-line paragraph — gravitas beat unless it is a real pivot",
                             "match": stripped[:90]})

    hits.extend(_fragment_runs(text))
    return hits


def _fragment_runs(text: str) -> list[dict]:
    """Three or more short sentences in a row inside one paragraph."""
    out = []
    line_no = 1
    for para in re.split(r"\n\s*\n", text):
        n = para.count("\n") + 1
        if not para.strip().startswith(("#", "-", "*", ">", "|", "`")):
            sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", para.strip()) if x.strip()]
            run = 0
            for x in sents:
                run = run + 1 if len(x.split()) <= 8 else 0
                if run == 3:
                    out.append({"line": line_no, "category": "cadence",
                                "note": "three or more short sentences in a row — fragment cadence, write it as one sentence",
                                "match": para.strip()[:90]})
                    break
        line_no += n + 1
    return out


def scan_density(text: str) -> list[dict]:
    out = []
    body = re.sub(r"```.*?```", "", text, flags=re.S)
    words = len(body.split()) or 1

    dashes = len(re.findall(r"—|(?<= )--(?= )", body))
    per150 = dashes / words * 150
    if per150 > 1.0:
        out.append({"line": 0, "category": "density",
                    "note": f"{dashes} em-dashes in {words} words ({per150:.1f} per 150) — above ~1.0 reads machine-written",
                    "match": "em-dash density"})

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    frags = [s for s in sentences if 1 <= len(s.split()) <= 5 and not s.startswith(("#", "-", "|"))]
    if sentences and len(frags) / len(sentences) > 0.12:
        out.append({"line": 0, "category": "density",
                    "note": f"{len(frags)} of {len(sentences)} sentences are <=5 words — check for fragment cadence",
                    "match": "fragment density"})

    lens = [len(s.split()) for s in sentences]
    if len(lens) > 20:
        mean = sum(lens) / len(lens)
        var = sum((x - mean) ** 2 for x in lens) / len(lens)
        if var ** 0.5 < 5:
            out.append({"line": 0, "category": "density",
                        "note": f"sentence-length sd {var ** 0.5:.1f} — uniform length is its own tell; vary by content",
                        "match": "sentence monotony"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="file to scan, or - for stdin")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet-slop", action="store_true", help="hide the slop/editorializing/time categories")
    args = ap.parse_args()

    text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")

    hits = scan_lines(text) + scan_density(text)
    if args.quiet_slop:
        hits = [h for h in hits if h["category"] not in {"slop", "editorializing", "time-inflation"}]

    hits.sort(key=lambda h: (CATEGORY_ORDER.index(h["category"]) if h["category"] in CATEGORY_ORDER else 99, h["line"]))

    if args.json:
        print(json.dumps({"hits": hits, "total": len(hits)}, indent=2))
        return 1 if hits else 0

    if not hits:
        print("no lexical tells found — this says nothing about the structural tics; run the sentence pass anyway")
        return 0

    counts: dict[str, int] = {}
    for h in hits:
        counts[h["category"]] = counts.get(h["category"], 0) + 1

    print(f"{len(hits)} candidates in {len(counts)} categories\n")
    current = None
    for h in hits:
        if h["category"] != current:
            current = h["category"]
            print(f"\n[{current}]  ({counts[current]})")
        loc = f"L{h['line']}" if h["line"] else "  —"
        print(f"  {loc:>6}  {h['match']}")
        print(f"          {h['note']}")

    print("\nCandidates, not verdicts. Check each against references/register.md,")
    print("and note that no regex reaches staged paragraph shape or a staged closer.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
