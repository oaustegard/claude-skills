#!/usr/bin/env python3
"""
mapping-features main entry point.

Orchestrates all four phases: discover → capture → describe → assemble.
Produces a _FEATURES.md file documenting the behavioral features of a web app.
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running as script or via package import
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.discover import discover_pages, pages_to_dict, PageInfo
from scripts.capture import capture_all_pages, PageCapture
from scripts.describe import describe_all_pages
from scripts.assemble import write_features_md
from scripts.staleness import load_manifest, save_manifest, filter_changed_pages
from scripts.auth_instructions import generate_auth_instructions


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate _FEATURES.md behavioral documentation for a web app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --app-url https://example.com --codebase /path/to/repo
  %(prog)s --app-url http://localhost:3000 --codebase . --max-pages 10
  %(prog)s --app-url https://example.com --codebase . --incremental
  %(prog)s --app-url https://example.com --codebase . --skip-describe
""",
    )
    parser.add_argument(
        "--app-url", required=True,
        help="Base URL of the running web app",
    )
    parser.add_argument(
        "--codebase", required=True, type=Path,
        help="Path to the codebase root (must contain _MAP.md files)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path for _FEATURES.md (default: <codebase>/_FEATURES.md)",
    )
    parser.add_argument(
        "--max-pages", type=int, default=20,
        help="Maximum number of pages to discover (default: 20)",
    )
    parser.add_argument(
        "--viewport", default="1280x720",
        help="Screenshot viewport as WxH (default: 1280x720)",
    )
    parser.add_argument(
        "--skip-describe", action="store_true",
        help="Capture screenshots only, skip Claude vision description",
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Only re-capture and re-describe pages with changed screenshots",
    )
    parser.add_argument(
        "--screenshots-dir", type=Path, default=None,
        help="Directory for screenshot PNGs (default: <codebase>/screenshots)",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-6",
        help="Claude model for vision descriptions (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--routes",
        help=(
            "Comma-separated list of routes (e.g. /,/demo.html,/dashboard.html) "
            "or path to a file with one route per line. Skips or supplements discover crawl."
        ),
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Discover pages only, print sitemap without capturing",
    )
    return parser.parse_args()


