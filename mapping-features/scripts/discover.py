#!/usr/bin/env python3
"""
Phase 1: DISCOVER — Code-first page discovery with optional browser crawling.

Primary: discovers pages from codebase structure (_MAP.md, HTML files, route configs).
Secondary: supplements with browser crawling via webctl when available.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse


@dataclass
class PageInfo:
    """A discovered page in the app."""
    url: str
    path: str
    label: str = ""
    gated: bool = False
    gate_reason: str = ""


# Files to skip during code-based discovery
SKIP_PATTERNS = {
    "404.html", "404.htm",
    "500.html", "500.htm",
    "robots.txt", "sitemap.xml",
    ".htaccess", "favicon.ico",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".nuxt",
    "dist", "build", "coverage", ".cache", "vendor",
    "screenshots", "assets", "images", "img", "fonts",
}


def discover_from_code(
    codebase: Path,
    app_url: str,
    max_pages: int = 100,
) -> list[PageInfo]:
    """Discover pages from codebase structure without browser crawling.

    Finds pages by:
    1. Scanning for HTML files (static sites)
    2. Parsing _MAP.md for route-like patterns
    3. Looking for common router/page directory conventions

    Args:
        codebase: Path to codebase root.
        app_url: Base URL of the app (for constructing full URLs).
        max_pages: Maximum pages to discover.

    Returns:
        List of PageInfo discovered from code.
    """
    pages: list[PageInfo] = []
    seen_paths: set[str] = set()
    base_url = app_url.rstrip("/")

    def _normalize_path(p: str) -> str:
        """Normalize a path for deduplication."""
        norm = p.rstrip("/") or "/"
        # Treat /foo/index.html as /foo/
        if norm.endswith("/index.html") or norm.endswith("/index.htm"):
            norm = norm.rsplit("/index.", 1)[0] + "/"
            norm = norm.rstrip("/") or "/"
        return norm

    def _add_page(page: PageInfo) -> bool:
        norm = _normalize_path(page.path)
        if norm not in seen_paths:
            pages.append(page)
            seen_paths.add(norm)
            return True
        return False

    # Strategy 1: Find HTML files (primary for static sites)
    html_pages = _discover_html_files(codebase, base_url, max_pages)
    for page in html_pages:
        _add_page(page)
        if len(pages) >= max_pages:
            break

    # Strategy 2: Parse route patterns from common framework conventions
    if len(pages) < max_pages:
        route_pages = _discover_framework_routes(codebase, base_url)
        for page in route_pages:
            _add_page(page)
            if len(pages) >= max_pages:
                break

    # Strategy 3: Parse _MAP.md for page-like entries
    if len(pages) < max_pages:
        map_pages = _discover_from_maps(codebase, base_url)
        for page in map_pages:
            _add_page(page)
            if len(pages) >= max_pages:
                break

    return pages


def _discover_html_files(
    codebase: Path,
    base_url: str,
    max_pages: int = 100,
) -> list[PageInfo]:
    """Find HTML files in the codebase and treat them as pages.

    Args:
        codebase: Path to codebase root.
        base_url: Base URL for constructing full URLs.
        max_pages: Maximum pages to return.

    Returns:
        List of PageInfo for HTML files.
    """
    pages = []

    for html_file in sorted(codebase.rglob("*.html")):
        # Skip files in excluded directories
        parts = html_file.relative_to(codebase).parts
        if any(part in SKIP_DIRS for part in parts):
            continue

        # Skip known non-page files
        if html_file.name in SKIP_PATTERNS:
            continue

        rel_path = html_file.relative_to(codebase)
        url_path = "/" + str(rel_path)

        # Simplify index.html → parent directory
        if html_file.name == "index.html":
            url_path = "/" + str(rel_path.parent)
            if url_path == "/.":
                url_path = "/"
            elif not url_path.endswith("/"):
                url_path += "/"

        # Extract title from HTML for label
        label = _extract_html_title(html_file)

        full_url = base_url + url_path
        pages.append(PageInfo(url=full_url, path=url_path, label=label))

        if len(pages) >= max_pages:
            break

    # Also check .htm files
    for htm_file in sorted(codebase.rglob("*.htm")):
        parts = htm_file.relative_to(codebase).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        if htm_file.name in SKIP_PATTERNS:
            continue

        rel_path = htm_file.relative_to(codebase)
        url_path = "/" + str(rel_path)
        label = _extract_html_title(htm_file)
        full_url = base_url + url_path
        pages.append(PageInfo(url=full_url, path=url_path, label=label))

        if len(pages) >= max_pages:
            break

    return pages


def _extract_html_title(html_file: Path) -> str:
    """Extract the <title> content from an HTML file.

    Args:
        html_file: Path to HTML file.

    Returns:
        Title string, or empty string if not found.
    """
    try:
        content = html_file.read_text(encoding="utf-8", errors="replace")[:5000]
        match = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean up common suffixes like " | Site Name" or " - Site Name"
            return title
    except OSError:
        pass
    return ""


def _discover_framework_routes(codebase: Path, base_url: str) -> list[PageInfo]:
    """Discover routes from common framework conventions.

    Checks for:
    - Next.js/Nuxt pages/ directories
    - SvelteKit routes/ directories
    - React Router / Vue Router config files

    Args:
        codebase: Path to codebase root.
        base_url: Base URL for constructing full URLs.

    Returns:
        List of PageInfo from framework routing conventions.
    """
    pages = []

    # Next.js: pages/ or app/ directories
    for pages_dir_name in ("pages", "app", "src/pages", "src/app"):
        pages_dir = codebase / pages_dir_name
        if pages_dir.is_dir():
            for f in sorted(pages_dir.rglob("*")):
                if not f.is_file():
                    continue
                if f.suffix not in (".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"):
                    continue
                if f.name.startswith("_") or f.name.startswith("["):
                    continue  # Skip _app, _document, [slug] etc.

                rel = f.relative_to(pages_dir)
                route = "/" + str(rel.with_suffix(""))
                if route.endswith("/index"):
                    route = route[:-6] or "/"

                full_url = base_url + route
                pages.append(PageInfo(url=full_url, path=route, label=f.stem))

    # SvelteKit: src/routes/
    routes_dir = codebase / "src" / "routes"
    if routes_dir.is_dir():
        for f in sorted(routes_dir.rglob("+page.svelte")):
            rel = f.relative_to(routes_dir).parent
            route = "/" + str(rel)
            if route == "/.":
                route = "/"
            full_url = base_url + route
            pages.append(PageInfo(url=full_url, path=route, label=str(rel)))

    return pages


def _discover_from_maps(codebase: Path, base_url: str) -> list[PageInfo]:
    """Parse _MAP.md files for page-like entries.

    Looks for HTML file references and route patterns in code maps.

    Args:
        codebase: Path to codebase root.
        base_url: Base URL for constructing full URLs.

    Returns:
        List of PageInfo from _MAP.md analysis.
    """
    pages = []
    seen = set()

    root_map = codebase / "_MAP.md"
    if not root_map.exists():
        return pages

    try:
        content = root_map.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return pages

    # Look for HTML file references in _MAP.md
    html_refs = re.findall(r'\b([\w/.-]+\.html?)\b', content)
    for ref in html_refs:
        if ref in SKIP_PATTERNS:
            continue
        path = "/" + ref
        norm = path.rstrip("/") or "/"
        if norm not in seen:
            full_url = base_url + path
            pages.append(PageInfo(url=full_url, path=path, label=""))
            seen.add(norm)

    return pages


# --- Browser-based discovery (original, now secondary) ---

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
    link_pattern = re.compile(
        r'link\s+"([^"]*)".*url="([^"]*)"',
        re.IGNORECASE
    )
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

    This is the browser-based discovery method. Used as a supplement to
    code-first discovery, or when webctl is available.

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

        # Check for redirect-as-gating
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

        # Check text-based gating heuristics
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
                    if link.get("label"):
                        for p in pages:
                            if p.path == link_parsed.path and not p.label:
                                p.label = link["label"]

    return pages


def is_webctl_available() -> bool:
    """Check if webctl is installed and can be started.

    Returns:
        True if webctl is available.
    """
    try:
        result = subprocess.run(
            ["which", "webctl"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def should_skip_verify(page: PageInfo) -> bool:
    """Determine if a page should be skipped during visual verification.

    Skips pages that are unlikely to benefit from screenshot verification:
    - Error pages (404, 500)
    - Pure redirect pages
    - Very small utility pages

    Args:
        page: PageInfo to evaluate.

    Returns:
        True if this page should be skipped for visual verification.
    """
    skip_names = {"404", "500", "error", "redirect"}
    path_parts = page.path.strip("/").lower().split("/")

    for part in path_parts:
        base = part.rsplit(".", 1)[0] if "." in part else part
        if base in skip_names:
            return True

    if page.gated:
        return True

    return False


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
