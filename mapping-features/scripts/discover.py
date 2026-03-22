#!/usr/bin/env python3
"""
Phase 1: DISCOVER — Route/page crawling via webctl.

Navigates the app entry point, extracts links from accessibility snapshots,
and builds a sitemap of reachable pages.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse


@dataclass
class PageInfo:
    """A discovered page in the app."""
    url: str
    path: str
    label: str = ""
    gated: bool = False
    gate_reason: str = ""


def run_webctl(*args: str, quiet: bool = True) -> str:
    """Run a webctl command and return stdout.

    Args:
        *args: Command arguments passed to webctl.
        quiet: Suppress webctl event output.

    Returns:
        stdout as string.

    Raises:
        subprocess.CalledProcessError: If webctl command fails.
    """
    cmd = ["webctl"]
    if quiet:
        cmd.append("--quiet")
    cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    result.check_returncode()
    return result.stdout.strip()


def extract_links_from_snapshot(snapshot_text: str, base_url: str) -> list[dict]:
    """Extract link URLs and labels from a webctl snapshot.

    Args:
        snapshot_text: Raw accessibility tree text from webctl snapshot.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with 'url', 'label' keys.
    """
    links = []
    # Match lines like: link "Home" [ref=5] url="/"
    # or: link "About" url="/about"
    link_pattern = re.compile(
        r'link\s+"([^"]*)".*url="([^"]*)"',
        re.IGNORECASE
    )
    # Also match href patterns in raw snapshot
    href_pattern = re.compile(r'href="([^"]*)"')

    for line in snapshot_text.splitlines():
        match = link_pattern.search(line)
        if match:
            label = match.group(1)
            url = match.group(2) or ""
            if url:
                full_url = urljoin(base_url, url)
                links.append({"url": full_url, "label": label})
            continue

        match = href_pattern.search(line)
        if match:
            url = match.group(1)
            if url and not url.startswith(("#", "javascript:", "mailto:")):
                full_url = urljoin(base_url, url)
                links.append({"url": full_url, "label": ""})

    return links


def is_same_origin(url: str, base_url: str) -> bool:
    """Check if url shares the same origin as base_url."""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)
    return parsed.netloc == base_parsed.netloc


def detect_gated_page(snapshot_text: str) -> tuple[bool, str]:
    """Heuristic detection of auth-gated pages.

    Args:
        snapshot_text: Accessibility tree text.

    Returns:
        (is_gated, reason) tuple.
    """
    auth_indicators = [
        (r'(?i)sign\s*in', "sign-in form detected"),
        (r'(?i)log\s*in', "login form detected"),
        (r'(?i)password', "password field detected"),
        (r'(?i)unauthorized', "unauthorized message"),
        (r'(?i)403\s*forbidden', "403 forbidden"),
        (r'(?i)authentication\s*required', "authentication required"),
    ]
    for pattern, reason in auth_indicators:
        if re.search(pattern, snapshot_text):
            return True, reason
    return False, ""


def discover_pages(app_url: str, max_pages: int = 20) -> list[PageInfo]:
    """Crawl the app starting from app_url and discover accessible pages.

    Args:
        app_url: Base URL of the running app.
        max_pages: Maximum number of pages to discover.

    Returns:
        List of PageInfo for each discovered page.
    """
    visited: set[str] = set()
    to_visit: list[str] = [app_url]
    pages: list[PageInfo] = []
    base_parsed = urlparse(app_url)

    # Ensure webctl is started
    try:
        run_webctl("status")
    except subprocess.CalledProcessError:
        run_webctl("start", "--mode", "unattended", quiet=False)

    while to_visit and len(pages) < max_pages:
        url = to_visit.pop(0)

        # Normalize URL (strip trailing slash, fragment)
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if normalized in visited:
            continue
        visited.add(normalized)

        # Navigate
        try:
            run_webctl("navigate", url)
            run_webctl("wait", "network-idle")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            pages.append(PageInfo(
                url=url,
                path=parsed.path or "/",
                label="",
                gated=True,
                gate_reason=f"navigation failed: {e}"
            ))
            continue

        # Check for redirect-as-gating: if final URL differs from intended
        is_gated = False
        gate_reason = ""
        try:
            current_url = run_webctl("evaluate", "window.location.href")
            current_path = urlparse(current_url).path.rstrip("/") or "/"
            intended_path = (parsed.path or "/").rstrip("/") or "/"
            if current_path != intended_path:
                is_gated = True
                gate_reason = f"redirected to {current_url}"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        # Capture accessibility snapshot
        try:
            snapshot = run_webctl("snapshot", "--interactive-only", "--limit", "50")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            snapshot = ""

        # Check text-based gating heuristics (if not already gated by redirect)
        if not is_gated:
            is_gated, gate_reason = detect_gated_page(snapshot)

        page = PageInfo(
            url=url,
            path=parsed.path or "/",
            label="",
            gated=is_gated,
            gate_reason=gate_reason
        )
        pages.append(page)

        # Don't crawl further from gated pages
        if is_gated:
            continue

        # Extract and queue new links
        links = extract_links_from_snapshot(snapshot, url)
        for link in links:
            link_url = link["url"]
            if is_same_origin(link_url, app_url):
                link_parsed = urlparse(link_url)
                link_normalized = f"{link_parsed.scheme}://{link_parsed.netloc}{link_parsed.path.rstrip('/')}"
                if link_normalized not in visited:
                    to_visit.append(link_url)
                    # Update label if we find one for an existing page
                    if link.get("label"):
                        for p in pages:
                            if p.path == link_parsed.path and not p.label:
                                p.label = link["label"]

    return pages


def pages_to_dict(pages: list[PageInfo]) -> list[dict]:
    """Serialize PageInfo list to JSON-compatible dicts."""
    return [
        {
            "url": p.url,
            "path": p.path,
            "label": p.label,
            "gated": p.gated,
            "gate_reason": p.gate_reason,
        }
        for p in pages
    ]
