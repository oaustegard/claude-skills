#!/usr/bin/env python3
"""
mapping-webapp main entry point.

Orchestrates the code-first feature mapping pipeline:
  Phase 1: DISCOVER — find pages from code structure
  Phase 2: ANALYZE  — generate behavioral descriptions from source code
  Phase 3: VERIFY   — selective visual verification via browser (optional)
  Phase 4: ASSEMBLE — compile _FEATURES.md
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

# Allow running as script or via package import
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.discover import (
    discover_from_code, discover_pages, pages_to_dict, PageInfo,
    is_webctl_available, should_skip_verify,
)
from scripts.analyze import analyze_page, analyze_pages
from scripts.capture import PageCapture
from scripts.verify import select_pages_for_verification, verify_pages
from scripts.assemble import write_features_md
from scripts.staleness import (
    load_manifest, save_manifest, save_code_manifest,
    filter_changed_pages, filter_unanalyzed_pages,
)
from scripts.auth_instructions import generate_auth_instructions
from scripts.environment import detect_environment, get_batch_size, batched


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate _FEATURES.md behavioral documentation for a web app.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Code-only analysis (no browser needed):
  %(prog)s --app-url https://example.com --codebase /path/to/repo --code-only

  # Full pipeline with selective verification:
  %(prog)s --app-url https://example.com --codebase /path/to/repo

  # Incremental update (skip unchanged pages):
  %(prog)s --app-url https://example.com --codebase . --incremental

  # Verify specific pages only:
  %(prog)s --app-url https://example.com --codebase . --verify-only

  # Custom batch size:
  %(prog)s --app-url https://example.com --codebase . --batch-size 5
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
        "--max-pages", type=int, default=100,
        help="Maximum number of pages to discover (default: 100)",
    )
    parser.add_argument(
        "--viewport", default="1280x720",
        help="Screenshot viewport as WxH (default: 1280x720)",
    )
    parser.add_argument(
        "--code-only", action="store_true",
        help="Skip all vision — produce features from code analysis alone",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only run visual verification on already-analyzed pages",
    )
    parser.add_argument(
        "--skip-describe", action="store_true",
        help="(Legacy) Capture screenshots only, skip description. Use --code-only instead.",
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Only re-process pages that have changed since last run",
    )
    parser.add_argument(
        "--batch-size", type=int, default=None,
        help="Pages per batch (auto-detected from environment if not set)",
    )
    parser.add_argument(
        "--screenshots-dir", type=Path, default=None,
        help="Directory for screenshot PNGs (default: <codebase>/screenshots)",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-6",
        help="Claude model for analysis/vision (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--routes",
        help=(
            "Comma-separated routes (e.g., /,/about.html) or path to a "
            "routes file. Supplements code-based discovery."
        ),
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Discover pages only, print sitemap without analyzing",
    )
    return parser.parse_args()


def _parse_routes(routes_arg: str | None, app_url: str) -> list[PageInfo]:
    """Parse --routes argument into PageInfo list.

    Args:
        routes_arg: Raw --routes value (comma-separated or file path).
        app_url: Base URL for constructing full URLs.

    Returns:
        List of PageInfo from manual routes.
    """
    if not routes_arg:
        return []

    routes_path = Path(routes_arg)
    if routes_path.is_file():
        route_strings = [
            line.strip() for line in routes_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        route_strings = [r.strip() for r in routes_arg.split(",") if r.strip()]

    pages = []
    for route in route_strings:
        url = urljoin(app_url.rstrip("/") + "/", route.lstrip("/") or "/")
        path = route if route.startswith("/") else "/" + route
        pages.append(PageInfo(url=url, path=path))

    return pages


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

    # Detect environment for batch sizing
    env = detect_environment()
    batch_size = get_batch_size(args.batch_size, env)
    print(f"Environment: {env.name} | Batch size: {batch_size or 'unbatched'}")

    # ================================================================
    # Phase 1: DISCOVER
    # ================================================================
    print(f"\nPhase 1: Discovering pages from code structure...")

    # Code-first discovery
    pages = discover_from_code(codebase, args.app_url, max_pages=args.max_pages)
    print(f"  Found {len(pages)} pages from code")

    # Supplement with manual routes
    manual_routes = _parse_routes(args.routes, args.app_url)
    if manual_routes:
        seen_paths = {p.path.rstrip("/") or "/" for p in pages}
        added = 0
        for rp in manual_routes:
            norm = rp.path.rstrip("/") or "/"
            if norm not in seen_paths:
                pages.append(rp)
                seen_paths.add(norm)
                added += 1
        if added:
            print(f"  Added {added} pages from --routes")

    # Print discovered pages
    for p in pages:
        label = f" ({p.label})" if p.label else ""
        print(f"    {p.path}{label}")

    if args.dry_run:
        print("\nDry run — sitemap above. No analysis performed.")
        print(json.dumps(pages_to_dict(pages), indent=2))
        return 0

    if not pages:
        print("No pages discovered. Nothing to do.", file=sys.stderr)
        return 1

    # ================================================================
    # Phase 2: ANALYZE (code-first)
    # ================================================================
    old_manifest = load_manifest(codebase) if args.incremental else {}
    all_descriptions: list[dict] = []

    if args.verify_only:
        # Skip analysis, load existing descriptions from manifest
        print("\nPhase 2: Skipped (--verify-only)")
        old_pages = old_manifest.get("pages", {}) if old_manifest else {}
        for p in pages:
            entry = old_pages.get(p.path, {})
            if entry.get("description"):
                all_descriptions.append({
                    "path": p.path,
                    "url": p.url,
                    "description": entry["description"],
                    "error": "",
                    "source": entry.get("source", "code"),
                })
            else:
                all_descriptions.append({
                    "path": p.path,
                    "url": p.url,
                    "description": "",
                    "error": "NO_PRIOR: no existing description found",
                    "source": "code",
                })
    else:
        # Determine which pages need analysis
        if args.incremental and old_manifest:
            to_analyze, already_done = filter_unanalyzed_pages(pages, old_manifest)
            print(f"\nPhase 2: Analyzing {len(to_analyze)} pages "
                  f"({len(already_done)} unchanged, skipped)")
            # Carry forward existing descriptions
            old_pages = old_manifest.get("pages", {})
            for p in already_done:
                entry = old_pages.get(p.path, {})
                all_descriptions.append({
                    "path": p.path,
                    "url": p.url,
                    "description": entry.get("description", ""),
                    "error": "",
                    "source": entry.get("source", "code"),
                })
        else:
            to_analyze = pages
            print(f"\nPhase 2: Analyzing {len(to_analyze)} pages via code reading...")

        # Process in batches
        batches = batched(to_analyze, batch_size)
        for i, batch in enumerate(batches):
            if len(batches) > 1:
                print(f"  Batch {i + 1}/{len(batches)}: {len(batch)} pages...")

            batch_descs = analyze_pages(batch, codebase, model=args.model)
            all_descriptions.extend(batch_descs)

            # Checkpoint: save progress after each batch
            save_code_manifest(codebase, args.app_url, all_descriptions)

            ok = sum(1 for d in batch_descs if d.get("description") and not d.get("error"))
            err = sum(1 for d in batch_descs if d.get("error"))
            print(f"    Analyzed: {ok} | Errors: {err}")

        total_ok = sum(1 for d in all_descriptions if d.get("description") and not d.get("error"))
        total_err = sum(1 for d in all_descriptions if d.get("error"))
        print(f"  Total: {total_ok} analyzed, {total_err} errors")

    # ================================================================
    # Phase 3: VERIFY (selective vision — optional)
    # ================================================================
    all_captures: list[PageCapture] = []

    if args.code_only or args.skip_describe:
        print("\nPhase 3: Skipped (code-only mode)")
    else:
        # Check if webctl is available
        if not is_webctl_available():
            print("\nPhase 3: Skipped (webctl not available)")
            print("  Install webctl for visual verification. "
                  "Code-derived descriptions will be used.")
        else:
            # Select pages for verification
            verify_candidates = select_pages_for_verification(pages, all_descriptions)

            if args.incremental and old_manifest:
                # In incremental mode, only verify pages with changed screenshots
                # First capture all candidates to check hashes
                from scripts.capture import capture_all_pages
                temp_captures = capture_all_pages(
                    verify_candidates, screenshots_dir, args.viewport
                )
                changed, unchanged = filter_changed_pages(temp_captures, old_manifest)
                verify_candidates_filtered = [c.page for c in changed]
                all_captures.extend(temp_captures)

                if unchanged:
                    # Carry forward unchanged verified descriptions
                    old_pages = old_manifest.get("pages", {})
                    for c in unchanged:
                        entry = old_pages.get(c.page.path, {})
                        if entry.get("description") and entry.get("source") == "verified":
                            # Update the description to the verified version
                            for idx, d in enumerate(all_descriptions):
                                if d["path"] == c.page.path:
                                    all_descriptions[idx] = {
                                        "path": c.page.path,
                                        "url": c.page.url,
                                        "description": entry["description"],
                                        "error": "",
                                        "source": "verified",
                                    }
                                    break

                print(f"\nPhase 3: Verifying {len(verify_candidates_filtered)} pages "
                      f"({len(unchanged)} unchanged)")
                verify_pages_list = verify_candidates_filtered
            else:
                print(f"\nPhase 3: Verifying {len(verify_candidates)} pages via vision...")
                verify_pages_list = verify_candidates

            if verify_pages_list:
                # Build code descriptions lookup for merging
                batches = batched(verify_pages_list, batch_size)
                for i, batch in enumerate(batches):
                    if len(batches) > 1:
                        print(f"  Batch {i + 1}/{len(batches)}: {len(batch)} pages...")

                    batch_captures, batch_verified = verify_pages(
                        batch, all_descriptions, screenshots_dir,
                        codebase, args.viewport, args.model
                    )
                    all_captures.extend(batch_captures)

                    # Merge verified descriptions into all_descriptions
                    for vd in batch_verified:
                        # Replace existing description for this path
                        found = False
                        for idx, d in enumerate(all_descriptions):
                            if d["path"] == vd["path"]:
                                all_descriptions[idx] = vd
                                found = True
                                break
                        if not found:
                            all_descriptions.append(vd)

                    ok = sum(1 for d in batch_verified
                             if d.get("description") and not d.get("error"))
                    print(f"    Verified: {ok}")

            # Generate auth instructions for gated pages
            gated_captures = [c for c in all_captures if c.page.gated]
            if gated_captures:
                auth_text = generate_auth_instructions(all_captures, screenshots_dir)
                if auth_text:
                    auth_path = codebase / "GATED_PAGES.md"
                    auth_path.write_text(auth_text, encoding="utf-8")
                    print(f"  Auth instructions: {auth_path}")

    # ================================================================
    # Phase 4: ASSEMBLE
    # ================================================================
    print(f"\nPhase 4: Assembling _FEATURES.md...")

    # Sort descriptions: documented first, then errors
    all_descriptions.sort(key=lambda d: (bool(d.get("error")), d.get("path", "")))

    write_features_md(
        all_descriptions,
        all_captures if all_captures else None,
        args.app_url,
        output_path,
    )
    print(f"  Written to {output_path}")

    # Save final manifest
    if all_captures:
        save_manifest(codebase, all_captures, args.app_url, descriptions=all_descriptions)
    else:
        save_code_manifest(codebase, args.app_url, all_descriptions)

    # Summary
    ok_count = sum(1 for d in all_descriptions if d.get("description") and not d.get("error"))
    code_count = sum(1 for d in all_descriptions if d.get("source") == "code" and not d.get("error"))
    verified_count = sum(1 for d in all_descriptions if d.get("source") == "verified")
    err_count = sum(1 for d in all_descriptions if d.get("error"))
    gated_count = sum(1 for d in all_descriptions if d.get("error", "").startswith("GATED"))

    print(f"\nDone. {ok_count} pages documented "
          f"({code_count} code-analyzed, {verified_count} verified), "
          f"{gated_count} gated, {err_count} errors.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
