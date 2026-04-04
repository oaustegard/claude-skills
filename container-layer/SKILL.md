---
name: container-layer
description: Build and cache a personalized container environment from a Dockerfile-like spec. Use when the user mentions "container layer", "Containerfile", "custom container", "environment setup", "cache my installs", "uv shim", or wants to persist package installations, skills, or environment config across ephemeral sessions. Also triggers when the user asks to snapshot, restore, or rebuild their environment, or wants to capture ad-hoc package installs into a reproducible spec.
metadata:
  version: 0.1.0
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

### Building / Restoring

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
