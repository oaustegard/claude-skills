#!/usr/bin/env bash
# vendor.sh — Download Preact ecosystem ESM modules from npm registry
#
# Usage: ./vendor.sh [output_dir]
#   output_dir: where to write vendor files (default: ./vendor)
#
# Downloads modular ESM files (not standalone bundles) so that
# @preact/signals can resolve 'preact' and 'preact/hooks' via
# import map to a single shared Preact instance.

set -euo pipefail

VENDOR_DIR="${1:-./vendor}"
mkdir -p "$VENDOR_DIR"

# Package versions — update these as needed
PREACT_VER="10.23.1"
SIGNALS_CORE_VER="1.8.0"
SIGNALS_VER="1.3.0"
HTM_VER="3.1.1"

# Fetch a single file from an npm package tarball.
# Args: package_name version tarball_path output_filename
fetch_npm_file() {
  local pkg="$1" ver="$2" tpath="$3" outfile="$4"
  local tarball_url

  # Get tarball URL from registry metadata
  tarball_url=$(curl -sL "https://registry.npmjs.org/${pkg}/${ver}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['dist']['tarball'])")

  # Download tarball and extract the single file we need
  curl -sL "$tarball_url" \
    | tar -xzf - --to-stdout "package/${tpath}" \
    > "${VENDOR_DIR}/${outfile}"

  local size
  size=$(wc -c < "${VENDOR_DIR}/${outfile}")
  echo "  ✓ ${outfile} (${size} bytes)"
}

echo "Vendoring Preact ecosystem into ${VENDOR_DIR}/"
echo ""

echo "Preact ${PREACT_VER}:"
fetch_npm_file "preact" "$PREACT_VER" \
  "dist/preact.module.js" "preact.module.js"
fetch_npm_file "preact" "$PREACT_VER" \
  "hooks/dist/hooks.module.js" "hooks.module.js"

echo ""
echo "@preact/signals-core ${SIGNALS_CORE_VER}:"
fetch_npm_file "@preact/signals-core" "$SIGNALS_CORE_VER" \
  "dist/signals-core.mjs" "signals-core.mjs"

echo ""
echo "@preact/signals ${SIGNALS_VER}:"
fetch_npm_file "@preact/signals" "$SIGNALS_VER" \
  "dist/signals.mjs" "signals.mjs"

echo ""
echo "HTM ${HTM_VER}:"
fetch_npm_file "htm" "$HTM_VER" \
  "dist/htm.module.js" "htm.module.js"

echo ""
echo "Done. Total vendored size:"
du -sh "$VENDOR_DIR"

echo ""
echo "Use this import map in your HTML:"
cat << 'IMPORTMAP'
<script type="importmap">
  {
    "imports": {
      "preact": "./vendor/preact.module.js",
      "preact/hooks": "./vendor/hooks.module.js",
      "@preact/signals-core": "./vendor/signals-core.mjs",
      "@preact/signals": "./vendor/signals.mjs",
      "htm": "./vendor/htm.module.js",
      "htm/preact": "./vendor/htm.module.js"
    }
  }
</script>
IMPORTMAP
