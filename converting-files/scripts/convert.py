#!/usr/bin/env python3
"""convert.py — route a file conversion to the right container engine.

This is a *dispatcher*, not a new engine. It picks among pandoc, LibreOffice,
ImageMagick, and ffmpeg by (source_ext -> target_ext) and runs the one that
produces correct output. The routing — not the subprocess call — is the value:
pandoc mangles docx->pdf, LibreOffice is the right tool; pandoc is right for
md->docx; neither touches mp4->gif.

Usage:
    python3 convert.py INPUT OUTPUT [--engine ENGINE] [extra engine args...]
    python3 convert.py --plan INPUT OUTPUT   # print the chosen engine+cmd, run nothing

Exit codes: 0 ok, 2 no route, 3 engine failure, 4 bad args.
"""
import os
import shlex
import subprocess
import sys

# Format families. Membership decides which engine owns a target extension.
DOC_TEXT = {  # pandoc's wheelhouse: markup <-> markup
    "md", "markdown", "rst", "html", "htm", "tex", "latex", "org",
    "rtf", "epub", "textile", "asciidoc", "adoc", "docbook", "man",
    "ipynb", "json", "opml", "mediawiki", "typ", "typst", "csv", "tsv",
}
DOC_OFFICE = {"docx", "pptx", "xlsx", "odt", "ods", "odp", "doc", "ppt", "xls"}
IMAGE = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "tif", "ico",
         "heic", "avif", "ppm", "pgm", "svg"}
AUDIO = {"mp3", "wav", "flac", "ogg", "oga", "aac", "m4a", "opus", "wma"}
VIDEO = {"mp4", "mkv", "webm", "mov", "avi", "gif", "flv", "m4v"}


def ext(path):
    return os.path.splitext(path)[1].lstrip(".").lower()


def family(e):
    if e in DOC_OFFICE:
        return "office"
    if e in DOC_TEXT:
        return "text"
    if e in IMAGE:
        return "image"
    if e in AUDIO:
        return "audio"
    if e in VIDEO:
        return "video"
    return None


def choose(src_ext, dst_ext):
    """Return (engine, reason) or (None, reason)."""
    sf, df = family(src_ext), family(dst_ext)

    # PDF is the cross-cutting target. Route by SOURCE.
    if dst_ext == "pdf":
        if sf in ("office", "text") or src_ext in DOC_OFFICE:
            # Office source -> LibreOffice (fidelity). Text/markup -> LibreOffice
            # too for odt/docx, but pandoc for markup is fine and lighter.
            if sf == "office":
                return "libreoffice", "office source to PDF: LibreOffice preserves layout"
            return "pandoc", "markup source to PDF: pandoc + latex engine"
        if sf == "image":
            return "imagemagick", "image to PDF"
        return None, f"no PDF route from .{src_ext}"

    # Office <-> Office, or Office <-> text-ish that pandoc can't do well.
    if sf == "office" or df == "office":
        # pandoc CAN do docx/odt/pptx but loses fidelity on real Office files
        # and cannot read xls/ppt/doc legacy at all. LibreOffice owns Office.
        # Exception: text-markup -> docx/odt/pptx is pandoc's job and is better.
        if sf == "text" and df == "office":
            return "pandoc", f"markup .{src_ext} to Office .{dst_ext}: pandoc"
        if sf == "office" and df == "text":
            # docx -> md etc: pandoc reads docx/odt well.
            if src_ext in ("docx", "odt", "pptx"):
                return "pandoc", f"Office .{src_ext} to markup: pandoc"
            return "libreoffice", f"legacy Office .{src_ext}: LibreOffice (pandoc can't read it)"
        return "libreoffice", f"Office conversion .{src_ext}->.{dst_ext}: LibreOffice"

    if sf == "text" and df == "text":
        return "pandoc", "markup to markup: pandoc"

    if sf == "image" and df == "image":
        return "imagemagick", "image to image: ImageMagick"

    if sf == "audio" and (df == "audio" or dst_ext == "mp4"):
        return "ffmpeg", "audio to audio: ffmpeg"

    if sf == "video" or df == "video":
        return "ffmpeg", f"video/animation .{src_ext}->.{dst_ext}: ffmpeg"

    if sf == "audio" and df == "video":
        return "ffmpeg", "audio to video container: ffmpeg"

    return None, f"no route .{src_ext} -> .{dst_ext}"


def build_cmd(engine, inp, out, extra):
    if engine == "pandoc":
        return ["pandoc", inp, "-o", out] + extra
    if engine == "libreoffice":
        # LibreOffice converts to a target FILTER by extension, writes into outdir.
        outdir = os.path.dirname(os.path.abspath(out)) or "."
        return ["libreoffice", "--headless", "--convert-to", ext(out),
                "--outdir", outdir, inp] + extra
    if engine == "imagemagick":
        # 'convert' is IM6 here; works for src->dst by extension.
        return ["convert", inp] + extra + [out]
    if engine == "ffmpeg":
        return ["ffmpeg", "-y", "-i", inp] + extra + [out]
    raise ValueError(engine)


def run(cmd, engine, out):
    # LibreOffice ignores the exact output filename (uses input stem). Handle rename.
    if engine == "libreoffice":
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            return 3
        produced = os.path.join(
            os.path.dirname(os.path.abspath(out)) or ".",
            os.path.splitext(os.path.basename(cmd[-1]))[0] + "." + ext(out),
        )
        if produced != os.path.abspath(out) and os.path.exists(produced):
            os.replace(produced, out)
        return 0 if os.path.exists(out) else 3
    r = subprocess.run(cmd, capture_output=True, text=True,
                       timeout=300 if engine == "ffmpeg" else 120)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        return 3
    return 0 if os.path.exists(out) else 3


def main(argv):
    plan_only = False
    args = []
    forced = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--plan":
            plan_only = True
        elif a == "--engine":
            i += 1
            forced = argv[i]
        else:
            args.append(a)
        i += 1
    if len(args) < 2:
        sys.stderr.write(__doc__)
        return 4
    inp, out = args[0], args[1]
    extra = args[2:]
    if not os.path.exists(inp) and not plan_only:
        sys.stderr.write(f"input not found: {inp}\n")
        return 4

    se, de = ext(inp), ext(out)
    if forced:
        engine, reason = forced, "forced via --engine"
    else:
        engine, reason = choose(se, de)
    if engine is None:
        sys.stderr.write(f"NO ROUTE: {reason}\n")
        return 2

    cmd = build_cmd(engine, inp, out, extra)
    if plan_only:
        print(f"engine: {engine}")
        print(f"reason: {reason}")
        print(f"cmd:    {' '.join(shlex.quote(c) for c in cmd)}")
        return 0

    rc = run(cmd, engine, out)
    if rc == 0:
        sz = os.path.getsize(out)
        print(f"ok: {out} ({sz} bytes) via {engine}")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
