#!/usr/bin/env bash
# ui_sdk_docs.sh — print a ui-sdk docs page from the @ui-sdk/react npm package
#
# Usage:
#   ./ui_sdk_docs.sh dialog                    # a component page (docs/components/dialog.md)
#   ./ui_sdk_docs.sh dialog --toc              # its headings only
#   ./ui_sdk_docs.sh dialog --section Styling  # one "## " section
#   ./ui_sdk_docs.sh popups                    # a guide (docs/popups.md)
#   ./ui_sdk_docs.sh --list                    # every page
#
# The pages are written for React (TSX). The parts, props, data attributes and
# CSS variables are the same in Preact; translate the markup to HTM. Pages run
# 30-130 KB, so read the TOC first and print the sections you need.

set -euo pipefail

VERSION="0.1.0-beta.10"   # keep equal to the build in assets/ui-sdk/
CACHE="${TMPDIR:-/tmp}/ui-sdk-react-${VERSION}"

if [ ! -d "$CACHE/package/docs" ]; then
  mkdir -p "$CACHE"
  url=$(curl -sfL "https://registry.npmjs.org/@ui-sdk/react/${VERSION}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['dist']['tarball'])")
  curl -sfL "$url" | tar -xzf - -C "$CACHE" package/docs
fi
DOCS="$CACHE/package/docs"

if [ "${1:-}" = "--list" ] || [ -z "${1:-}" ]; then
  echo "Components:"; ls "$DOCS/components" | sed 's/\.md$//' | paste -sd' ' -
  echo; echo "Guides:"; ls "$DOCS" | grep '\.md$' | sed 's/\.md$//' | paste -sd' ' -
  echo; echo "Hooks:"; ls "$DOCS/hooks" | sed 's/\.md$//' | paste -sd' ' -
  exit 0
fi

name="$1"; shift
page=""
for candidate in "$DOCS/components/$name.md" "$DOCS/$name.md" "$DOCS/hooks/$name.md"; do
  if [ -f "$candidate" ]; then page="$candidate"; break; fi
done
if [ -z "$page" ]; then
  echo "No ui-sdk docs page named '$name'. Run with --list." >&2
  exit 1
fi

case "${1:-}" in
  --toc)
    grep -E '^#{1,3} ' "$page"
    ;;
  --section)
    want="${2:?--section needs a heading, like Composition}"
    awk -v want="$want" '
      /^## / { on = (substr($0, 4) == want) }
      on { print }
    ' "$page"
    ;;
  "")
    cat "$page"
    ;;
  *)
    echo "Unknown option $1" >&2
    exit 2
    ;;
esac
