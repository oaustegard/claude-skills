#!/usr/bin/env python3
"""
CLI for container-layer: build, restore, or snapshot container layers.

Single-layer mode (back-compat):
    python -m scripts.cli build /path/to/Containerfile [--repo user/repo] [--no-cache] [--name N]
    python -m scripts.cli restore /path/to/Containerfile [--repo user/repo] [--name N]
    python -m scripts.cli hash /path/to/Containerfile [--name N]
    python -m scripts.cli inspect /path/to/Containerfile

Multi-layer composition (new in v0.2.0):
    python -m scripts.cli compose <containerfile1> [<containerfile2> ...] [--repo user/repo]
        Restores each layer in order. Each layer gets its own cache release tag
        `layer-<name>-<hash>` (name derived from filename: `Containerfile.mojo`
        -> 'mojo', `Containerfile` -> 'base'). Later layers can overwrite
        earlier ones — additive Docker-like semantics.

    Per-layer name override (rare; uncommon path/filename):
        python -m scripts.cli compose --name base:Containerfile.foo --name mojo:Containerfile.bar

Cache invalidation (single or composed):
    --invalidate-on user/repo        Include repo HEAD SHA in cache key
    --invalidate-on user/repo@branch  Specific branch
    Multiple repos: --invalidate-on repo1 --invalidate-on repo2
"""

import argparse
import os
import sys

from .containerfile import (
    ContainerLayer,
    compose,
    content_hash,
    default_layer_name,
    github_head_sha,
    parse_containerfile,
)


def _compute_salt(invalidate_on: list[str], token: str) -> str:
    """Compute salt from GitHub repo HEAD SHAs."""
    if not invalidate_on:
        return ""

    parts = []
    for spec in invalidate_on:
        if "@" in spec:
            repo, ref = spec.rsplit("@", 1)
        else:
            repo, ref = spec, "main"

        sha = github_head_sha(repo, ref, token)
        if sha:
            parts.append(f"{repo}@{sha}")
            print(f"  Salt: {repo} @ {sha}")
        else:
            print(f"  WARNING: couldn't fetch HEAD for {repo}, skipping from salt")

    return "|".join(parts)


def cmd_build(args):
    """Execute the Containerfile and optionally push to cache."""
    salt = _compute_salt(args.invalidate_on or [], args.token)

    layer = ContainerLayer(
        containerfile_path=args.containerfile,
        cache_repo=args.repo,
        gh_token=args.token,
        salt=salt,
        layer_name=args.name,
    )

    if args.no_cache:
        result = layer.build_only()
    else:
        result = layer.build_and_push()

    if result.success:
        print(f"\n✓ Build complete (tag: {layer.tag})")
        if result.snapshot_paths:
            print(f"  Snapshot paths: {len(result.snapshot_paths)} entries")
        if result.env_vars:
            print(f"  Environment: {len(result.env_vars)} vars set")
    else:
        print(f"\n✗ Build failed")
        for err in result.errors:
            print(f"  {err}")
        sys.exit(1)


def cmd_restore(args):
    """Try to restore from cache, fall back to build."""
    salt = _compute_salt(args.invalidate_on or [], args.token)

    layer = ContainerLayer(
        containerfile_path=args.containerfile,
        cache_repo=args.repo,
        gh_token=args.token,
        salt=salt,
        layer_name=args.name,
    )
    result = layer.restore_or_build()

    if result.success:
        print(f"\n✓ Environment ready (tag: {layer.tag})")
    else:
        print(f"\n✗ Restore failed")
        for err in result.errors:
            print(f"  {err}")
        sys.exit(1)


