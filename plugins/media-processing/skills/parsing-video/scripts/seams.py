#!/usr/bin/env python3
"""
seams.py — seam-continuity sheet for an editing agent overseeing a multi-clip cut.

A whole-film contact sheet shows overall flow; this shows the CUTS. For each
boundary it pairs the last frame of the outgoing clip with the first frame of the
incoming clip, side by side, one row per seam — so character/prop/logic continuity
across a cut is checkable in a single Read.

Usage:
  python3 seams.py clip1.mp4 clip2.mp4 clip3.mp4 [--out seams.png] [--tile-width 480]

Reads left-to-right, top-to-bottom: row k = [end of clip k | start of clip k+1].
"""
import sys, subprocess, tempfile, argparse
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pillow",
                    "--break-system-packages", "-q"])
    from PIL import Image, ImageDraw, ImageFont


def _dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], stdout=subprocess.PIPE)
    try:
        return float(r.stdout.decode().strip())
    except ValueError:
        return 0.0


def _frame(path, t, out):
    subprocess.run(["ffmpeg", "-y", "-ss", f"{max(t,0):.2f}", "-i", str(path),
                    "-frames:v", "1", str(out)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Path(out).exists()


def _label(img, text):
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:
        f = ImageFont.load_default()
    d.rectangle([0, img.height - 30, len(text) * 13 + 12, img.height], fill=(0, 0, 0))
    d.text((6, img.height - 28), text, fill=(255, 255, 255), font=f)
    return img


def build(clips, out="seams.png", tile_w=480):
    tmp = Path(tempfile.mkdtemp())
    tiles = []  # (label, path)
    for i, c in enumerate(clips):
        d = _dur(c)
        fin = tmp / f"{i}_in.png"; fout = tmp / f"{i}_out.png"
        _frame(c, 0.1, fin)
        _frame(c, max(d - 0.15, 0.1), fout)
        tiles.append((f"clip{i+1} OUT", fout, f"clip{i+2} IN"))
    rows = []
    for k in range(len(clips) - 1):
        out_lbl, out_path, _ = tiles[k]
        in_path = tmp / f"{k+1}_in.png"
        rows.append((f"seam {k+1}\u2192{k+2}: {out_lbl}", out_path,
                     f"clip{k+2} IN", in_path))
    if not rows:
        raise SystemExit("Need at least 2 clips for a seam sheet.")

    # size each tile to tile_w preserving aspect
    def load(p, lbl):
        im = Image.open(p).convert("RGB")
        h = int(im.height * tile_w / im.width)
        im = im.resize((tile_w, h))
        return _label(im, lbl)

    row_imgs = []
    for lo, op, li, ip in rows:
        left = load(op, lo); right = load(ip, li)
        h = max(left.height, right.height)
        row = Image.new("RGB", (tile_w * 2 + 8, h), (18, 18, 18))
        row.paste(left, (0, 0)); row.paste(right, (tile_w + 8, 0))
        row_imgs.append(row)
    W = row_imgs[0].width
    H = sum(r.height for r in row_imgs) + 8 * (len(row_imgs) - 1)
    sheet = Image.new("RGB", (W, H), (18, 18, 18))
    y = 0
    for r in row_imgs:
        sheet.paste(r, (0, y)); y += r.height + 8
    sheet.save(out)
    print(f"{out}  ({len(rows)} seams, {len(clips)} clips)")
    print("Each row: [end of outgoing clip | start of incoming clip]. "
          "Read for character/prop/logic continuity across the cut.")
    return out


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--out", default="seams.png")
    ap.add_argument("--tile-width", type=int, default=480)
    a = ap.parse_args()
    build(a.clips, a.out, a.tile_width)


if __name__ == "__main__":
    _main()
