#!/usr/bin/env python3
"""
Staleness detection and manifest management.

Manages _FEATURES_MANIFEST.json which stores page hashes, descriptions,
and source tracking (code vs verified) for incremental updates.
"""

import hashlib
import json
from pathlib import Path

from .capture import PageCapture

MANIFEST_FILENAME = "_FEATURES_MANIFEST.json"


def load_manifest(codebase: Path) -> dict:
    """Load the existing features manifest.

    Args:
        codebase: Path to codebase root.

    Returns:
        Dict with manifest data, or empty dict if none exists.
    """
    manifest_path = codebase / MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_manifest(
    codebase: Path,
    captures: list[PageCapture],
    app_url: str,
    descriptions: list[dict] | None = None,
) -> Path:
    """Save the features manifest with current state.

    Args:
        codebase: Path to codebase root.
        captures: List of PageCapture with current hashes.
        app_url: Base URL of the app.
        descriptions: Optional list of description dicts to persist.

    Returns:
        Path to the written manifest file.
    """
    from datetime import datetime, timezone

    # Build description lookup
    desc_by_path: dict[str, dict] = {}
    if descriptions:
        for d in descriptions:
            text = d.get("description", "")
            if text and not text.startswith("*(unchanged"):
                desc_by_path[d["path"]] = {
                    "description": text,
                    "source": d.get("source", "code"),
                }

    # Preserve data from old manifest for pages not re-described
    old_manifest = load_manifest(codebase)
    old_pages = old_manifest.get("pages", {})

    manifest: dict = {
        "app_url": app_url,
        "updated": datetime.now(timezone.utc).isoformat(),
        "version": "0.3.0",
        "pages": {},
    }

    for c in captures:
        if c.screenshot_hash:
            entry: dict = {
                "hash": c.screenshot_hash,
                "screenshot": c.screenshot_path,
                "url": c.page.url,
            }
            if c.page.path in desc_by_path:
                entry["description"] = desc_by_path[c.page.path]["description"]
                entry["source"] = desc_by_path[c.page.path]["source"]
            elif c.page.path in old_pages and "description" in old_pages[c.page.path]:
                entry["description"] = old_pages[c.page.path]["description"]
                entry["source"] = old_pages[c.page.path].get("source", "code")
            manifest["pages"][c.page.path] = entry
        elif c.page.gated:
            manifest["pages"][c.page.path] = {
                "hash": "",
                "gated": True,
                "gate_reason": c.page.gate_reason,
            }

    # Also store code-only descriptions (pages with no capture)
    if descriptions:
        for d in descriptions:
            path = d["path"]
            if path not in manifest["pages"] and d.get("description"):
                manifest["pages"][path] = {
                    "hash": "",
                    "url": d.get("url", ""),
                    "description": d["description"],
                    "source": d.get("source", "code"),
                }

    manifest_path = codebase / MANIFEST_FILENAME
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def save_code_manifest(
    codebase: Path,
    app_url: str,
    descriptions: list[dict],
) -> Path:
    """Save a manifest for code-only analysis (no captures).

    Args:
        codebase: Path to codebase root.
        app_url: Base URL of the app.
        descriptions: Code-derived description dicts.

    Returns:
        Path to the written manifest file.
    """
    from datetime import datetime, timezone

    old_manifest = load_manifest(codebase)
    old_pages = old_manifest.get("pages", {})

    manifest: dict = {
        "app_url": app_url,
        "updated": datetime.now(timezone.utc).isoformat(),
        "version": "0.3.0",
        "pages": {},
    }

    for d in descriptions:
        path = d["path"]
        entry: dict = {
            "hash": _hash_description(d.get("description", "")),
            "url": d.get("url", ""),
            "source": d.get("source", "code"),
        }

        if d.get("description") and not d.get("error"):
            entry["description"] = d["description"]
        elif path in old_pages and "description" in old_pages[path]:
            entry["description"] = old_pages[path]["description"]
            entry["source"] = old_pages[path].get("source", "code")

        if d.get("error"):
            entry["error"] = d["error"]

        manifest["pages"][path] = entry

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


def filter_unanalyzed_pages(
    pages: list,
    old_manifest: dict,
) -> tuple[list, list]:
    """Split pages into analyzed and unanalyzed based on manifest.

    Args:
        pages: List of PageInfo.
        old_manifest: Previously saved manifest dict.

    Returns:
        Tuple of (unanalyzed, already_analyzed) page lists.
    """
    old_pages = old_manifest.get("pages", {})
    unanalyzed = []
    analyzed = []

    for p in pages:
        old_entry = old_pages.get(p.path, {})
        if old_entry.get("description") and not old_entry.get("error"):
            analyzed.append(p)
        else:
            unanalyzed.append(p)

    return unanalyzed, analyzed


def _hash_description(text: str) -> str:
    """Hash a description string for staleness detection.

    Args:
        text: Description text.

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""
