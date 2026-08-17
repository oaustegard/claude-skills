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
    ("negation-first", r"\b(?:is|are|was|were)\s+[a-z]{3,20},\s*not\s+[a-z]{3,20}\.", "X is A, not B — mid-paragraph, check the reader was holding B"),

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
    ("agency", r"(?<!\bI )(?<!\byou )(?<!\bwe )(?<!\bthey )\b(?:earns?|demands?|buys?|deserves?)\s+(?:its|their|the)\s+\w+", "abstraction earning something"),
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

    # ===== entries 24-36: encyclopedic and chatbot patterns ==================

    # --- copula avoidance ----------------------------------------------------
    ("copula", r"\b(?:serves?|stands?|acts?)\s+as\s+(?:a|an|the)\b", "serves as — use is"),
    ("copula", r"\bboasts?\s+(?:a|an|the|over|more than|some|\d)", "boasts — use has"),
    ("copula", r"\b(?:it|which|that|the\s+\w+)\s+features\s+(?:a|an|the|over|\d)", "features — use has"),
    ("copula", r"\b(?:represents|marks)\s+(?:a|an|the)\s+(?:shift|turning point|milestone|step|departure|moment)\b", "represents a shift"),

    # --- participle tail -----------------------------------------------------
    ("participle", r",\s*(?:highlight|underscor|emphasiz|reflect|symboliz|showcas|ensur|foster|cultivat|encompass|solidif|cement|underlin)\w*ing\b", "participle tail asserting significance"),
    ("participle", r",\s*contributing\s+to\b", "participle tail asserting significance"),

    # --- false range ---------------------------------------------------------
    ("false-range", r"\bfrom\s+[^,.;]{3,45}\s+to\s+[^,.;]{3,45},\s*from\s+", "stacked from-X-to-Y ranges"),
    ("false-range", r"\b(?:everything|anything|ranging)\s+from\b[^.]{0,60}\bto\b", "false range — list the items"),

    # --- inline-header list --------------------------------------------------
    ("list-shape", r"^\s*[-*+]\s+\*\*[^*\n]{2,45}\*\*\s*:", "inline-header bullet — the label restates the item"),
    ("list-shape", r"^\s*[-*+]\s+\*\*[^*\n]{2,45}:\*\*", "inline-header bullet — the label restates the item"),

    # --- chatbot residue -----------------------------------------------------
    ("chatbot", r"\b(?:great|excellent|good)\s+question\b", "chatbot residue"),
    ("chatbot", r"\byou'?re\s+absolutely\s+right\b", "chatbot residue"),
    ("chatbot", r"\bI\s+hope\s+this\s+helps\b", "chatbot residue"),
    ("chatbot", r"\blet\s+me\s+know\s+if\s+you'?d\b", "chatbot residue"),
    ("chatbot", r"\b(?:would|do)\s+you\s+(?:like|want)\s+me\s+to\b", "chatbot residue"),
    ("chatbot", r"\bwant\s+me\s+to\s+(?:give|show|expand|continue|explain)\b", "chatbot residue"),
    ("chatbot", r"\b(?:should|shall)\s+I\s+continue\b", "chatbot residue"),
    ("chatbot", r"^\s*(?:Certainly|Of course|Absolutely)[!,]", "chatbot residue"),
    ("chatbot", r"\bhere\s+is\s+an\s+overview\s+of\b", "chatbot residue"),

    # --- filler and hedge stacking -------------------------------------------
    ("filler", r"\bin\s+order\s+to\b", "in order to — use to"),
    ("filler", r"\bdue\s+to\s+the\s+fact\s+that\b", "due to the fact that — use because"),
    ("filler", r"\bat\s+this\s+point\s+in\s+time\b", "at this point in time — use now"),
    ("filler", r"\bin\s+the\s+event\s+that\b", "in the event that — use if"),
    ("filler", r"\bhas\s+the\s+ability\s+to\b", "has the ability to — use can"),
    ("filler", r"\bit\s+is\s+important\s+to\s+note\s+that\b", "delete the frame, keep the claim"),
    ("filler", r"\b(?:could|might|may|can)\s+(?:potentially|possibly|arguably|conceivably)\b", "stacked hedges — one carries the uncertainty"),
    ("filler", r"\bpotentially\s+possibly\b", "stacked hedges"),

    # --- speculative gap-filling ---------------------------------------------
    ("gap-fill", r"\bmaintains?\s+a\s+low\s+profile\b", "stock filler for an absent source"),
    ("gap-fill", r"\bkeeps?\s+(?:personal\s+)?details?\s+private\b", "stock filler for an absent source"),
    ("gap-fill", r"\b(?:is|are)\s+not\s+publicly\s+available\b", "say what is not known, or cut"),
    ("gap-fill", r"\bbased\s+on\s+(?:the\s+)?available\s+information\b", "meta-sentence about the search, not the subject"),
    ("gap-fill", r"\bas\s+of\s+my\s+last\s+(?:update|training)\b", "knowledge-cutoff disclaimer"),
    ("gap-fill", r"\bdetails\s+(?:about|are)[^.]{0,50}\b(?:limited|scarce|not\s+extensively)\b", "meta-sentence about the search"),
    ("gap-fill", r"\bit\s+is\s+believed\s+that\b", "unsourced guess"),
    ("gap-fill", r"\blikely\s+(?:grew\s+up|studied|began|started|attended)\b", "unsourced guess about a person"),

    # --- diff-anchored documentation -----------------------------------------
    ("diff-anchored", r"\b(?:was|were)\s+added\s+to\s+(?:replace|fix|handle|support)\b", "documents the change, not the thing"),
    ("diff-anchored", r"\bthe\s+(?:previous|old|former)\s+(?:approach|implementation|version|behaviour|behavior|method)\b", "documents the change, not the thing"),
    ("diff-anchored", r"\bhas\s+(?:since\s+)?been\s+(?:updated|changed|replaced|refactored)\s+to\b", "documents the change, not the thing"),
    ("diff-anchored", r"\bwe\s+now\s+(?:use|do|call|store|write)\b", "documents the change, not the thing"),

    # --- subjectless fragment ------------------------------------------------
    ("subjectless", r"\bNo\s+\w+(?:\s+\w+){0,2}\s+(?:needed|required)\s*[.!]", "subjectless claim — name the actor"),
    ("subjectless", r"\b(?:is|are)\s+\w+ed\s+automatically\b", "subjectless claim — who does it?"),

    # --- predicate-position hyphenation --------------------------------------
    ("hyphenation", r"\b(?:is|are|was|were|feels?|seems?)\s+(?:high-quality|cross-functional|data-driven|end-to-end|real-time|long-term|well-known|client-facing|decision-making|third-party|open-source)\b", "drop the hyphen after the noun"),
]

