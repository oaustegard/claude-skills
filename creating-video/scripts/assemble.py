#!/usr/bin/env python3
"""
assemble.py — cut raw Veo clips into a finished short via ffmpeg.

Encodes the editing facts learned 2026-07-18:
  - Veo returns ~8s clips; trim each to its beat (~5s) picking a window past
    the initial settle (default --ss 0.4).
  - Drop audio by default (-an): crossfading 6 independent Veo ambiences is
    jarring. Pass --keep-audio to acrossfade instead.
  - xfade chain offset for equal clips of duration D with transition T:
    offset_k = (k+1)*(D-T). Get this wrong and clips stack or gap.
  - Veo renders on-screen WORDS unreliably, so keep "no on-screen text" in the
    generation prompt and burn the payoff word here with drawtext.
  - Abrupt endings: hold the final frame (--tail-hold) before the fade-out so
    the last beat lands instead of being cut. (Oskar note, 2026-07-18.)
  - Single-core container: encodes serialize; keep each ffmpeg invocation short.

Usage:
  python3 assemble.py c1.mp4 c2.mp4 ... c6.mp4 --out film.mp4 \
      [--beat 5.42] [--xfade 0.5] [--keep-audio] \
      [--overlay-last "COMING HOME"] [--overlay-at 3.2] \
      [--tail-hold 1.2] [--font /path/to/Bold.ttf]
"""
import os, sys, json, argparse, subprocess, tempfile
from pathlib import Path


def _run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode(errors="replace")


def _font():
    for c in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(c).exists():
            return c
    return None


def assemble(clips, out, beat=5.42, xfade=0.5, keep_audio=False,
             overlay_last=None, overlay_at=3.2, tail_hold=0.0,
             size="1280:720", fps=25, font=None):
    tmp = Path(tempfile.mkdtemp())
    font = font or _font()
    vf_base = (f"scale={size}:force_original_aspect_ratio=increase,"
               f"crop={size},fps={fps}")
    trimmed = []
    n = len(clips)
    for i, src in enumerate(clips):
        vf = vf_base
        last = (i == n - 1)
        # hold last frame on the final clip by extending it via tpad
        beat_i = beat + (tail_hold if last else 0.0)
        if last and overlay_last and font:
            dt = (f",drawtext=fontfile='{font}':text='{overlay_last}':"
                  f"fontcolor=white:fontsize=72:x=(w-text_w)/2:y=h*0.82:"
                  f"alpha='if(lt(t,{overlay_at}),0,min((t-{overlay_at})/1.5,0.94))':"
                  f"shadowcolor=black:shadowx=3:shadowy=3")
            vf += dt
        if last and tail_hold > 0:
            vf += f",tpad=stop_mode=clone:stop_duration={tail_hold}"
        vf += ",format=yuv420p"
        dst = tmp / f"t{i}.mp4"
        audio = [] if not keep_audio else []
        cmd = ["ffmpeg", "-y", "-ss", "0.4", "-t", f"{beat}", "-i", str(src),
               "-vf", vf, "-r", str(fps)]
        if not keep_audio:
            cmd += ["-an"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(dst)]
        rc, log = _run(cmd)
        if rc != 0 or not dst.exists():
            raise RuntimeError(f"trim failed for {src}:\n{log[-400:]}")
        trimmed.append(dst)

    # xfade chain
    inputs = []
    for t in trimmed:
        inputs += ["-i", str(t)]
    D = beat  # clip duration for offset math (tail_hold handled inside last clip)
    T = xfade
    fc = ""
    prev = "0"
    total = D + tail_hold  # final clip is longer by tail_hold
    for k in range(1, n):
        off = k * (D - T)
        lbl = "v" if k == n - 1 else f"x{k}"
        fc += f"[{prev}][{k}]xfade=transition=fade:duration={T}:offset={off:.3f}[{lbl}];"
        prev = lbl
    full_len = (n * D) - ((n - 1) * T) + tail_hold
    fc += (f"[v]fade=t=in:st=0:d=0.6,"
           f"fade=t=out:st={full_len-1.0:.2f}:d=1.0,format=yuv420p[vv]")
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", fc, "-map", "[vv]",
           "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-movflags", "+faststart", str(out)]
    rc, log = _run(cmd)
    if rc != 0 or not Path(out).exists():
        raise RuntimeError(f"stitch failed:\n{log[-500:]}")
    return out


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--beat", type=float, default=5.42)
    ap.add_argument("--xfade", type=float, default=0.5)
    ap.add_argument("--keep-audio", action="store_true")
    ap.add_argument("--overlay-last", default=None)
    ap.add_argument("--overlay-at", type=float, default=3.2)
    ap.add_argument("--tail-hold", type=float, default=0.0)
    ap.add_argument("--font", default=None)
    a = ap.parse_args()
    out = assemble(a.clips, a.out, beat=a.beat, xfade=a.xfade,
                   keep_audio=a.keep_audio, overlay_last=a.overlay_last,
                   overlay_at=a.overlay_at, tail_hold=a.tail_hold, font=a.font)
    rc, info = _run(["ffprobe", "-v", "error", "-show_entries",
                     "format=duration", "-of", "csv=p=0", out])
    print(f"wrote {out} ({info.strip()}s)")


if __name__ == "__main__":
    _main()
