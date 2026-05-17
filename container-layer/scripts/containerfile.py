"""
Containerfile parser and executor.

Parses a Dockerfile-like spec and executes the supported subset of instructions,
tracking which filesystem paths are modified for layer snapshot/caching.
"""

import hashlib
import json
import os
import re
import subprocess
import shlex
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Instructions we execute
EXECUTABLE_INSTRUCTIONS = {"ENV", "RUN", "FETCH", "WORKDIR", "SNAPSHOT"}

# Instructions we silently ignore (Dockerfile compat)
IGNORED_INSTRUCTIONS = {
    "FROM", "EXPOSE", "CMD", "ENTRYPOINT", "LABEL",
    "ARG", "VOLUME", "USER", "SHELL", "HEALTHCHECK",
    "STOPSIGNAL", "ONBUILD",
}

# Well-known paths that pip/uv/apt install into.
# `_dedup_paths` uses these as baseline keys so that auto-tracked snapshot
# paths (from RUN commands) get the diff-vs-baseline treatment instead of
# whole-tree capture.
#
# Lists all common Python versions so the diff logic works regardless of
# which interpreter is active. The single-entry list pre-0.2.1 hardcoded
# python3.12, so containers on python3.11 captured all of dist-packages
# instead of just newly-installed files.
#
# /usr/{bin,lib,share} are here so `apt-get install` layers diff correctly
# — `_exec_run` auto-adds these to snapshot_paths on any apt invocation
# (one .deb pulls in shared libs / headers / docs sprawled across all
# three). Pre-0.2.2 they fell into the whole-tree path: adding `zstd`
# to a layer captured ~3GB raw → ~600MB compressed.
#
# Despite the name, this list is no longer Python-only. Kept the name for
# backwards-compat with any external importer; consider renaming to
# BASELINED_PATHS in a future major bump.
PYTHON_INSTALL_PATHS = [
    "/usr/local/lib/python3.10/dist-packages",
    "/usr/local/lib/python3.11/dist-packages",
    "/usr/local/lib/python3.12/dist-packages",
    "/usr/local/lib/python3.13/dist-packages",
    "/usr/local/bin",
    "/usr/bin",
    "/usr/lib",
    "/usr/share",
    "/home/claude/.local/lib",
    "/home/claude/.local/bin",
]


@dataclass
class Instruction:
    """A parsed Containerfile instruction."""
    line_num: int
    directive: str
    args: str
    raw: str


@dataclass
class BuildResult:
    """Result of executing a Containerfile."""
    success: bool
    snapshot_paths: list[str]
    content_hash: str
    errors: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)


def parse_containerfile(path: str) -> list[Instruction]:
    """Parse a Containerfile into a list of Instructions."""
    instructions = []
    content = Path(path).read_text()
    
    # Handle line continuations
    content = re.sub(r'\\\n\s*', ' ', content)
    
    for line_num, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        
        # Skip comments and blank lines
        if not line or line.startswith('#'):
            continue
        
        # Extract directive and args
        match = re.match(r'^([A-Z]+)\s+(.*)', line)
        if not match:
            continue
        
        directive, args = match.group(1), match.group(2).strip()
        
        if directive in EXECUTABLE_INSTRUCTIONS:
            instructions.append(Instruction(line_num, directive, args, line))
        elif directive in IGNORED_INSTRUCTIONS:
            continue  # silently skip
        else:
            print(f"  WARNING line {line_num}: unknown instruction '{directive}', skipping")
    
    return instructions


def content_hash(path: str, extra_salt: str = "") -> str:
    """SHA-256 hash of a Containerfile's contents (the cache key).
    
    Optionally include extra_salt (e.g. a git SHA) so the cache
    invalidates when external dependencies change.
    """
    content = Path(path).read_text().strip()
    if extra_salt:
        content += f"\n# salt: {extra_salt}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def default_layer_name(containerfile_path: str) -> str:
    """Derive a default layer name from a Containerfile path.

    `Containerfile`         -> 'base'
    `Containerfile.mojo`    -> 'mojo'
    `layers/Containerfile.scientific` -> 'scientific'
    `foo/bar.txt`           -> 'bar' (fallback: file stem)

    Names are lowercased and stripped of non-[a-z0-9-_] characters so they're
    safe to embed in GitHub Release tags (`layer-<name>-<hash>`).
    """
    basename = os.path.basename(containerfile_path)
    if basename == "Containerfile":
        raw = "base"
    elif basename.startswith("Containerfile."):
        raw = basename[len("Containerfile."):]
    else:
        # Fallback: stem of whatever path was passed
        raw = os.path.splitext(basename)[0]
    # Sanitize: keep alphanumerics, hyphen, underscore, period -> hyphen
    safe = re.sub(r"[^a-z0-9_-]", "-", raw.lower()).strip("-")
    return safe or "layer"