HTML_HEADING_RE = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.S | re.I)
HTML_MASTHEAD_RE = re.compile(
    r'<[^>]+class="[^"]*\b(subtitle|eyebrow|post-meta)\b[^"]*"[^>]*>(.*?)</', re.S | re.I)
HTML_BLOCK_RE = re.compile(r"<(p|li|figcaption|summary)\b[^>]*>(.*?)</\1>", re.S | re.I)
HTML_DROP_RE = re.compile(r"<(script|style|pre|code)\b.*?</\1>", re.S | re.I)
HTML_ENTITIES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
                 "&quot;": '"', "&#39;": "'", "&#8212;": "\u2014", "&mdash;": "\u2014"}


def looks_like_html(text: str) -> bool:
    head = text[:4000].lower()
    return "<html" in head or "<!doctype html" in head or bool(HTML_HEADING_RE.search(text))


def _detag(fragment: str) -> str:
    out = re.sub(r"<[^>]+>", " ", fragment)
    for ent, ch in HTML_ENTITIES.items():
        out = out.replace(ent, ch)
    return re.sub(r"\s+", " ", out).strip()


def html_to_lines(text: str) -> str:
    """Flatten HTML into the line-oriented prose the rules expect.

    Headings become markdown headings so the header rules see them, and
    composing-html's masthead classes are treated as headings too — a subtitle
    is a header by every test that matters. Line numbers refer to this
    flattened view, not the source file.
    """
    text = HTML_DROP_RE.sub(" ", text)
    parts: list[tuple[int, str]] = []
    for m in HTML_HEADING_RE.finditer(text):
        parts.append((m.start(), "#" * int(m.group(1)) + " " + _detag(m.group(2))))
    for m in HTML_MASTHEAD_RE.finditer(text):
        parts.append((m.start(), "## " + _detag(m.group(2))))
    for m in HTML_BLOCK_RE.finditer(text):
        parts.append((m.start(), _detag(m.group(2))))
    lines = [t for _, t in sorted(parts) if t.strip(" #")]
    return "\n\n".join(lines) + "\n"