def main() -> int:
    """Run the feature mapping pipeline."""
    args = parse_args()

    codebase = args.codebase.resolve()
    output_path = args.output or (codebase / "_FEATURES.md")
    screenshots_dir = args.screenshots_dir or (codebase / "screenshots")

    # Validate codebase has _MAP.md
    root_map = codebase / "_MAP.md"
    if not root_map.exists():
        print(
            f"ERROR: No _MAP.md found at {root_map}. "
            "Run mapping-codebases first.",
            file=sys.stderr,
        )
        return 1

    # Phase 1: DISCOVER
    # Parse --routes if provided
    manual_routes: list[str] = []
    if args.routes:
        routes_path = Path(args.routes)
        if routes_path.is_file():
            manual_routes = [
                line.strip() for line in routes_path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        else:
            manual_routes = [r.strip() for r in args.routes.split(",") if r.strip()]

    if manual_routes:
        # Build PageInfo from manual routes
        from urllib.parse import urljoin
        route_pages = []
        for route in manual_routes:
            url = urljoin(args.app_url.rstrip("/") + "/", route.lstrip("/") or "/")
            route_pages.append(PageInfo(url=url, path=route if route.startswith("/") else "/" + route))
        if args.max_pages > 0:
            # Also run discover to find additional pages
            print(f"Phase 1: Discovering pages at {args.app_url} (seeded with {len(route_pages)} routes)...")
            discovered = discover_pages(args.app_url, max_pages=args.max_pages)
            # Merge: manual routes first, then discovered (deduplicated by path)
            seen_paths = {p.path.rstrip("/") or "/" for p in route_pages}
            for dp in discovered:
                norm = dp.path.rstrip("/") or "/"
                if norm not in seen_paths:
                    route_pages.append(dp)
                    seen_paths.add(norm)
        pages = route_pages
        print(f"  Total pages: {len(pages)} ({len(manual_routes)} from --routes)")
    else:
        print(f"Phase 1: Discovering pages at {args.app_url}...")
        pages = discover_pages(args.app_url, max_pages=args.max_pages)
        print(f"  Found {len(pages)} pages")

    for p in pages:
        status = "GATED" if p.gated else "OK"
        label = f" ({p.label})" if p.label else ""
        print(f"  [{status}] {p.path}{label}")

    if args.dry_run:
        print("\nDry run — sitemap above. No captures taken.")
        print(json.dumps(pages_to_dict(pages), indent=2))
        return 0

    # Phase 2: CAPTURE
    print(f"\nPhase 2: Capturing screenshots to {screenshots_dir}...")
    captures = capture_all_pages(pages, screenshots_dir, args.viewport)

    ok_count = sum(1 for c in captures if not c.capture_error)
    err_count = sum(1 for c in captures if c.capture_error)
    print(f"  Captured: {ok_count} | Errors: {err_count}")

    # Staleness filtering for incremental mode
    old_manifest = {}
    if args.incremental:
        old_manifest = load_manifest(codebase)
        changed, unchanged = filter_changed_pages(captures, old_manifest)
        print(f"  Incremental: {len(changed)} changed, {len(unchanged)} unchanged")
        captures_to_describe = changed
    else:
        captures_to_describe = captures

    # Save manifest with current hashes (descriptions added after describe phase)
    # Initial save for hash tracking; will be updated with descriptions later
    save_manifest(codebase, captures, args.app_url)

    # Generate auth instructions for gated pages
    auth_text = generate_auth_instructions(captures, screenshots_dir)
    if auth_text:
        auth_path = codebase / "GATED_PAGES.md"
        auth_path.write_text(auth_text, encoding="utf-8")
        print(f"\n  Auth instructions written to {auth_path}")

    if args.skip_describe:
        print("\nSkipping Phase 3 (describe). Screenshots captured only.")
        # Still assemble a skeleton _FEATURES.md
        descriptions = [
            {"path": c.page.path, "url": c.page.url, "description": "", "error": c.capture_error}
            for c in captures
        ]
        write_features_md(descriptions, captures, args.app_url, output_path)
        print(f"Skeleton _FEATURES.md written to {output_path}")
        return 0

    # Phase 3: DESCRIBE
    print(f"\nPhase 3: Describing {len(captures_to_describe)} pages via Claude vision...")
    descriptions = describe_all_pages(captures_to_describe, codebase, model=args.model)

    # Merge unchanged descriptions from previous run if incremental
    if args.incremental and old_manifest:
        old_pages = old_manifest.get("pages", {})
        for c in unchanged:
            old_entry = old_pages.get(c.page.path, {})
            prev_desc = old_entry.get("description", "")
            if prev_desc:
                descriptions.append({
                    "path": c.page.path,
                    "url": c.page.url,
                    "description": prev_desc,
                    "error": "",
                })
            else:
                # Legacy manifest without descriptions — must re-describe
                descriptions.append({
                    "path": c.page.path,
                    "url": c.page.url,
                    "description": "*(unchanged — previous description not available, re-run without --incremental)*",
                    "error": "",
                })

    desc_ok = sum(1 for d in descriptions if d.get("description") and not d.get("error"))
    desc_err = sum(1 for d in descriptions if d.get("error"))
    print(f"  Described: {desc_ok} | Errors: {desc_err}")

    # Update manifest with descriptions for future incremental runs
    save_manifest(codebase, captures, args.app_url, descriptions=descriptions)

    # Phase 4: ASSEMBLE
    print(f"\nPhase 4: Assembling _FEATURES.md...")
    write_features_md(descriptions, captures, args.app_url, output_path)
    print(f"  Written to {output_path}")

    # Summary
    gated = [c for c in captures if c.page.gated]
    print(f"\nDone. {desc_ok} pages documented, {len(gated)} gated, {desc_err} errors.")
    if gated:
        print(f"See {codebase / 'GATED_PAGES.md'} for manual capture instructions.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
