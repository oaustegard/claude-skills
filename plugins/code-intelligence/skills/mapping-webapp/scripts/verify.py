#!/usr/bin/env python3
"""
Phase 3: VERIFY — Selective visual verification of code-derived descriptions.

Orchestrates capture + describe for pages where visual verification adds value.
Uses screenshots + a11y trees to enrich code-derived behavioral descriptions.
"""

from pathlib import Path

from .capture import capture_page, PageCapture
from .describe import describe_page
from .discover import PageInfo, should_skip_verify


VERIFY_ENRICHMENT_SUFFIX = """

---
*Verified via screenshot + accessibility tree analysis.*
"""


def select_pages_for_verification(
    pages: list[PageInfo],
    code_descriptions: list[dict],
) -> list[PageInfo]:
    """Select which pages should undergo visual verification.

    Filters out pages that:
    - Are error/utility pages (404, 500, redirect)
    - Are auth-gated
    - Had no source files (nothing to verify against)

    Args:
        pages: All discovered pages.
        code_descriptions: Code-derived descriptions from analyze phase.

    Returns:
        Filtered list of pages suitable for visual verification.
    """
    # Build lookup of pages with successful code analysis
    analyzed_paths = {
        d["path"] for d in code_descriptions
        if d.get("description") and not d.get("error")
    }

    selected = []
    for page in pages:
        if should_skip_verify(page):
            continue
        # Verify pages that were successfully analyzed (have code descriptions to enrich)
        # Also verify pages that FAILED code analysis (vision might succeed where code didn't)
        selected.append(page)

    return selected


def verify_page(
    page: PageInfo,
    code_description: dict | None,
    screenshots_dir: Path,
    codebase: Path,
    viewport: str = "1280x720",
    model: str = "claude-sonnet-4-6",
) -> tuple[PageCapture, dict]:
    """Capture and verify a single page via vision.

    Args:
        page: PageInfo to verify.
        code_description: Existing code-derived description, or None.
        screenshots_dir: Directory for screenshot PNGs.
        codebase: Path to codebase root.
        viewport: Screenshot viewport dimensions.
        model: Claude model for vision.

    Returns:
        Tuple of (PageCapture, enriched_description_dict).
    """
    # Capture screenshot + a11y tree
    capture = capture_page(page, screenshots_dir, viewport)

    if capture.capture_error:
        # Vision capture failed — fall back to code description
        if code_description and code_description.get("description"):
            return capture, {
                **code_description,
                "source": "code",
            }
        return capture, {
            "path": page.path,
            "url": page.url,
            "description": "",
            "error": capture.capture_error,
            "source": "failed",
        }

    # Run vision description
    vision_desc = describe_page(capture, codebase, model)

    if vision_desc.get("error"):
        # Vision API failed — fall back to code description
        if code_description and code_description.get("description"):
            return capture, {
                **code_description,
                "source": "code",
            }
        return capture, {
            **vision_desc,
            "source": "failed",
        }

    # Merge: vision description enriches/replaces code description
    if code_description and code_description.get("description"):
        # Both available — use vision as primary (it has visual context),
        # append code analysis insights
        merged_desc = vision_desc["description"] + VERIFY_ENRICHMENT_SUFFIX
        return capture, {
            "path": page.path,
            "url": page.url,
            "description": merged_desc,
            "error": "",
            "source": "verified",
        }

    # Only vision available
    return capture, {
        **vision_desc,
        "source": "verified",
    }


def verify_pages(
    pages: list[PageInfo],
    code_descriptions: list[dict],
    screenshots_dir: Path,
    codebase: Path,
    viewport: str = "1280x720",
    model: str = "claude-sonnet-4-6",
) -> tuple[list[PageCapture], list[dict]]:
    """Verify multiple pages via vision, merging with code descriptions.

    Args:
        pages: Pages to verify.
        code_descriptions: Code-derived descriptions (for merging).
        screenshots_dir: Directory for screenshot PNGs.
        codebase: Path to codebase root.
        viewport: Screenshot viewport dimensions.
        model: Claude model for vision.

    Returns:
        Tuple of (all_captures, merged_descriptions).
    """
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Build code description lookup by path
    code_desc_by_path: dict[str, dict] = {}
    for d in code_descriptions:
        code_desc_by_path[d["path"]] = d

    all_captures = []
    verified_descriptions = []

    for page in pages:
        code_desc = code_desc_by_path.get(page.path)
        capture, desc = verify_page(
            page, code_desc, screenshots_dir, codebase, viewport, model
        )
        all_captures.append(capture)
        verified_descriptions.append(desc)

    return all_captures, verified_descriptions
