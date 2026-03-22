#!/usr/bin/env python3
"""
Phase 4: ASSEMBLE — Compile _FEATURES.md from page descriptions.

Combines all page descriptions, screenshots, and metadata into a single
_FEATURES.md document with a feature inventory.
"""

from datetime import datetime, timezone
from pathlib import Path

from .capture import PageCapture


def _relative_screenshot_path(screenshot_path: str, output_path: Path) -> str:
    """Compute a relative path from _FEATURES.md to the screenshot.

    Args:
        screenshot_path: Absolute path to screenshot PNG.
        output_path: Absolute path to the _FEATURES.md output file.

    Returns:
        Relative path string suitable for markdown image references.
    """
    try:
        screenshot = Path(screenshot_path)
        output_dir = output_path.parent
        return str(screenshot.relative_to(output_dir))
    except ValueError:
        return screenshot_path


def _page_title(desc: dict, capture: PageCapture | None) -> str:
    """Generate a section title for a page.

    Args:
        desc: Description dict with 'path' and optionally label info.
        capture: Optional PageCapture for label.

    Returns:
        Formatted title string.
    """
    label = ""
    if capture and capture.page.label:
        label = capture.page.label
    path = desc.get("path", "/")
    if label:
        return f"{label} (`{path}`)"
    return f"`{path}`"


def assemble_features_md(
    descriptions: list[dict],
    captures: list[PageCapture],
    app_url: str,
    app_name: str = "",
    output_path: Path | None = None,
) -> str:
    """Assemble a _FEATURES.md document from page descriptions.

    Args:
        descriptions: List of description dicts from describe phase.
        captures: List of PageCapture for screenshot paths.
        app_url: Base URL of the app.
        app_name: Human-readable app name (defaults to URL hostname).
        output_path: Path where _FEATURES.md will be written (for relative paths).

    Returns:
        Complete _FEATURES.md content as a string.
    """
    from urllib.parse import urlparse

    if not app_name:
        app_name = urlparse(app_url).netloc

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")

    # Build capture lookup by path
    capture_by_path: dict[str, PageCapture] = {}
    for c in captures:
        capture_by_path[c.page.path] = c

    lines = [
        f"# _FEATURES.md — {app_name}",
        f"Generated: {now}",
        f"App URL: {app_url}",
        "",
        "## Feature Inventory",
        "",
    ]

    # Summary of gated/failed pages
    gated_pages = [d for d in descriptions if d.get("error", "").startswith("GATED")]
    failed_pages = [d for d in descriptions if d.get("error", "").startswith("CAPTURE_FAILED")]
    ok_pages = [d for d in descriptions if not d.get("error")]

    if gated_pages or failed_pages:
        lines.append("### Status Summary")
        lines.append(f"- **Documented:** {len(ok_pages)} pages")
        if gated_pages:
            lines.append(f"- **Gated (auth required):** {len(gated_pages)} pages")
        if failed_pages:
            lines.append(f"- **Capture failed:** {len(failed_pages)} pages")
        lines.append("")

    # Documented pages
    for desc in descriptions:
        path = desc.get("path", "/")
        capture = capture_by_path.get(path)
        title = _page_title(desc, capture)

        lines.append(f"### {title}")

        error = desc.get("error", "")
        if error:
            lines.append(f"> **Status:** {error}")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        # Screenshot reference
        if capture and capture.screenshot_path and output_path:
            rel_path = _relative_screenshot_path(capture.screenshot_path, output_path)
            lines.append(f"![Screenshot of {path}]({rel_path})")
            lines.append("")

        # Description from Claude vision
        description = desc.get("description", "")
        if description:
            lines.append(description)
        else:
            lines.append("*(No description generated)*")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def write_features_md(
    descriptions: list[dict],
    captures: list[PageCapture],
    app_url: str,
    output_path: Path,
    app_name: str = "",
) -> Path:
    """Write the _FEATURES.md file to disk.

    Args:
        descriptions: List of description dicts.
        captures: List of PageCapture results.
        app_url: Base URL of the app.
        output_path: Where to write the file.
        app_name: Human-readable app name.

    Returns:
        Path to the written file.
    """
    content = assemble_features_md(
        descriptions, captures, app_url, app_name, output_path
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
