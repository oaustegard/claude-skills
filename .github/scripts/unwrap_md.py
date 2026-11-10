#!/usr/bin/env python3
"""Join hard-wrapped Markdown paragraphs onto one line each.

GitHub renders a newline in a release body as a line break, unlike README
rendering, so a README wrapped at 80 columns shows ragged breaks when it is
pasted into release notes. This joins continuation lines of paragraphs and list
items, and leaves code fences, tables, headings, blockquotes, HTML and blank
lines as they are. Reads a file path (or stdin) and writes to stdout.
"""
import re
import sys

BLOCK_START = re.compile(r"^\s*[-*+]\s|^\s*#|^\s*>|^\s*\||^\s*<|^\s*(---|\*\*\*|___)\s*$")
ORDERED = re.compile(r"^\s*(\d+)[.)]\s")
LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s")


def starts_block(line: str, prev: str) -> bool:
    """True when `line` cannot continue the paragraph or item in `prev`.

    As in CommonMark, an ordered marker interrupts a paragraph only when it is
    1, so a wrapped line that happens to begin "56." stays in its paragraph.
    """
    if BLOCK_START.match(line):
        return True
    m = ORDERED.match(line)
    return bool(m) and (m.group(1) == "1" or bool(LIST_ITEM.match(prev)))


def unwrap(text: str) -> str:
    out: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or not stripped:
            out.append(line)
            continue
        prev = out[-1] if out else ""
        p = prev.strip()
        joinable = (
            p
            and not p.startswith(("```", "~~~", "#", "|", ">", "<"))
            and not re.match(r"^(---|\*\*\*|___)$", p)
            and not prev.endswith("  ")
            and not starts_block(line, prev)
        )
        if joinable:
            out[-1] = prev.rstrip() + " " + stripped
        else:
            out.append(line)
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            src = fh.read()
    else:
        src = sys.stdin.read()
    sys.stdout.write(unwrap(src))
