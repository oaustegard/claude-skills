#!/usr/bin/env python3
"""
CLI for container-layer: build, restore, or snapshot container layers.

Usage:
    python -m scripts.cli build /path/to/Containerfile [--repo user/repo] [--no-cache]
    python -m scripts.cli restore /path/to/Containerfile [--repo user/repo]
    python -m scripts.cli hash /path/to/Containerfile
    python -m scripts.cli inspect /path/to/Containerfile

Cache invalidation:
    --invalidate-on user/repo        Include repo HEAD SHA in cache key
    --invalidate-on user/repo@branch  Specific branch
    Multiple repos: --invalidate-on repo1 --invalidate-on repo2
"""

import argparse
import os
import sys

from .containerfile import ContainerLayer, parse_containerfile, content_hash, github_head_sha


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
    )
    
    if args.no_cache:
        result = layer.build_only()
    else:
        result = layer.build_and_push()
    
    if result.success:
        print(f"\n✓ Build complete (hash: {result.content_hash})")
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
    )
    result = layer.restore_or_build()
    
    if result.success:
        print(f"\n✓ Environment ready (hash: {result.content_hash})")
    else:
        print(f"\n✗ Restore failed")
        for err in result.errors:
            print(f"  {err}")
        sys.exit(1)


def cmd_hash(args):
    """Print the cache key hash of a Containerfile."""
    salt = _compute_salt(args.invalidate_on or [], args.token)
    h = content_hash(args.containerfile, extra_salt=salt)
    print(h)


def cmd_inspect(args):
    """Parse and display the instructions in a Containerfile."""
    instructions = parse_containerfile(args.containerfile)
    salt = _compute_salt(args.invalidate_on or [], args.token)
    print(f"Containerfile: {args.containerfile}")
    print(f"Cache key: {content_hash(args.containerfile, extra_salt=salt)}")
    print(f"Instructions: {len(instructions)}")
    print()
    for inst in instructions:
        print(f"  [{inst.line_num:3d}] {inst.directive:10s} {inst.args}")


def main():
    parser = argparse.ArgumentParser(description="Container layer manager")
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN", ""),
                       help="GitHub token (default: $GH_TOKEN)")
    parser.add_argument("--repo", default="oaustegard/claude-container-layers",
                       help="GitHub repo for cache storage")
    parser.add_argument("--invalidate-on", action="append",
                       help="GitHub repo whose HEAD SHA is included in cache key "
                            "(e.g. user/repo or user/repo@branch). Repeatable.")
    
    sub = parser.add_subparsers(dest="command", required=True)
    
    p_build = sub.add_parser("build", help="Execute Containerfile and cache result")
    p_build.add_argument("containerfile")
    p_build.add_argument("--no-cache", action="store_true", help="Skip cache push")
    p_build.set_defaults(func=cmd_build)
    
    p_restore = sub.add_parser("restore", help="Restore from cache or build")
    p_restore.add_argument("containerfile")
    p_restore.set_defaults(func=cmd_restore)
    
    p_hash = sub.add_parser("hash", help="Print Containerfile cache key")
    p_hash.add_argument("containerfile")
    p_hash.set_defaults(func=cmd_hash)
    
    p_inspect = sub.add_parser("inspect", help="Show parsed instructions")
    p_inspect.add_argument("containerfile")
    p_inspect.set_defaults(func=cmd_inspect)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
