#!/usr/bin/env python3
"""Fresh eyes: put reader-facing text in front of a reader who never saw its earlier version.

Text written right after a change takes its focus from the change: a detail that only means something against the
old version ("pick your options here, upright", after the options moved off a sideways screen), the fix described
where the reader needs the behaviour, one section updated while another still describes the old flow. The writer
knows the old version and cannot see this. A reader who never saw it can. The writer cannot be that reader, so the
read goes to a subagent.

    python3 fresh_eyes.py packet FILE [FILE ...]   # write a packet of these files, print its path and the prompt
    python3 fresh_eyes.py hook                       # Stop hook: reads the hook JSON on stdin

As a Stop hook (declauding's plugin wires it): when the turn changed visible prose in a .md or .html file, the stop is
blocked once with a packet of the changed sections as they now stand and the prompt to send a subagent. A read
counts only if its Agent prompt carries MARK and was sent after the last write to those files. Changed files are
found through git where they sit in a repository (commits made since the turn began, and uncommitted edits written
since then, so any route counts: an edit tool, a script, a subagent) and by write time elsewhere, such as a Cowork
session's outputs. Left out: history, whose subject is the change (CHANGELOG, HISTORY, NEWS, failure-modes.md,
transcripts, memory files, anything under a Log, Changelog, History or Release notes heading); working records
(ERRORS.md, PLAN.md); generated text (_site/, tools.html, blog/index.html, feed.xml, <!--gen:NAME--> regions); edits
that change no visible prose; and changes under MIN_PROSE characters, such as a typo or a link. Every run appends a
line to LOG, which is how to tell whether the hook fires in a given environment. Fails open: an error never blocks.
Standard library only.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MARK = "FRESH-EYES READ"
MIN_PROSE = 20
FILE_CAP, PACKET_CAP, HTML_WINDOW = 30000, 80000, 25
OUT_DIR = Path(os.environ.get("FRESH_EYES_OUT", "/tmp/fresh-eyes"))
LOG = Path(os.environ.get("FRESH_EYES_LOG", os.path.expanduser("~/.claude/fresh-eyes-log.jsonl")))
REPO_ROOTS = ("/home/user", "/home/user/claude-workspace/.spokes", "/workspace", "/home/claude")
SCAN_ROOTS = ("/mnt/user-data/outputs", "/home/claude")       # where a session without a repository writes files
SCAN_DEPTH, SCAN_SECONDS = 4, 2.0

_DOC = re.compile(r"\.(?:md|markdown|html?)$", re.I)
_SKIP = re.compile(r"(?:^|/)(?:CHANGELOG|CHANGES|HISTORY|NEWS)[^/]*$|(?:^|/)(?:ERRORS|PLAN)\.md$|(?:^|/)failure-modes\.md$"
                   r"|(?:^|/)transcripts?/|(?:^|/)memory/|(?:^|/)_site/|(?:^|/)tools\.html$|(?:^|/)blog/index\.html$"
                   r"|(?:^|/)feed\.xml$|(?:^|/)node_modules/", re.I)
_HISTORY_HEAD = re.compile(r"^#{1,3}\s+(?:Log|Changelog|Change log|History|Release notes)\b", re.I)
_HEAD = re.compile(r"^#{1,6}\s")
GLOBS = ["--", "*.md", "*.markdown", "*.html", "*.htm"]
_PRUNE = {".git", "node_modules", ".venv", "venv", "__pycache__", "_site", ".cache"}


# ------------------------------------------------------------------ text

def prose(text: str, html: bool) -> str:
    """Visible prose: code spans and fences out; for HTML, scripts, styles, comments and tags out."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", text)
    if html:
        text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
        if "<" not in text and re.search(r"[;{}]\s*$|=>|\bconst |\bfunction\b|\blet ", text, re.M):
            return ""                                   # lines inside a script block, not page copy
        text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def history_start(text: str) -> int | None:
    """1-based line number of the first Log/Changelog/History heading, or None."""
    for i, line in enumerate(text.splitlines(), 1):
        if _HISTORY_HEAD.match(line):
            return i
    return None


def code_lines(text: str) -> set[int]:
    """Line numbers inside <script> and <style> blocks of an HTML file (the tag lines included)."""
    out, inside = set(), None
    for i, line in enumerate(text.splitlines(), 1):
        if inside is None:
            m = re.search(r"<(script|style)\b", line, re.I)
            if m and not re.search(rf"</{m.group(1)}>", line[m.end():], re.I):
                inside = m.group(1).lower()
                out.add(i)
            continue
        out.add(i)
        if re.search(rf"</{inside}>", line, re.I):
            inside = None
    return out