def github_head_sha(repo: str, ref: str = "main", token: str = "") -> str:
    """Fetch the HEAD SHA of a GitHub repo ref. Returns empty string on failure."""
    try:
        url = f"https://api.github.com/repos/{repo}/commits/{ref}"
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("sha", "")[:12]
    except Exception:
        return ""


def snapshot_baseline(paths: list[str]) -> dict[str, set[str]]:
    """Capture the set of files currently in each path (for diffing later)."""
    baseline = {}
    for p in paths:
        p = os.path.normpath(p)
        if os.path.isdir(p):
            files = set()
            for root, dirs, fnames in os.walk(p):
                for f in fnames:
                    files.add(os.path.join(root, f))
            baseline[p] = files
        elif os.path.isfile(p):
            baseline[p] = {p}
        else:
            baseline[p] = set()
    return baseline


def diff_paths(baseline: dict[str, set[str]], paths: list[str]) -> list[str]:
    """
    Given a baseline snapshot and current paths, return a list of
    new/modified files to include in the layer tarball.
    For FETCH destinations (not in baseline), include everything.
    """
    new_files = []
    for p in paths:
        p = os.path.normpath(p)
        if p not in baseline:
            # New path (e.g. FETCH destination) — include whole tree
            if os.path.exists(p):
                new_files.append(p)
            continue
        
        if os.path.isdir(p):
            current = set()
            for root, dirs, fnames in os.walk(p):
                for f in fnames:
                    current.add(os.path.join(root, f))
            added = current - baseline[p]
            if added:
                new_files.extend(sorted(added))
        elif os.path.isfile(p):
            if p not in baseline[p]:
                new_files.append(p)
    
    return new_files


