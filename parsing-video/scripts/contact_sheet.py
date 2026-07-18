#!/usr/bin/env python3
"""Generate timestamped contact sheets from a video for visual interpretation.

Samples frames evenly across the video (or a --start/--end window), stamps
each frame with its source timestamp, and tiles them into one or more grid
images sized for vision-model readability.

Usage:
    python3 contact_sheet.py input.mp4
    python3 contact_sheet.py input.mp4 --sheets 3 --grid 4x4 --output-dir /tmp/sheets
    python3 contact_sheet.py input.mp4 --start 120 --end 300 --grid 3x3
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def probe(path: str) -> dict:
    """Return format/stream metadata for a media file via ffprobe.

    Raises SystemExit with a readable message if the file is unreadable
    or has no video stream.
    """
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("ffprobe not found — install ffmpeg first (apt-get install -y ffmpeg)")
    except subprocess.CalledProcessError as e:
        sys.exit(f"ffprobe failed on {path}: {e.stderr.strip()}")
    info = json.loads(out)
    video = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not video:
        sys.exit(f"No video stream in {path}")
    return {
        "duration": float(info["format"].get("duration", 0) or 0),
        "width": video[0].get("width"),
        "height": video[0].get("height"),
    }


def hms(seconds: float) -> str:
    """Format seconds as H:MM:SS."""
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def parse_ts(value: str) -> float:
    """Parse a timestamp given as seconds ('90', '90.5') or clock ('1:30', '0:01:30')."""
    parts = value.strip().split(":")
    if len(parts) > 3 or not all(p for p in parts):
        raise ValueError(f"bad timestamp: {value!r}")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def find_font() -> str | None:
    """Return the first available label font, or None to rely on fontconfig."""
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return None


def extract_frame(src: str, ts: float, dest: Path, tile_width: int, font: str | None) -> bool:
    """Extract one frame at ts, scaled to tile_width and stamped with its timestamp.

    Returns True on success, False if extraction failed (e.g. ts past EOF).
    """
    label = hms(ts).replace(":", r"\:")
    fontsize = max(14, tile_width // 16)
    draw = (
        f"drawtext=text='{label}'"
        + (f":fontfile={font}" if font else "")
        + f":fontsize={fontsize}:fontcolor=white:borderw=2:bordercolor=black"
        + ":x=6:y=h-th-6"
    )
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-ss", f"{ts:.3f}", "-i", src,
        "-frames:v", "1",
        "-vf", f"scale={tile_width}:-2,{draw}",
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and dest.exists()


def assemble(frames_dir: Path, cols: int, rows: int, sheet_pattern: Path) -> None:
    """Tile the extracted frame sequence into contact sheet image(s)."""
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-framerate", "1", "-i", str(frames_dir / "f_%04d.png"),
        "-vf", f"tile={cols}x{rows}:padding=4:margin=4:color=0x181818",
        "-fps_mode", "passthrough",
        str(sheet_pattern),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"tiling failed: {result.stderr.strip()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="video file")
    ap.add_argument("--grid", default="4x4", help="tiles per sheet as COLSxROWS (default 4x4)")
    ap.add_argument("--sheets", type=int, default=1, help="number of sheets to produce (default 1)")
    ap.add_argument("--tile-width", type=int, default=380,
                    help="width of each tile in px (default 380; 4 cols ≈ 1550px sheet)")
    ap.add_argument("--start", type=float, default=0.0, help="window start in seconds")
    ap.add_argument("--end", type=float, default=None, help="window end in seconds (default: duration)")
    ap.add_argument("--at", default=None, metavar="TS,TS,...",
                    help="sample at explicit timestamps (seconds or H:MM:SS, comma-separated) "
                         "instead of even intervals — e.g. scene-cut times; "
                         "overrides --sheets/--start/--end")
    ap.add_argument("--output-dir", default=None, help="where to write sheets (default: alongside input)")
    args = ap.parse_args()

    try:
        cols, rows = (int(v) for v in args.grid.lower().split("x"))
    except ValueError:
        sys.exit(f"--grid must look like 4x4, got {args.grid!r}")
    if cols < 1 or rows < 1 or args.sheets < 1:
        sys.exit("--grid dimensions and --sheets must be positive")

    src = Path(args.input)
    if not src.exists():
        sys.exit(f"input not found: {src}")

    meta = probe(str(src))
    duration = meta["duration"]

    if args.at:
        try:
            timestamps = sorted(parse_ts(t) for t in args.at.split(","))
        except ValueError as e:
            sys.exit(str(e))
        in_range = [t for t in timestamps if 0 <= t < duration]
        if len(in_range) < len(timestamps):
            print(f"warning: dropped {len(timestamps) - len(in_range)} timestamp(s) "
                  f"outside 0–{duration:.1f}s", file=sys.stderr)
        if not in_range:
            sys.exit("no --at timestamps fall within the video")
        timestamps = in_range
        n_frames = len(timestamps)
        start, end, interval = timestamps[0], timestamps[-1], None
    else:
        end = min(args.end, duration) if args.end is not None else duration
        start = max(0.0, args.start)
        span = end - start
        if span <= 0:
            sys.exit(f"empty time window: start={start}, end={end} (duration {duration:.1f}s)")
        n_frames = cols * rows * args.sheets
        interval = span / n_frames
        # Sample at interval midpoints: avoids the black/logo first frame and EOF misses.
        timestamps = [start + (i + 0.5) * interval for i in range(n_frames)]

    out_dir = Path(args.output_dir) if args.output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    font = find_font()

    tmp = Path(tempfile.mkdtemp(prefix="contact_sheet_"))
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            ok = list(pool.map(
                lambda it: extract_frame(str(src), it[1], tmp / f"f_{it[0]:04d}.png",
                                         args.tile_width, font),
                enumerate(timestamps),
            ))
        n_ok = sum(ok)
        if n_ok == 0:
            sys.exit("no frames could be extracted — check the file with ffprobe")
        if n_ok < n_frames:
            # Renumber contiguously so the image2 sequence reader sees no gaps.
            for i, f in enumerate(sorted(tmp.glob("f_*.png"))):
                f.rename(tmp / f"r_{i:04d}.png")
            for f in sorted(tmp.glob("r_*.png")):
                f.rename(tmp / f"f_{f.stem[2:]}.png")
            print(f"warning: {n_frames - n_ok} of {n_frames} frames failed to extract",
                  file=sys.stderr)

        pattern = out_dir / f"{src.stem}_sheet_%02d.png"
        assemble(tmp, cols, rows, pattern)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    sheets = sorted(out_dir.glob(f"{src.stem}_sheet_*.png"))
    per_sheet = cols * rows
    how = (f"at {n_frames} explicit timestamps" if interval is None
           else f"{n_frames} frames every {interval:.1f}s")
    print(f"{src.name}: {duration:.1f}s total, sampled {how} "
          f"from {hms(start)} to {hms(end)}")
    for i, sheet in enumerate(sheets):
        chunk = timestamps[i * per_sheet:(i + 1) * per_sheet]
        if chunk:
            print(f"  {sheet}  [{hms(chunk[0])} – {hms(chunk[-1])}]")
    print("Read the sheet image(s) to view the video; timestamps are stamped on each tile.")


if __name__ == "__main__":
    main()
