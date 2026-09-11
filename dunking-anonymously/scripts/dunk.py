#!/usr/bin/env python3
"""Render a Bluesky post as an anonymised screenshot — declassified-document styling.

Fetches via the public (unauthenticated) AppView API, strips every identifier of
the author, and writes a PNG plus alt text you can attach to a post of your own.

    python3 dunk.py https://bsky.app/profile/lu.is/post/3mv6ynbcjr62b
    python3 dunk.py at://did:plc:xxxx/app.bsky.feed.post/3mv6... --stamp
    python3 dunk.py <url> --redact "my town" --redact "the conference" --show-date

Outputs <rkey>.png, prints the alt text to stdout, and writes <rkey>.json with
the source URI for your own records. The source URI never appears in the image
or the alt text.
"""

import argparse
import json
import os
import random
import re
import urllib.error
import urllib.parse
import urllib.request

HOSTS = ("public.api.bsky.app", "api.bsky.app")
PATH = "/xrpc/app.bsky.feed.getPostThread"
UA = "muninn-raven"

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
MONO = os.path.join(FONT_DIR, "DejaVuSansMono.ttf")
MONO_BOLD = os.path.join(FONT_DIR, "DejaVuSansMono-Bold.ttf")

PAPER = (242, 239, 231)
INK = (26, 24, 20)
FADE = (120, 114, 102)
BAR = (12, 12, 12)
STAMP = (168, 38, 38)


# ---------------------------------------------------------------- fetching


def post_uri(ref: str) -> str:
    """Accept a bsky.app URL, an at:// URI, or handle/rkey. Return an at:// URI."""
    ref = ref.strip()
    if ref.startswith("at://"):
        return ref
    m = re.search(r"/profile/([^/]+)/post/([A-Za-z0-9]+)", ref)
    if m:
        return f"at://{m.group(1)}/app.bsky.feed.post/{m.group(2)}"
    m = re.fullmatch(r"([^/\s]+)/([A-Za-z0-9]+)", ref)
    if m:
        return f"at://{m.group(1)}/app.bsky.feed.post/{m.group(2)}"
    raise SystemExit(f"cannot parse post reference: {ref!r}")


