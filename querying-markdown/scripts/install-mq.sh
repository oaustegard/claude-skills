#!/usr/bin/env bash
# Idempotent installer for `mq`, the jq-for-Markdown CLI (https://github.com/harehare/mq).
# Fetches the static x86_64-linux binary into /usr/local/bin. Safe to re-run — exits
# early if mq is already on PATH. No build step; mq is a single self-contained binary.
set -euo pipefail

MQ_VERSION="${MQ_VERSION:-v0.5.31}"
DEST="${MQ_DEST:-/usr/local/bin/mq}"
ASSET="mq-x86_64-unknown-linux-gnu"

if command -v mq >/dev/null 2>&1; then
  echo "mq already installed: $(mq --version 2>/dev/null) ($(command -v mq))"
  exit 0
fi

echo "Installing mq ${MQ_VERSION} -> ${DEST}"
tmp="$(mktemp)"

if command -v gh >/dev/null 2>&1; then
  # gh carries GH_TOKEN auth, sidestepping shared-container-IP rate limits.
  gh release download "${MQ_VERSION}" --repo harehare/mq \
     --pattern "${ASSET}" --output "${tmp}" --clobber
else
  curl -fsSL "https://github.com/harehare/mq/releases/download/${MQ_VERSION}/${ASSET}" -o "${tmp}"
fi

chmod +x "${tmp}"
# /usr/local/bin is typically root-owned; fall back to sudo if a plain mv is denied.
mv "${tmp}" "${DEST}" 2>/dev/null || sudo mv "${tmp}" "${DEST}"

echo "Installed: $(mq --version)"
