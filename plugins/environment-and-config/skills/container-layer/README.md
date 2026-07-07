# container-layer

Custom, cached environment overlays for Claude's ephemeral containers.

## What This Does

Claude.ai and Claude Code on the Web run in ephemeral containers — every session starts from a blank slate. This skill lets you declare your environment in a `Containerfile` (a Dockerfile subset), build it once, cache the result as a tarball in GitHub Releases, and restore it in seconds on subsequent sessions.

**First session:** parse Containerfile → execute instructions → snapshot filesystem delta → push ~3 MB tarball to GitHub Releases.

**Every session after:** download tarball → extract → done. One fetch replaces N installs.

## Components

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill metadata and documentation |
| `Containerfile` | Default environment spec (edit this) |
| `boot.sh` | Boot script for Claude.ai project instructions |
| `boot-ccotw.sh` | Boot script for Claude Code (SessionStart hook) |
| `scripts/containerfile.py` | Parser + executor with baseline diffing |
| `scripts/layer_cache.py` | GitHub Releases tarball cache |
| `scripts/cli.py` | CLI: `build`, `restore`, `hash`, `inspect` |
| `scripts/uv_shim.sh` | Captures ad-hoc `uv pip install` to Containerfile |

## Supported Instructions

```dockerfile
FETCH github:user/repo /dest          # GitHub repo tarball
FETCH github:user/repo@ref /dest      # Specific ref
RUN uv pip install --system pandas     # Shell commands
ENV KEY=value                          # Environment variables  
WORKDIR /path                          # Working directory
SNAPSHOT /path                         # Include in cached layer
```

`FROM`, `EXPOSE`, `CMD`, `ENTRYPOINT`, etc. are silently ignored (Dockerfile compatibility).

## Smart Snapshotting

The executor captures a filesystem baseline before building, then diffs against it — only new files from `pip install` / `uv pip install` are included in the tarball, not the entire `dist-packages` directory. `FETCH` destinations are captured in full. This keeps tarballs small (~3 MB for a full skills repo + Python packages).

## Cache Invalidation

The cache key is a SHA-256 of the Containerfile contents. Pass `--invalidate-on user/repo` to include a GitHub repo's HEAD SHA in the key — when that repo gets a new commit, the cache auto-invalidates and triggers a rebuild.

```bash
python3 -m scripts.cli --invalidate-on oaustegard/claude-skills restore ./Containerfile
```

## Ad-Hoc Install Capture

Source the uv shim to automatically append new installs to your Containerfile:

```bash
source ./scripts/uv_shim.sh ./Containerfile
uv pip install --system pandas    # installs AND appends RUN line
```

## Test Repo

See [container-layer-test](https://github.com/oaustegard/container-layer-test) for a working example with Claude Code on the Web SessionStart hooks.
