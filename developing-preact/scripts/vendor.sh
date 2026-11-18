#!/usr/bin/env bash
# vendor.sh — Download Preact ecosystem ESM modules from npm registry
#
# Usage: ./vendor.sh [output_dir] [--ui-sdk]
#   output_dir: where to write vendor files (default: ./vendor)
#   --ui-sdk:   also vendor preact/compat and copy the ui-sdk component build
#               (assets/ui-sdk/) to output_dir/ui-sdk/
#
# Downloads modular ESM files (not standalone bundles) so that
# @preact/signals and ui-sdk resolve 'preact' and 'preact/hooks' via
# import map to a single shared Preact instance.

set -euo pipefail

VENDOR_DIR="./vendor"
UI_SDK=0
for arg in "$@"; do
  case "$arg" in
    --ui-sdk) UI_SDK=1 ;;
    -*) echo "Unknown option $arg" >&2; exit 2 ;;
    *) VENDOR_DIR="$arg" ;;
  esac
done
mkdir -p "$VENDOR_DIR"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Package versions. ui-sdk needs Preact 11: its parts take `ref` as a prop.
PREACT_VER="11.2.0"
SIGNALS_CORE_VER="1.14.5"
SIGNALS_VER="2.11.4"
HTM_VER="3.1.1"

# Fetch a single file from an npm package tarball.
# Args: package_name version tarball_path output_filename
fetch_npm_file() {
  local pkg="$1" ver="$2" tpath="$3" outfile="$4"
  local tarball_url

  tarball_url=$(curl -sfL "https://registry.npmjs.org/${pkg}/${ver}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['dist']['tarball'])")

  curl -sfL "$tarball_url" \
    | tar -xzf - --to-stdout "package/${tpath}" \
    > "${VENDOR_DIR}/${outfile}"

  local size
  size=$(wc -c < "${VENDOR_DIR}/${outfile}")
  if [ "$size" -eq 0 ]; then
    echo "  ✗ ${outfile}: empty, ${pkg}@${ver} has no ${tpath}" >&2
    exit 1
  fi
  echo "  ✓ ${outfile} (${size} bytes)"
}

echo "Vendoring Preact ecosystem into ${VENDOR_DIR}/"
echo ""

echo "Preact ${PREACT_VER}:"
fetch_npm_file "preact" "$PREACT_VER" "dist/preact.mjs" "preact.module.js"
fetch_npm_file "preact" "$PREACT_VER" "hooks/dist/hooks.mjs" "hooks.module.js"
if [ "$UI_SDK" -eq 1 ]; then
  fetch_npm_file "preact" "$PREACT_VER" "compat/dist/compat.mjs" "compat.module.js"
  fetch_npm_file "preact" "$PREACT_VER" "jsx-runtime/dist/jsxRuntime.mjs" "jsx-runtime.module.js"
  fetch_npm_file "preact" "$PREACT_VER" "compat/jsx-runtime.mjs" "compat-jsx-runtime.module.js"
fi

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

if [ "$UI_SDK" -eq 1 ]; then
  echo ""
  echo "ui-sdk components:"
  rm -rf "${VENDOR_DIR}/ui-sdk"
  cp -R "${SKILL_DIR}/assets/ui-sdk" "${VENDOR_DIR}/ui-sdk"
  echo "  ✓ ui-sdk/ ($(find "${VENDOR_DIR}/ui-sdk" -name '*.js' | wc -l | tr -d ' ') modules)"
fi

echo ""
echo "Done. Total vendored size:"
du -sh "$VENDOR_DIR"

echo ""
echo "Use this import map in your HTML:"
if [ "$UI_SDK" -eq 1 ]; then
cat << 'IMPORTMAP'
<script type="importmap">
  {
    "imports": {
      "preact": "./vendor/preact.module.js",
      "preact/hooks": "./vendor/hooks.module.js",
      "preact/compat": "./vendor/compat.module.js",
      "preact/jsx-runtime": "./vendor/jsx-runtime.module.js",
      "preact/compat/jsx-runtime": "./vendor/compat-jsx-runtime.module.js",
      "@preact/signals-core": "./vendor/signals-core.mjs",
      "@preact/signals": "./vendor/signals.mjs",
      "htm": "./vendor/htm.module.js",
      "ui-sdk/": "./vendor/ui-sdk/"
    }
  }
</script>
IMPORTMAP
else
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
fi