def fetch(uri: str) -> dict:
    """Query the public AppView. Falls back to api.bsky.app, which answers when
    public.api.bsky.app 403s from a proxied environment."""
    qs = urllib.parse.urlencode({"uri": uri, "depth": 0})
    last = None
    for host in HOSTS:
        req = urllib.request.Request(f"https://{host}{PATH}?{qs}",
                                     headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code not in (403, 429, 502, 503):
                raise
            last = e
    else:
        raise SystemExit(f"both AppView hosts refused the request ({last})")
    post = data.get("thread", {}).get("post")
    if not post:
        raise SystemExit(f"no post at {uri} (deleted, blocked, or wrong rkey)")
    return post


# ---------------------------------------------------------------- redaction

EMBED_NOTE = {
    "app.bsky.embed.images": "[image not shown]",
    "app.bsky.embed.external": "[link preview not shown]",
    "app.bsky.embed.video": "[video not shown]",
    "app.bsky.embed.record": "[quoted post not shown]",
    "app.bsky.embed.recordWithMedia": "[quoted post and media not shown]",
}


def spans(post: dict, extra: list) -> list:
    """Return [(text, redacted)] segments. Mentions always go; extra is literal."""
    record = post["record"]
    raw = record.get("text", "").encode("utf-8")
    cuts = []
    for facet in record.get("facets", []):
        kinds = {f.get("$type", "") for f in facet.get("features", [])}
        if any("mention" in k for k in kinds):
            idx = facet["index"]
            cuts.append((idx["byteStart"], idx["byteEnd"]))
    out, pos = [], 0
    for start, end in sorted(cuts):
        if start < pos:
            continue
        out.append((raw[pos:start].decode("utf-8", "replace"), False))
        out.append((raw[start:end].decode("utf-8", "replace"), True))
        pos = end
    out.append((raw[pos:].decode("utf-8", "replace"), False))

    for phrase in extra:
        if not phrase:
            continue
        split = []
        for text, red in out:
            if red or phrase.lower() not in text.lower():
                split.append((text, red))
                continue
            i = 0
            low = text.lower()
            needle = phrase.lower()
            while True:
                j = low.find(needle, i)
                if j < 0:
                    split.append((text[i:], False))
                    break
                split.append((text[i:j], False))
                split.append((text[j : j + len(phrase)], True))
                i = j + len(phrase)
        out = [s for s in split if s[0]]
    return [s for s in out if s[0]]


def alt_text(segments: list, note: str) -> str:
    body = "".join("[redacted]" if red else t for t, red in segments)
    if note:
        body = f"{body}\n\n{note}"
    alt = f"Screenshot of a Bluesky post, author hidden: {body}"
    return alt[:1997] + "..." if len(alt) > 2000 else alt


# ---------------------------------------------------------------- rendering


def wrap(draw, segments, font, max_w):
    """Word-wrap [(text, redacted)] into lines of [(word, redacted, width)]."""
    lines, line, width = [], [], 0
    space = draw.textlength(" ", font=font)
    paras, gaps = split_paragraphs(segments)
    for para_i, para in enumerate(paras):
        for text, red in para:
            for word in re.split(r"(\s+)", text):
                if not word:
                    continue
                if word.isspace():
                    if line:
                        line.append((" ", False, space))
                        width += space
                    continue
                w = draw.textlength(word, font=font)
                if line and width + w > max_w:
                    while line and line[-1][0] == " ":
                        line.pop()
                    lines.append(line)
                    line, width = [], 0
                line.append((word, red, w))
                width += w
        while line and line[-1][0] == " ":
            line.pop()
        lines.append(line)
        line, width = [], 0
        if gaps[para_i]:
            lines.append([])  # blank line between paragraphs
    while lines and not lines[-1]:
        lines.pop()
    return lines


def split_paragraphs(segments):
    """Split on newlines. Returns (paragraphs, gap_after) — gap only for blank lines."""
    paras, gaps, cur = [], [], []
    for text, red in segments:
        if red:
            cur.append((text, red))
            continue
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i:
                if cur:
                    paras.append(cur)
                    gaps.append(False)
                    cur = []
                elif paras:
                    gaps[-1] = True  # this newline followed an empty line
            if part:
                cur.append((part, False))
    if cur:
        paras.append(cur)
        gaps.append(False)
    return (paras or [[]]), (gaps or [False])


def render(segments, note, date, width, use_stamp, out_path):
    from PIL import Image, ImageDraw, ImageFont

    pad = 56
    body_font = ImageFont.truetype(MONO, 27)
    small = ImageFont.truetype(MONO, 17)
    label = ImageFont.truetype(MONO_BOLD, 15)
    max_w = width - 2 * pad

    probe = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(probe)
    lines = wrap(d, segments, body_font, max_w)

    line_h = 40
    head_h = 118
    note_h = 44 if note else 0
    foot_h = 56
    stamp_h = 120 if use_stamp else 0
    height = pad + head_h + len(lines) * line_h + note_h + foot_h + stamp_h + pad

    img = Image.new("RGB", (width, height), PAPER)
    d = ImageDraw.Draw(img)

    # photocopy grain
    rng = random.Random(1312)
    px = img.load()
    for _ in range((width * height) // 220):
        x, y = rng.randrange(width), rng.randrange(height)
        v = rng.randint(-14, 6)
        r, g, b = px[x, y]
        px[x, y] = (max(0, r + v), max(0, g + v), max(0, b + v))

    d.rectangle([pad - 22, pad - 22, width - pad + 22, height - pad + 22],
                outline=(178, 170, 156), width=2)

    # header: avatar block + two name bars, all struck out
    y = pad
    d.rectangle([pad, y, pad + 86, y + 86], fill=BAR)

    bar_x = pad + 110
    d.rectangle([bar_x, y + 8, bar_x + 330, y + 42], fill=BAR)
    d.text((bar_x + 14, y + 25), "REDACTED", font=label, fill=PAPER, anchor="lm")
    d.rectangle([bar_x, y + 52, bar_x + 232, y + 80], fill=BAR)
    d.text((bar_x + 14, y + 66), "REDACTED", font=label, fill=PAPER, anchor="lm")

    # body
    y = pad + head_h
    for line in lines:
        x = pad
        run_start = None
        for i, (word, red, w) in enumerate(line):
            joins = red or (
                run_start is not None
                and word == " "
                and i + 1 < len(line)
                and line[i + 1][1]
            )
            if joins:
                if run_start is None:
                    run_start = x
            else:
                if run_start is not None:
                    d.rectangle([run_start, y + 4, x, y + 32], fill=BAR)
                    run_start = None
                d.text((x, y), word, font=body_font, fill=INK)
            x += w
        if run_start is not None:
            d.rectangle([run_start, y + 4, x, y + 32], fill=BAR)
        y += line_h

    if note:
        d.text((pad, y + 6), note, font=small, fill=FADE)
        y += note_h

    y += stamp_h
    foot = "SOURCE WITHHELD — ANONYMOUS QUOTE"
    if date:
        foot += f"   ·   {date}"
    d.line([pad, height - pad - 34, width - pad, height - pad - 34], fill=(196, 188, 172), width=1)
    d.text((pad, height - pad - 22), foot, font=small, fill=FADE)

    if use_stamp:
        stamp = Image.new("RGBA", (392, 112), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sf = ImageFont.truetype(MONO_BOLD, 46)
        sd.rectangle([5, 5, 387, 107], outline=STAMP + (165,), width=6)
        sd.text((196, 57), "REDACTED", font=sf, fill=STAMP + (165,), anchor="mm")
        stamp = stamp.rotate(9, expand=True, resample=Image.BICUBIC)
        img.paste(stamp, (width - stamp.width - pad,
                          height - pad - 46 - stamp.height), stamp)

    img.save(out_path)
    return out_path


# ---------------------------------------------------------------- cli


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("post", help="bsky.app URL, at:// URI, or handle/rkey")
    ap.add_argument("--out", help="output PNG path (default ./<rkey>.png)")
    ap.add_argument("--redact", action="append", default=[],
                    help="literal phrase to black out; repeatable")
    ap.add_argument("--show-date", action="store_true",
                    help="print the post date in the footer (default off — dates narrow the field)")
    ap.add_argument("--stamp", action="store_true", help="add the rotated REDACTED stamp")
    ap.add_argument("--width", type=int, default=1200)
    args = ap.parse_args()

    uri = post_uri(args.post)
    post = fetch(uri)
    record = post["record"]

    segments = spans(post, args.redact)
    etype = (record.get("embed") or {}).get("$type", "")
    note = EMBED_NOTE.get(etype.split("#")[0], "")
    date = record.get("createdAt", "")[:10] if args.show_date else ""

    rkey = uri.rsplit("/", 1)[-1]
    out = args.out or f"{rkey}.png"
    render(segments, note, date, args.width, args.stamp, out)

    alt = alt_text(segments, note)
    with open(os.path.splitext(out)[0] + ".json", "w") as f:
        json.dump({"source_uri": uri, "alt": alt, "image": out}, f, indent=1)

    print(out)
    print("--- alt text ---")
    print(alt)


if __name__ == "__main__":
    main()
