#!/usr/bin/env python3
"""
Phase 2: CAPTURE — Screenshot + accessibility tree capture via webctl.

For each discovered page, takes a screenshot, captures interactive elements,
and computes a hash for staleness detection.
"""

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .discover import PageInfo, run_webctl


@dataclass
class PageCapture:
    """Captured data for a single page."""
    page: PageInfo
    screenshot_path: str = ""
    a11y_tree: str = ""
    screenshot_hash: str = ""
    capture_error: str = ""


def _slug_from_path(url_path: str) -> str:
    """Convert a URL path to a filesystem-safe slug.

    Args:
        url_path: URL path like '/dashboard/settings'.

    Returns:
        Slug like 'dashboard-settings'. Root '/' becomes 'index'.
    """
    clean = url_path.strip("/")
    if not clean:
        return "index"
    return clean.replace("/", "-").replace(".", "-")


def hash_file(filepath: str) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        filepath: Path to the file.

    Returns:
        Hex digest string.
    """
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def capture_page(
    page: PageInfo,
    screenshots_dir: Path,
    viewport: str = "1280x720",
) -> PageCapture:
    """Navigate to a page and capture screenshot + accessibility tree.

    Args:
        page: PageInfo with URL to capture.
        screenshots_dir: Directory for saving PNGs.
        viewport: Viewport dimensions as 'WxH'.

    Returns:
        PageCapture with screenshot path, a11y tree, and hash.
    """
    if page.gated:
        return PageCapture(
            page=page,
            capture_error=f"GATED: {page.gate_reason}"
        )

    slug = _slug_from_path(page.path)
    screenshot_path = screenshots_dir / f"{slug}.png"

    # Navigate to the page
    try:
        run_webctl("navigate", page.url)
        run_webctl("wait", "network-idle")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return PageCapture(
            page=page,
            capture_error=f"CAPTURE_FAILED: navigation error: {e}"
        )

    # Take screenshot
    try:
        run_webctl("screenshot", "--path", str(screenshot_path))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return PageCapture(
            page=page,
            capture_error=f"CAPTURE_FAILED: screenshot error: {e}"
        )

    # Capture accessibility tree
    a11y_tree = ""
    try:
        a11y_tree = run_webctl("snapshot", "--interactive-only", "--limit", "50")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        a11y_tree = "(accessibility tree capture failed)"

    # Compute screenshot hash
    img_hash = ""
    if screenshot_path.exists():
        img_hash = hash_file(str(screenshot_path))

    return PageCapture(
        page=page,
        screenshot_path=str(screenshot_path),
        a11y_tree=a11y_tree,
        screenshot_hash=img_hash,
    )


def capture_all_pages(
    pages: list[PageInfo],
    screenshots_dir: Path,
    viewport: str = "1280x720",
) -> list[PageCapture]:
    """Capture screenshots and accessibility trees for all pages.

    Args:
        pages: List of discovered pages.
        screenshots_dir: Directory for saving PNGs.
        viewport: Viewport dimensions as 'WxH'.

    Returns:
        List of PageCapture results.
    """
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    captures = []
    for page in pages:
        capture = capture_page(page, screenshots_dir, viewport)
        captures.append(capture)
    return captures


def captures_to_dict(captures: list[PageCapture]) -> list[dict]:
    """Serialize captures to JSON-compatible dicts."""
    return [
        {
            "url": c.page.url,
            "path": c.page.path,
            "label": c.page.label,
            "gated": c.page.gated,
            "gate_reason": c.page.gate_reason,
            "screenshot_path": c.screenshot_path,
            "a11y_tree": c.a11y_tree,
            "screenshot_hash": c.screenshot_hash,
            "capture_error": c.capture_error,
        }
        for c in captures
    ]