HEADER_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
COY_HEADER_RE = re.compile(r"^(?:what|why|how)\b(?!.*\?$)", re.I)
VERDICT_HEADER_RE = re.compile(r"\b(?:is|are|isn'?t|aren'?t|was|wasn'?t|does|doesn'?t|actually|really|wrong|right|matters|counts)\b", re.I)

TITLE_CASE_SKIP = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "onto", "or", "over", "the", "to", "up", "via", "with",
}
# Emoji-presentation blocks only. An earlier version included U+2190-U+21FF and
# U+2300-U+23FF, so a plain -> arrow or a technical symbol reported as decoration.
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF☀-➿]|.️"
)

CATEGORY_ORDER = [
    "negation-first", "significance", "agency", "deferred-noun", "locator",
    "staging", "rhetorical-q", "self-grading", "humility", "throat-clearing",
    "rtfm", "dev-cliche", "slop", "editorializing", "time-inflation",
    "copula", "participle", "false-range", "list-shape", "chatbot", "filler",
    "gap-fill", "diff-anchored", "subjectless", "hyphenation",
    "header", "typography", "cadence", "density",
]

COMPILED = [(cat, re.compile(pat, re.I | re.M), note) for cat, pat, note in RULES]


def _blank_quoted(text: str) -> str:
    """Blank out quoted specimens, preserving line numbering."""
    def blank(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")

    # Blockquotes and table rows go first. Doing this after the span pass let a
    # bold marker inside a table cell mis-pair the italic regex across lines,
    # leaving the row's own specimens visible to the scanner.
    text = "\n".join("" if ln.lstrip().startswith((">", "|")) else ln
                     for ln in text.splitlines())
    text = re.sub(r"```.*?```", blank, text, flags=re.S)       # fenced code
    text = re.sub(r"`[^`\n]+`", blank, text)                   # inline code span
    text = re.sub(r"(?<!\*)\*[^*]+\*(?!\*)", blank, text)      # *italic*, may wrap lines
    return re.sub(r"<q>.*?</q>", blank, text, flags=re.S)


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
            words = title.split()
            minor = [w for w in words[1:] if w.lower() not in TITLE_CASE_SKIP]
            if len(words) > 3 and minor and all(
                w[:1].isupper() and not w.isupper() for w in minor
            ):
                hits.append({"line": i, "category": "typography",
                             "note": "Title Case heading — sentence case unless the document says otherwise",
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
    # headings, table rows and list bullets are not sentences
    body = "\n".join(ln for ln in body.splitlines()
                      if not ln.lstrip().startswith(("#", "|", "-", "*", ">")))
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

    curly = len(re.findall(r"[“”‘’]", body))
    if curly:
        out.append({"line": 0, "category": "typography",
                    "note": f"{curly} curly quote characters — straight quotes in anything a program reads. "
                            "Not a tell on its own: most editors curl by default",
                    "match": "curly quotes"})

    emoji = EMOJI_RE.findall(text)
    if emoji:
        out.append({"line": 0, "category": "typography",
                    "note": f"{len(emoji)} emoji — decoration on headings and bullets is a tell "
                            "unless the document already uses them",
                    "match": "".join(sorted(set(emoji))[:12])})

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
    ap.add_argument("--skip-quoted", action="store_true",
                    help="ignore blockquotes, *italic* spans and table cells — use on docs that quote bad prose as specimens")
    ap.add_argument("--html", action="store_true",
                    help="force HTML flattening (headings, masthead subtitle, block prose)")
    ap.add_argument("--no-html", action="store_true", help="never flatten; scan the raw source")
    args = ap.parse_args()

    text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    if args.html or (not args.no_html and looks_like_html(text)):
        text = html_to_lines(text)
    if args.skip_quoted:
        text = _blank_quoted(text)

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
