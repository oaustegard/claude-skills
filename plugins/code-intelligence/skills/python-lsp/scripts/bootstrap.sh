#!/bin/sh
# Self-install pyright so `pyright-langserver --stdio` is available.
#
# pyright wheels vendor the langserver JS bundle and run it on *system node*;
# with node present this is a single ~1.8s (cold) wheel install. With NO node,
# pyright-python falls back to downloading node from nodejs.org, which may be
# blocked in locked-down containers and can hang — so detect node and fail
# loudly rather than hang.
set -eu

if command -v pyright-langserver >/dev/null 2>&1; then
    exit 0
fi

if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: pyright requires system 'node' but none was found on PATH." >&2
    echo "       Without node, pyright tries to download it from nodejs.org," >&2
    echo "       which may be blocked and can hang. Install node (v18+) first." >&2
    exit 1
fi

if command -v uv >/dev/null 2>&1; then
    uv tool install pyright
elif command -v pipx >/dev/null 2>&1; then
    pipx install pyright
else
    echo "ERROR: need 'uv' (or 'pipx') to install pyright; neither found." >&2
    echo "       Install uv: https://docs.astral.sh/uv/" >&2
    exit 1
fi

command -v pyright-langserver >/dev/null 2>&1 || {
    echo "ERROR: installed pyright but pyright-langserver still not on PATH." >&2
    echo "       Ensure ~/.local/bin is on PATH." >&2
    exit 1
}