class ContainerfileExecutor:
    """Executes a parsed Containerfile, tracking modified paths."""
    
    def __init__(self, gh_token: Optional[str] = None):
        self.snapshot_paths: list[str] = []
        self.env: dict[str, str] = dict(os.environ)
        self.workdir: str = "/home/claude"
        self.gh_token = gh_token or os.environ.get("GH_TOKEN", "")
        self.errors: list[str] = []
        self._baseline: dict[str, set[str]] = {}
    
    def execute(self, instructions: list[Instruction]) -> BuildResult:
        """Execute all instructions, return result with snapshot paths."""
        file_hash = ""  # Caller should set this
        
        # Capture baseline of well-known install paths before building
        self._baseline = snapshot_baseline(PYTHON_INSTALL_PATHS)
        
        for inst in instructions:
            try:
                handler = getattr(self, f"_exec_{inst.directive.lower()}", None)
                if handler:
                    print(f"  [{inst.line_num}] {inst.raw}")
                    handler(inst)
                else:
                    self.errors.append(f"Line {inst.line_num}: no handler for {inst.directive}")
            except Exception as e:
                msg = f"Line {inst.line_num}: {inst.directive} failed: {e}"
                self.errors.append(msg)
                print(f"  ERROR: {msg}")
                return BuildResult(
                    success=False,
                    snapshot_paths=self._dedup_paths(),
                    content_hash=file_hash,
                    errors=self.errors,
                    env_vars={k: v for k, v in self.env.items() if k not in os.environ or os.environ[k] != v},
                )
        
        return BuildResult(
            success=True,
            snapshot_paths=self._dedup_paths(),
            content_hash=file_hash,
            errors=self.errors,
            env_vars={k: v for k, v in self.env.items() if k not in os.environ or os.environ[k] != v},
        )
    
    def _exec_env(self, inst: Instruction):
        """ENV KEY=value or ENV KEY value"""
        if '=' in inst.args:
            key, _, value = inst.args.partition('=')
            value = value.strip('"').strip("'")
        else:
            parts = inst.args.split(None, 1)
            key = parts[0]
            value = parts[1] if len(parts) > 1 else ""
        
        self.env[key.strip()] = value
        os.environ[key.strip()] = value
    
    def _exec_workdir(self, inst: Instruction):
        """WORKDIR /path"""
        path = inst.args.strip()
        os.makedirs(path, exist_ok=True)
        self.workdir = path
    
    def _exec_run(self, inst: Instruction):
        """RUN command — execute shell command, detect package installs."""
        cmd = inst.args
        
        # Detect pip/uv installs to track snapshot paths
        if re.search(r'\b(pip|uv pip)\s+install\b', cmd):
            for p in PYTHON_INSTALL_PATHS:
                if p not in self.snapshot_paths:
                    self.snapshot_paths.append(p)
            # Auto-add --break-system-packages if not present (externally managed envs)
            if '--break-system-packages' not in cmd:
                cmd = cmd.replace('install', 'install --break-system-packages', 1)
        
        # Detect apt installs
        if re.search(r'\bapt(-get)?\s+install\b', cmd):
            self.snapshot_paths.extend([
                "/usr/lib",
                "/usr/bin",
                "/usr/share",
            ])
        
        result = subprocess.run(
            cmd, shell=True, cwd=self.workdir, env=self.env,
            capture_output=True, text=True, timeout=300,
        )
        
        if result.stdout.strip():
            # Print last 5 lines of stdout to avoid noise
            lines = result.stdout.strip().splitlines()
            for line in lines[-5:]:
                print(f"    {line}")
            if len(lines) > 5:
                print(f"    ... ({len(lines) - 5} lines omitted)")
        
        if result.returncode != 0:
            raise RuntimeError(f"Command failed (exit {result.returncode}): {result.stderr.strip()}")
    
    def _exec_fetch(self, inst: Instruction):
        """FETCH source dest — fetch from URL or GitHub."""
        parts = shlex.split(inst.args)
        if len(parts) < 2:
            raise ValueError("FETCH requires <source> <dest>")
        
        source, dest = parts[0], parts[1]
        os.makedirs(dest, exist_ok=True)
        self.snapshot_paths.append(dest)
        
        if source.startswith("github:"):
            self._fetch_github(source[7:], dest)
        elif source.startswith("http://") or source.startswith("https://"):
            self._fetch_url(source, dest)
        else:
            raise ValueError(f"Unknown FETCH source: {source}")
    
    def _exec_snapshot(self, inst: Instruction):
        """SNAPSHOT /path — explicitly add a path to the snapshot."""
        path = inst.args.strip()
        if path and path not in self.snapshot_paths:
            self.snapshot_paths.append(path)
    
    def _fetch_github(self, spec: str, dest: str):
        """Fetch a GitHub repo tarball. Spec: user/repo or user/repo@ref"""
        if '@' in spec:
            repo, ref = spec.rsplit('@', 1)
        else:
            repo, ref = spec, "main"
        
        url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
        tarball = f"/tmp/_fetch_{repo.replace('/', '_')}.tar.gz"
        
        headers = ""
        if self.gh_token:
            headers = f'-H "Authorization: token {self.gh_token}"'
        
        cmd = f'curl -sL {headers} "{url}" -o "{tarball}" && tar -xzf "{tarball}" -C "{dest}" --strip-components=1 && rm -f "{tarball}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise RuntimeError(f"GitHub fetch failed: {result.stderr.strip()}")
        
        print(f"    Fetched {repo}@{ref} → {dest}")
    
    def _fetch_url(self, url: str, dest: str):
        """Fetch a URL to a destination."""
        filename = url.rsplit('/', 1)[-1] or "download"
        dest_file = os.path.join(dest, filename)
        
        cmd = f'curl -sL "{url}" -o "{dest_file}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise RuntimeError(f"URL fetch failed: {result.stderr.strip()}")
        
        # Auto-extract tarballs
        if filename.endswith(('.tar.gz', '.tgz')):
            subprocess.run(f'tar -xzf "{dest_file}" -C "{dest}" && rm -f "{dest_file}"',
                          shell=True, capture_output=True, timeout=60)
            print(f"    Fetched and extracted {filename} → {dest}")
        else:
            print(f"    Fetched {filename} → {dest}")
    
    def _dedup_paths(self) -> list[str]:
        """Deduplicate, filter, and diff snapshot paths.
        
        For paths that existed before build (pip install targets), only
        capture new files. For FETCH destinations and explicit SNAPSHOTs,
        capture everything.
        """
        seen = set()
        result = []
        
        # Separate paths into baselined (pip/apt targets) and new (FETCH/SNAPSHOT)
        baselined = set(self._baseline.keys())
        
        for p in self.snapshot_paths:
            p = os.path.normpath(p)
            if p in seen or not os.path.exists(p):
                continue
            seen.add(p)
            
            if p in baselined:
                # For baselined paths, compute diff — individual new files
                new_files = diff_paths({p: self._baseline[p]}, [p])
                result.extend(new_files)
            else:
                # For FETCH destinations and explicit SNAPSHOTs, take the whole tree
                result.append(p)
        
        return result