def cmd_compose(args):
    """Restore (or build+push on miss) a sequence of named layers."""
    salt = _compute_salt(args.invalidate_on or [], args.token)

    # Parse --name overrides: list of "name:path" strings to (name, path) pairs.
    name_overrides: dict[str, str] = {}
    for spec in args.name or []:
        if ":" not in spec:
            print(f"✗ --name expects 'name:path', got: {spec}")
            sys.exit(2)
        name, path = spec.split(":", 1)
        name_overrides[os.path.abspath(path)] = name

    paths = args.containerfiles
    if not paths:
        print("✗ compose requires at least one Containerfile path")
        sys.exit(2)

    # Apply overrides where path matches; fall back to default derivation
    names = [name_overrides.get(os.path.abspath(p)) for p in paths]

    results = compose(
        containerfile_paths=paths,
        cache_repo=args.repo,
        gh_token=args.token,
        salt=salt,
        names=names,
    )

    succeeded = [r for r in results if r.success]
    print(
        f"\n=== Compose summary: {len(succeeded)}/{len(paths)} layers ready ==="
    )
    if len(succeeded) != len(paths):
        sys.exit(1)


def cmd_hash(args):
    """Print the cache key hash (or full tag, if --name) of a Containerfile."""
    salt = _compute_salt(args.invalidate_on or [], args.token)
    h = content_hash(args.containerfile, extra_salt=salt)
    if args.name:
        print(f"layer-{args.name}-{h}")
    else:
        print(h)


def cmd_inspect(args):
    """Parse and display the instructions in a Containerfile."""
    instructions = parse_containerfile(args.containerfile)
    salt = _compute_salt(args.invalidate_on or [], args.token)
    layer_name = args.name or default_layer_name(args.containerfile)
    h = content_hash(args.containerfile, extra_salt=salt)
    print(f"Containerfile: {args.containerfile}")
    print(f"Derived name:  {layer_name}")
    print(f"Cache key:     {h}")
    print(f"Full tag:      layer-{layer_name}-{h}")
    print(f"Instructions:  {len(instructions)}")
    print()
    for inst in instructions:
        print(f"  [{inst.line_num:3d}] {inst.directive:10s} {inst.args}")


def main():
    parser = argparse.ArgumentParser(description="Container layer manager")
    parser.add_argument(
        "--token",
        default=os.environ.get("GH_TOKEN", ""),
        help="GitHub token (default: $GH_TOKEN)",
    )
    parser.add_argument(
        "--repo",
        default="oaustegard/claude-container-layers",
        help="GitHub repo for cache storage",
    )
    parser.add_argument(
        "--invalidate-on",
        action="append",
        help="GitHub repo whose HEAD SHA is included in cache key "
        "(e.g. user/repo or user/repo@branch). Repeatable.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Execute Containerfile and cache result")
    p_build.add_argument("containerfile")
    p_build.add_argument(
        "--name",
        help="Layer name for cache release tag (default: derived from filename, "
        "e.g. 'Containerfile.mojo' -> 'mojo'). Pass empty to use old "
        "back-compat tag 'layer-<hash>'.",
    )
    p_build.add_argument("--no-cache", action="store_true", help="Skip cache push")
    p_build.set_defaults(func=cmd_build)

    p_restore = sub.add_parser("restore", help="Restore from cache or build")
    p_restore.add_argument("containerfile")
    p_restore.add_argument(
        "--name",
        help="Layer name for cache release tag (see `build --name`).",
    )
    p_restore.set_defaults(func=cmd_restore)

    p_compose = sub.add_parser(
        "compose",
        help="Restore a sequence of named layers in order (cache miss = build+push)",
    )
    p_compose.add_argument(
        "containerfiles",
        nargs="+",
        help="Ordered list of Containerfile paths to restore",
    )
    p_compose.add_argument(
        "--name",
        action="append",
        help="Per-layer name override, formatted 'name:path'. Repeatable. "
        "Paths not listed get a default name derived from filename.",
    )
    p_compose.set_defaults(func=cmd_compose)

    p_hash = sub.add_parser("hash", help="Print Containerfile cache key")
    p_hash.add_argument("containerfile")
    p_hash.add_argument(
        "--name", help="If set, prints full tag `layer-<name>-<hash>` instead of bare hash."
    )
    p_hash.set_defaults(func=cmd_hash)

    p_inspect = sub.add_parser("inspect", help="Show parsed instructions")
    p_inspect.add_argument("containerfile")
    p_inspect.add_argument(
        "--name", help="Override the layer name displayed in inspection output."
    )
    p_inspect.set_defaults(func=cmd_inspect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
