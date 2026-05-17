---
name: container-layer
description: Build and cache a personalized container environment from a Dockerfile-like spec. Supports both single-layer (one Containerfile -> one cached tarball) and multi-layer composition (compose [base, scientific, mojo, ...] into one container with each layer cached independently). Use when the user mentions "container layer", "Containerfile", "custom container", "environment setup", "cache my installs", "uv shim", "composable layers", or wants to persist package installations, skills, or environment config across ephemeral sessions. Also triggers when the user asks to snapshot, restore, or rebuild their environment, or wants to capture ad-hoc package installs into a reproducible spec.
metadata:
  version: 0.2.1
---

# Container Layer

Build a reproducible, cached environment overlay for ephemeral containers using a Dockerfile-like spec.

## Concept

The container resets every session, but your environment shouldn't. This skill:
1. Parses a `Containerfile` (Dockerfile subset) that declares your environment
2. Caches the built result as a tarball in GitHub Releases
3. Restores from cache on subsequent boots (single fetch vs. N installs)
4. Provides a `uv` shim that captures ad-hoc installs back into the Containerfile

## Supported Containerfile Instructions

```dockerfile
# Environment variables
ENV KEY=value

# Shell commands (including package installs)
RUN apt-get install -y foo        # system packages
RUN uv pip install pandas numpy   # Python packages (preferred)
RUN pip install requests          # also works

# Fetch files from URLs or GitHub
FETCH https://example.com/file.tar.gz /dest/path
FETCH github:user/repo /dest/path              # latest tarball
FETCH github:user/repo@ref /dest/path          # specific ref

# Set working directory for subsequent RUN commands
WORKDIR /some/path

# Declare paths to include in the cached layer snapshot
# (auto-detected for FETCH destinations and pip/uv installs)
SNAPSHOT /additional/path/to/capture

# Ignored (Dockerfile compat, no-op here):
# FROM, EXPOSE, CMD, ENTRYPOINT, LABEL, ARG, VOLUME, USER, SHELL
```

## Usage

### Single layer — build / restore

```python
from scripts.containerfile import ContainerLayer

layer = ContainerLayer(
    containerfile_path="/path/to/Containerfile",
    cache_repo="oaustegard/claude-container-layers",  # GitHub repo for release assets
    gh_token="...",
)

# Try cache first, fall back to full build
layer.restore_or_build()
```

Or via CLI:

```bash
python -m scripts.cli restore /path/to/Containerfile --repo user/cache-repo
```

### Multi-layer composition (v0.2.0+)

Decompose a heavy environment into named layers, each cached independently. Compose them in order on session start so most-changed bits don't invalidate stable bits.

```python
from scripts.containerfile import compose

compose(
    containerfile_paths=[
        "layers/Containerfile",            # name='base'  (always-on)
        "layers/Containerfile.scientific", # name='scientific'
        "layers/Containerfile.mojo",       # name='mojo'
    ],
    cache_repo="user/cache-repo",
)
```

Each layer gets its own cache release tag `layer-<name>-<hash>` so retention policies (keep last N) and cache invalidation operate per-name.

Default layer names are derived from the Containerfile path:
- `Containerfile`            → `base`
- `Containerfile.scientific` → `scientific`
- `layers/Containerfile.X`   → `X`

CLI equivalent:

```bash
python -m scripts.cli compose \
    layers/Containerfile \
    layers/Containerfile.scientific \
    layers/Containerfile.mojo \
    --repo user/cache-repo
```

### Per-layer name override

If filename doesn't derive cleanly, pass `--name NAME:PATH` per layer:

```bash
python -m scripts.cli compose \
    --name base:weird-named-file.txt \
    --name mojo:other-file.txt \
    weird-named-file.txt other-file.txt
```

### Single-layer naming (back-compat)

`build` / `restore` / `hash` / `inspect` accept `--name`:

```bash
python -m scripts.cli restore Containerfile.mojo --name mojo
# Cache tag becomes 'layer-mojo-<hash>' instead of 'layer-<hash>'.
# Omit --name to keep the old back-compat tag for existing callers.
```

### The uv Shim

After building, install the shim to capture future installs:
```bash
source /path/to/container-layer/scripts/uv_shim.sh /path/to/Containerfile
```

Now `uv pip install foo` both installs the package AND appends `RUN uv pip install foo` to your Containerfile.

### Rebuilding the Cache

After modifying the Containerfile:
```python
layer.build_and_push()  # Execute, snapshot, upload
```

## Architecture

Read `scripts/containerfile.py` for the parser/executor and `scripts/layer_cache.py` for the GitHub Releases caching logic. The cache key is a SHA-256 of the Containerfile contents — any change triggers a rebuild.

## Configuration

The skill expects these environment variables (or pass as constructor args):
- `GH_TOKEN` — GitHub token with `repo` scope (for releases)
- Cache repo can be any repo the token has write access to

## Workflow Integration

This skill is designed to be invoked from a boot script. Example Containerfile:

```dockerfile
# Skills
FETCH github:oaustegard/claude-skills /mnt/skills/user

# Python environment
RUN uv pip install --system pandas numpy requests

# Path config
RUN echo '/mnt/skills/user/remembering' > /usr/local/lib/python3.12/dist-packages/muninn-remembering.pth

# Custom setup
ENV MY_VAR=hello
WORKDIR /home/claude
```
