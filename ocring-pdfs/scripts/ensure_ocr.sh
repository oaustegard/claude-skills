#!/bin/sh
# Idempotent runtime install for the ocrmypdf toolchain.
# Usage:  sh ensure_ocr.sh [lang ...]     e.g.  sh ensure_ocr.sh nor deu
# Fast-exits in <1s when everything is already present.
set -e

need=""
command -v tesseract >/dev/null 2>&1 || need="$need tesseract-ocr"
command -v gs        >/dev/null 2>&1 || need="$need ghostscript"
command -v pngquant  >/dev/null 2>&1 || need="$need pngquant"
command -v pdftotext >/dev/null 2>&1 || need="$need poppler-utils"

for l in "$@"; do
  tesseract --list-langs 2>/dev/null | grep -qx "$l" || need="$need tesseract-ocr-$l"
done

if [ -n "$need" ]; then
  # Do NOT run `apt-get update` first. A preconfigured nodesource repo is off the
  # egress allowlist and 403s, which makes update exit 100 and abort the chain.
  # The Ubuntu mirrors are reachable without it. (Measured 2026-09-12.)
  echo "installing:$need" >&2
  apt-get install -y --no-install-recommends $need >/dev/null 2>&1
fi

if ! python3 -c 'import ocrmypdf' >/dev/null 2>&1; then
  echo "installing: ocrmypdf" >&2
  pip install --break-system-packages -q ocrmypdf >/dev/null 2>&1
fi

echo "ocrmypdf $(ocrmypdf --version 2>&1) | tesseract langs: $(tesseract --list-langs 2>/dev/null | tail -n +2 | tr '\n' ' ')"