def generated_lines(text: str) -> set[int]:
    """Line numbers inside <!--gen:NAME--> ... <!--/gen:NAME--> regions, which a build script writes."""
    out, start = set(), None
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(r"<!--gen:[\w-]+-->", line):
            start = i
        if start is not None:
            out.add(i)
        if re.search(r"<!--/gen:[\w-]+-->", line):
            start = None
    return out


def changed_lines(patch: str, path_text) -> dict[str, tuple[set[int], int]]:
    """From a -U0 unified diff: {path: (new-file line numbers whose prose changed, added prose chars)}.

    path_text(path) gives the file as it stands, used to drop lines under a history heading.
    """
    out: dict[str, tuple[set[int], int]] = {}
    for block in re.split(r"(?m)^diff --git ", patch):
        m = re.search(r"(?m)^\+\+\+ (?:b/)?(.+)$", block)
        if not m or m.group(1) == "/dev/null":
            continue
        path = m.group(1).strip()
        if not _DOC.search(path) or _SKIP.search(path):
            continue
        html = path.lower().endswith((".html", ".htm"))
        text = path_text(path) or ""
        cut = history_start(text)
        gen = generated_lines(text) | (code_lines(text) if html else set())
        lines, chars = set(), 0
        for h in re.split(r"(?m)^(?=@@ )", block)[1:]:
            hm = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))?", h)
            if not hm:
                continue
            start, rows = int(hm.group(1)), h.split("\n")[1:]
            old = "\n".join(r[1:] for r in rows if r.startswith("-"))
            new = [r[1:] for r in rows if r.startswith("+")]
            if cut is not None and start >= cut:
                continue
            pn, po = prose("\n".join(new), html), prose(old, html)
            if pn == po:
                continue
            span = range(start, start + max(1, len(new)))
            keep = [n for n in span if (cut is None or n < cut) and n not in gen]
            if not keep:
                continue
            lines.update(keep)
            chars += round(max(len(pn), len(po)) * (1 - difflib.SequenceMatcher(None, po, pn).ratio()))
        if lines:
            out[path] = (lines, chars)
    return out


# ------------------------------------------------------------------ collection

def _git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


def _read(p: Path) -> str | None:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return None


def label(it: dict) -> str:
    return f"{Path(it['root']).name}/{it['path']}"


def repos(extra: tuple[str, ...] = ()) -> list[Path]:
    """Git repositories at, or directly under, each root."""
    seen, out = set(), []
    for root in map(Path, (*extra, *REPO_ROOTS)):
        if not root.is_dir():
            continue
        try:
            kids = sorted(p for p in root.iterdir() if p.is_dir())
        except OSError:
            continue
        for d in [root, *kids]:
            if (d / ".git").exists() and d.resolve() not in seen:
                seen.add(d.resolve())
                out.append(d)
    return out


def _whole(root: Path, rel: str) -> dict | None:
    """A new or unversioned file: every line above any history heading."""
    text = _read(root / rel) or ""
    end = (history_start(text) or len(text.splitlines()) + 1) - 1
    html = rel.lower().endswith((".html", ".htm"))
    skip = code_lines(text) | generated_lines(text) if html else set()
    lines = {n for n in range(1, end + 1) if n not in skip}
    chars = len(prose("\n".join(text.splitlines()[:end]), html))
    return {"root": root, "path": rel, "lines": lines, "chars": chars} if lines and chars else None


def _commits_since(repo: Path, t0: float) -> tuple[list[str], set[str]]:
    """(the turn's own commits, newest first; the files they touched). Not the turn's: a shallow clone's boundary
    commit, which git shows as adding every file, and a bot's commit pulled in by a fetch or rebase."""
    try:
        shallow = set((repo / ".git" / "shallow").read_text().split())
    except OSError:
        shallow = set()
    own, files, sha = [], set(), None
    for line in _git(repo, "log", f"--since=@{int(t0)}", "--format=@%H %ae", "--name-only", *GLOBS).splitlines():
        if line.startswith("@"):
            h, _, author = line[1:].partition(" ")
            sha = h if h not in shallow and "[bot]" not in author else None    # a bot's commit, pulled in, is not the turn's
            if sha:
                own.append(sha)
        elif line.strip() and sha:
            files.add(line.strip())
    return own, files


