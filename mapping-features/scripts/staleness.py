#!/usr/bin/env python3
"""
Staleness detection via screenshot hash comparison.

Manages _FEATURES_MANIFEST.json which stores screenshot hashes for each page.
On re-run, unchanged pages can skip the expensive describe phase.
"""

import json
from pathlib import Path

from .capture import PageCapture

MANIFEST_FILENAME = "_FEATURES_MANIFEST.json"


def load_manifest(codebase: Path) -> dict:
    """Load the existing features manifest.

    Args:
        codebase: Path to codebase root.

    Returns:
        Dict mapping page paths to their last-known screenshot hashes and metadata.
    """
    manifest_path = codebase / MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_manifest(codebase: Path, captures: list[PageCapture], app_url: str) -> Path:
    """Save the features manifest with current screenshot hashes.

    Args:
        codebase: Path to codebase root.
        captures: List of PageCapture with current hashes.
        app_url: Base URL of the app.

    Returns:
        Path to the written manifest file.
    """
    from datetime import datetime, timezone

    manifest: dict = {
        "app_url": app_url,
        "updated": datetime.now(timezone.utc).isoformat(),
        "pages": {},
    }

    for c in captures:
        if c.screenshot_hash:
            manifest["pages"][c.page.path] = {
                "hash": c.screenshot_hash,
                "screenshot": c.screenshot_path,
                "url": c.page.url,
            }
        elif c.page.gated:
            manifest["pages"][c.page.path] = {
                "hash": "",
                "gated": True,
                "gate_reason": c.page.gate_reason,
            }

    manifest_path = codebase / MANIFEST_FILENAME
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def filter_changed_pages(
    captures: list[PageCapture],
    old_manifest: dict,
) -> tuple[list[PageCapture], list[PageCapture]]:
    """Split captures into changed and unchanged based on manifest hashes.

    Args:
        captures: Current captures with fresh screenshot hashes.
        old_manifest: Previously saved manifest dict.

    Returns:
        Tuple of (changed_captures, unchanged_captures).
    """
    old_pages = old_manifest.get("pages", {})
    changed = []
    unchanged = []

    for c in captures:
        if c.capture_error:
            changed.append(c)
            continue

        old_entry = old_pages.get(c.page.path, {})
        old_hash = old_entry.get("hash", "")

        if c.screenshot_hash and c.screenshot_hash == old_hash:
            unchanged.append(c)
        else:
            changed.append(c)

    return changed, unchanged
