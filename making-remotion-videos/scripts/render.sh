#!/usr/bin/env bash
# Render with the browser this container already has, not a downloaded one.
# Usage (from the project dir):
#   render.sh still <CompId> <out.png> <frame>
#   render.sh video <CompId> <out.mp4> [extra remotion flags]
set -euo pipefail
MODE=${1:?still|video}; COMP=${2:?composition id}; OUT=${3:?output path}; shift 3
HS=$(ls /opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell 2>/dev/null | sort -V | tail -1 || true)
BROWSER=()
if [ -n "$HS" ]; then BROWSER=(--browser-executable="$HS"); else echo "no preinstalled headless shell; Remotion will try to download one" >&2; fi
ENTRY=${ENTRY:-src/index.ts}
case "$MODE" in
  still)
    FRAME=${1:?frame number}; shift
    npx remotion still "$ENTRY" "$COMP" "$OUT" --frame="$FRAME" "${BROWSER[@]}" --log=error "$@" ;;
  video)
    # yuv420p + bt709: plays everywhere, including iOS and social uploaders.
    # crf 20 is visually lossless for UI footage at a sane size.
    npx remotion render "$ENTRY" "$COMP" "$OUT" "${BROWSER[@]}" \
      --codec=h264 --crf=20 --pixel-format=yuv420p --color-space=bt709 \
      --concurrency="${CONCURRENCY:-$(nproc)}" "$@" ;;
  *) echo "mode must be still or video" >&2; exit 2 ;;
esac