def changed_in_repos(t0: float, roots: list[Path]) -> list[dict]:
    items = []
    for repo in roots:
        own, committed = _commits_since(repo, t0)
        dirty = {p for p in _git(repo, "diff", "HEAD", "--name-only", *GLOBS).split()
                 if (repo / p).exists() and (repo / p).stat().st_mtime >= t0}
        files = sorted(p for p in committed | dirty if (repo / p).exists())
        if files:
            base = _git(repo, "rev-list", "-1", f"--before=@{int(t0)}", "HEAD").strip()
            if not base and own:        # the commit before the turn's first, when it exists in this clone
                base = _git(repo, "rev-parse", "--verify", "-q", own[-1] + "^").strip()
            if not base and not own:
                base = "HEAD"
            if base:
                got = changed_lines(_git(repo, "diff", base, "-U0", "--no-color", "--", *files),
                                    lambda p, r=repo: _read(r / p))
                items += [{"root": repo, "path": p, "lines": l, "chars": c} for p, (l, c) in got.items()]
            else:                       # no commit from before the turn in this clone: read the files whole
                items += [it for p in files if _DOC.search(p) and not _SKIP.search(p)
                          for it in [_whole(repo, p)] if it]
        for p in _git(repo, "ls-files", "--others", "--exclude-standard", *GLOBS).split():
            if _DOC.search(p) and not _SKIP.search(p) and (repo / p).stat().st_mtime >= t0:
                it = _whole(repo, p)
                if it:
                    items.append(it)
    return items


def _in_repo(p: Path, cache: dict) -> bool:
    for d in [p, *p.parents]:
        if d in cache:
            return cache[d]
        if (d / ".git").exists():
            cache[d] = True
            return True
    return False


def changed_outside_repos(t0: float, roots: tuple[str, ...]) -> list[dict]:
    """Doc files written since t0 under the scan roots and not inside a git repository, whole."""
    items, cache, deadline, seen = [], {}, time.time() + SCAN_SECONDS, set()
    for root in map(Path, roots):
        if not root.is_dir() or root.resolve() in seen:
            continue
        seen.add(root.resolve())
        base = len(root.parts)
        for dirpath, dirs, files in os.walk(root):
            if time.time() > deadline:
                return items
            here = Path(dirpath)
            dirs[:] = [d for d in dirs if d not in _PRUNE and not d.startswith(".") and len(here.parts) - base < SCAN_DEPTH]
            if _in_repo(here, cache):
                dirs[:] = []
                continue
            for f in files:
                rel = str((here / f).relative_to(root))
                if not _DOC.search(f) or _SKIP.search(rel):
                    continue
                try:
                    if (here / f).stat().st_mtime < t0:
                        continue
                except OSError:
                    continue
                it = _whole(root, rel)
                if it:
                    items.append(it)
    return items


def changed_since(t0: float, cwd: str = "") -> list[dict]:
    extra = tuple(x for x in (cwd, os.environ.get("CLAUDE_PROJECT_DIR", "")) if x)
    return changed_in_repos(t0, repos(extra)) + changed_outside_repos(t0, (*extra, *SCAN_ROOTS))


# ------------------------------------------------------------------ packet

def sections(text: str, lines: set[int]) -> list[str]:
    """Each Markdown section (heading to the next heading) holding a changed line, whole, plus the title."""
    rows = text.splitlines()
    heads = [i for i, r in enumerate(rows, 1) if _HEAD.match(r)]
    bounds = list(zip([1] + heads, heads + [len(rows) + 1]))
    out = []
    if rows and rows[0].startswith("# ") and not any(a == 1 and any(a <= n < b for n in lines) for a, b in bounds):
        out.append(rows[0])
    spans: list[list[int]] = []                 # touching sections merge, so "[…]" marks only a real gap
    for a, b in bounds:
        if a < b and any(a <= n < b for n in lines):
            if spans and spans[-1][1] == a:
                spans[-1][1] = b
            else:
                spans.append([a, b])
    out += ["\n".join(rows[a - 1:b - 1]).strip() for a, b in spans]
    return [s for s in out if s]


def html_windows(text: str, lines: set[int]) -> list[str]:
    code = code_lines(text)                     # blank script and style lines, so a window never starts inside one
    rows = ["" if i in code else r for i, r in enumerate(text.splitlines(), 1)]
    out, spans = [], []
    for n in sorted(lines):
        a, b = max(1, n - HTML_WINDOW), min(len(rows), n + HTML_WINDOW)
        if spans and a <= spans[-1][1] + 1:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    for a, b in spans:
        t = prose("\n".join(rows[a - 1:b]), html=True)
        if t:
            out.append(t)
    return out


def packet(items: list[dict]) -> str:
    parts, total = [], 0
    for it in items:
        text = _read(Path(it["root"]) / it["path"]) or ""
        html = it["path"].lower().endswith((".html", ".htm"))
        body = "\n\n[…]\n\n".join(html_windows(text, it["lines"]) if html else sections(text, it["lines"]))[:FILE_CAP]
        part = f"## {label(it)}\n\n{body}\n"
        if total + len(part) > PACKET_CAP:
            parts.append(f"## {label(it)}\n\n(left out: the packet is full)\n")
            continue
        parts.append(part)
        total += len(part)
    return "\n".join(parts)