class ContainerLayer:
    """
    High-level interface: parse a Containerfile, execute or restore from cache.

    A layer can optionally have a `layer_name`. When set, the cache release
    tag becomes `layer-<name>-<hash>` instead of `layer-<hash>`. This enables
    composing multiple named layers (each cached independently) into a single
    container, and lets cache-retention policies operate per-name.

    Back-compat: if `layer_name` is None, the tag stays `layer-<hash>` so
    existing single-Containerfile callers don't see their cache invalidate.
    """

    def __init__(
        self,
        containerfile_path: str,
        cache_repo: str = "oaustegard/claude-container-layers",
        gh_token: Optional[str] = None,
        salt: str = "",
        layer_name: Optional[str] = None,
    ):
        self.containerfile_path = containerfile_path
        self.cache_repo = cache_repo
        self.gh_token = gh_token or os.environ.get("GH_TOKEN", "")
        self.layer_name = layer_name
        self._hash = content_hash(containerfile_path, extra_salt=salt)

    @property
    def tag(self) -> str:
        if self.layer_name:
            return f"layer-{self.layer_name}-{self._hash}"
        return f"layer-{self._hash}"
    
    def restore_or_build(self) -> BuildResult:
        """Try cache restore first, fall back to full build."""
        from . import layer_cache
        
        print(f"Container layer hash: {self._hash}")
        
        if layer_cache.try_restore(self.cache_repo, self.tag, self.gh_token):
            print("✓ Restored from cache")
            # Still need to replay ENV instructions
            instructions = parse_containerfile(self.containerfile_path)
            env_instructions = [i for i in instructions if i.directive == "ENV"]
            executor = ContainerfileExecutor(self.gh_token)
            for inst in env_instructions:
                executor._exec_env(inst)
            return BuildResult(
                success=True, snapshot_paths=[], content_hash=self._hash,
                env_vars=executor.env,
            )
        
        print("Cache miss — building from Containerfile...")
        return self.build_and_push()
    
    def build_and_push(self) -> BuildResult:
        """Execute Containerfile, snapshot, and push to cache."""
        from . import layer_cache
        
        instructions = parse_containerfile(self.containerfile_path)
        executor = ContainerfileExecutor(self.gh_token)
        result = executor.execute(instructions)
        result.content_hash = self._hash
        
        if result.success and result.snapshot_paths:
            print(f"\nSnapshotting {len(result.snapshot_paths)} paths...")
            layer_cache.build_and_push(
                result.snapshot_paths, self.cache_repo, self.tag, self.gh_token
            )
        
        return result
    
    def build_only(self) -> BuildResult:
        """Execute Containerfile without caching (for testing)."""
        instructions = parse_containerfile(self.containerfile_path)
        executor = ContainerfileExecutor(self.gh_token)
        result = executor.execute(instructions)
        result.content_hash = self._hash
        return result


def compose(
    containerfile_paths: list[str],
    cache_repo: str = "oaustegard/claude-container-layers",
    gh_token: Optional[str] = None,
    salt: str = "",
    names: Optional[list[Optional[str]]] = None,
) -> list[BuildResult]:
    """Restore (or build+push, on miss) a sequence of named layers in order.

    Each Containerfile becomes a named ContainerLayer with its own cache
    key and GitHub Release. Layers are restored sequentially — later layers'
    file modifications can overwrite earlier ones, mirroring Docker's
    additive-overlay semantics.

    Args:
        containerfile_paths: Ordered list of Containerfile paths.
        cache_repo: Single cache repo for all layers (each gets its own
            release within it, tagged `layer-<name>-<hash>`).
        gh_token: GitHub token; falls back to $GH_TOKEN.
        salt: Optional salt applied to every layer's hash (typically a
            git HEAD SHA so the whole composition invalidates together
            when the source repo advances).
        names: Optional per-layer name overrides. None entries fall back
            to `default_layer_name()`. List length must match
            `containerfile_paths` if provided.

    Returns:
        List of BuildResult, one per layer, in the same order as input.
        Stops on first failure (later layers in the list aren't attempted).
    """
    if names is not None and len(names) != len(containerfile_paths):
        raise ValueError(
            f"names length ({len(names)}) must match containerfile_paths "
            f"length ({len(containerfile_paths)})"
        )

    results: list[BuildResult] = []
    for i, cf_path in enumerate(containerfile_paths):
        explicit_name = names[i] if names else None
        name = explicit_name or default_layer_name(cf_path)
        print(f"\n=== Composing layer [{i + 1}/{len(containerfile_paths)}]: {name} ({cf_path}) ===")

        layer = ContainerLayer(
            containerfile_path=cf_path,
            cache_repo=cache_repo,
            gh_token=gh_token,
            salt=salt,
            layer_name=name,
        )
        result = layer.restore_or_build()
        results.append(result)

        if not result.success:
            print(f"\n✗ Compose halted at layer '{name}' (errors above)")
            break

    return results