def reader_prompt(path: str, files: str) -> str:
    return (f"{MARK}. You are someone meeting this project for the first time. Read {path}: the sections of {files} "
            f"that were just written or changed, as they now stand. Read only that file, the way a newcomer would; do "
            f"not look at git history, earlier versions or other files. For each section, list what a newcomer would "
            f"stumble on, quoting the phrase: a word or detail that refers to something you were never told (such as "
            f"'here', 'upright', 'still', 'instead', 'the fix'); a passage about what changed or was fixed where you "
            f"needed what the thing is and does; a comparison with a version you never saw; a part given more space "
            f"than it deserves for you; anything you would need to use or understand the thing that is missing. If a "
            f"section reads cleanly to a newcomer, say so in one line. Report only; do not edit any file.")


# ------------------------------------------------------------------ gate

def _stamp(ts) -> float | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def turn_start(turn: list[dict]) -> float | None:
    for rec in turn:
        t = _stamp(rec.get("timestamp")) if rec.get("timestamp") else None
        if t is not None:
            return t - 5
    return None


def reader_at(turn: list[dict]) -> float | None:
    """When the last newcomer read in the turn was sent (epoch seconds), or None if none was."""
    at = None
    for rec in turn:
        if rec.get("type") != "assistant":
            continue
        for b in (rec.get("message") or {}).get("content") or []:
            if (isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")
                    and MARK in str((b.get("input") or {}).get("prompt", ""))):
                at = _stamp(rec.get("timestamp")) or at
    return at


def gate(turn: list[dict], collect=changed_since, prefix: str = "fresh_eyes") -> str | None:
    """The block message for a turn that changed reader-facing text without a later newcomer read, else None."""
    t0 = turn_start(turn)
    if t0 is None:
        return None
    items = collect(t0)
    if not items or sum(it["chars"] for it in items) < MIN_PROSE:
        return None
    read = reader_at(turn)
    last = max((Path(it["root"]) / it["path"]).stat().st_mtime for it in items)
    if read is not None and read >= last:
        return None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{int(time.time())}.md"
    out.write_text(packet(items))
    files = ", ".join(label(it) for it in items)
    return (f"{prefix}: this turn changed reader-facing text in {files}. Before ending, have it read by someone who "
            f"never saw the earlier version: an Agent subagent (general-purpose, a capable model) with this prompt, "
            f"verbatim:\n\n{reader_prompt(str(out), files)}\n\nThen fix what it reports, or say in one line why a "
            f"point stands. Where no subagent tool exists, read the packet yourself as a newcomer and say that the "
            f"read was not independent.")


# ------------------------------------------------------------------ entry points

def _is_human(rec: dict) -> bool:
    if rec.get("type") != "user" or rec.get("isSidechain") or rec.get("isMeta"):
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return not content.startswith("<")
    return isinstance(content, list) and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content) \
        and any(isinstance(b, dict) and b.get("type") == "text" for b in content)


def turn_from(transcript: str) -> list[dict]:
    recs = []
    with open(transcript, errors="replace") as f:
        for line in f:
            try:
                recs.append(json.loads(line))
            except ValueError:
                continue
    for i in range(len(recs) - 1, -1, -1):
        if _is_human(recs[i]):
            return [r for r in recs[i + 1:] if not r.get("isSidechain")]
    return recs


def _log(rec: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def hook() -> int:
    """Stop hook. Prints a block decision or nothing; always exits 0."""
    rec = {"at": datetime.now().isoformat(timespec="seconds"), "cwd": os.getcwd()}
    try:
        d = json.load(sys.stdin)
        rec["cwd"] = d.get("cwd") or rec["cwd"]
        project = os.environ.get("CLAUDE_PROJECT_DIR", "")
        if d.get("stop_hook_active"):
            rec["result"] = "continuation"
        elif project and (Path(project) / "scripts" / "guard_fresh_eyes.py").exists():
            rec["result"] = "deferred to the project's own guard"
        else:
            turn = turn_from(d.get("transcript_path", ""))
            msg = gate(turn, collect=lambda t0: changed_since(t0, d.get("cwd", "")))
            rec["result"] = "blocked" if msg else "pass"
            if msg:
                print(json.dumps({"decision": "block", "reason": msg}))
    except Exception as e:  # noqa: BLE001 - a hook fails open
        rec["result"] = f"error: {type(e).__name__}: {e}"
    _log(rec)
    return 0


def main(argv: list[str]) -> int:
    if argv[1:2] == ["hook"]:
        return hook()
    if argv[1:2] == ["packet"] and len(argv) > 2:
        items = []
        for f in argv[2:]:
            p = Path(f).resolve()
            it = _whole(p.parent, p.name)
            if it:
                items.append(it)
        if not items:
            print("no readable prose in those files", file=sys.stderr)
            return 1
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"{int(time.time())}.md"
        out.write_text(packet(items))
        print(out)
        print(reader_prompt(str(out), ", ".join(label(it) for it in items)))
        return 0
    print(next(b for b in __doc__.split("\n\n") if "fresh_eyes.py packet" in b), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
