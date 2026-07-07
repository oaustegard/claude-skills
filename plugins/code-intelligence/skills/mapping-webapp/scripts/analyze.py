#!/usr/bin/env python3
"""
Phase 2: ANALYZE — Code-first behavioral analysis.

Reads source code for each discovered page and uses Claude API to generate
behavioral descriptions without requiring a browser or screenshots.
"""

import json
import os
import re
import sys
from pathlib import Path

from .discover import PageInfo


# Prompt template for code-based analysis
ANALYZE_PROMPT = """\
You are documenting a web application's features for developer agents who cannot see the UI.

I'm showing you the source code for a page at `{path}` ({url}).
Analyze this code and produce a structured behavioral description.

## Sections to produce:

1. **What the user sees:** Describe what a user would see on this page — layout, content areas, \
visual hierarchy. Infer from the HTML structure, CSS classes, and component composition.

2. **Interactions:** Bullet list of interactive elements and what they do. Format:
   - "Button/Link/Input label" → what happens when activated

3. **Invariants:** Behavioral rules this page must satisfy. These are testable assertions. Think: \
"What must always be true for this page to be correct?" Examples:
   - "Page renders without authentication"
   - "Navigation links are present in header"
   - "Form validates required fields before submission"

4. **Code:** Reference the source files that implement this page. Format: `path/file.ext` :linenum

Keep descriptions factual and concise. Infer behavior from code structure — do not speculate \
about features not present in the source.

## Source Code
```
{source_code}
```

## Code Map Context
```
{map_excerpts}
```
"""


def _find_source_files(codebase: Path, page_path: str) -> list[Path]:
    """Find source files relevant to a page path.

    For static sites: finds the HTML file directly.
    For SPAs: looks for components matching the route name.

    Args:
        codebase: Path to codebase root.
        page_path: URL path (e.g., '/dashboard', '/about.html').

    Returns:
        List of source file paths, ordered by relevance.
    """
    sources = []
    clean_path = page_path.strip("/")

    # Direct file match (static sites)
    if clean_path:
        candidates = [
            codebase / clean_path,
            codebase / f"{clean_path}.html",
            codebase / f"{clean_path}/index.html",
        ]
    else:
        candidates = [
            codebase / "index.html",
        ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            sources.append(candidate)
            break  # Take the first direct match

    # Look for associated JS/CSS/TS files
    if clean_path:
        # Extract the base name for matching
        base_name = clean_path.rsplit("/", 1)[-1]
        base_name = base_name.rsplit(".", 1)[0] if "." in base_name else base_name

        # Search for component/module files matching the page name
        for ext in (".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte"):
            for match in codebase.rglob(f"*{base_name}*{ext}"):
                if match not in sources and "node_modules" not in str(match):
                    sources.append(match)
                    if len(sources) >= 5:  # Cap to avoid reading too many files
                        break

    # Look for referenced scripts in the HTML source
    if sources and sources[0].suffix in (".html", ".htm"):
        html_content = sources[0].read_text(encoding="utf-8", errors="replace")
        script_refs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html_content)
        style_refs = re.findall(r'<link[^>]+href=["\']([^"\']+\.css)["\']', html_content)
        for ref in script_refs + style_refs:
            if ref.startswith(("http://", "https://", "//")):
                continue  # Skip external resources
            ref_path = (sources[0].parent / ref).resolve()
            if ref_path.exists() and ref_path not in sources:
                sources.append(ref_path)

    return sources[:8]  # Cap total files


def _read_source_context(codebase: Path, page_path: str, max_chars: int = 15000) -> str:
    """Read source files for a page and prepare a combined context string.

    Args:
        codebase: Path to codebase root.
        page_path: URL path of the page.
        max_chars: Maximum total characters to include.

    Returns:
        Combined source code string with file headers.
    """
    sources = _find_source_files(codebase, page_path)
    if not sources:
        return "(no source files found for this page)"

    parts = []
    total_chars = 0

    for src in sources:
        try:
            content = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel_path = src.relative_to(codebase)
        header = f"### {rel_path}"

        # Truncate individual files if too large
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        if len(content) > remaining:
            content = content[:remaining] + "\n... (truncated)"

        parts.append(f"{header}\n{content}")
        total_chars += len(header) + len(content)

    return "\n\n".join(parts) if parts else "(no readable source files)"


def _find_relevant_map_excerpts(codebase: Path, page_path: str) -> str:
    """Find _MAP.md excerpts relevant to a page.

    Args:
        codebase: Path to codebase root.
        page_path: URL path of the page.

    Returns:
        Concatenated relevant _MAP.md excerpts.
    """
    excerpts = []
    map_files = list(codebase.rglob("_MAP.md"))

    keywords = [
        seg.lower()
        for seg in page_path.strip("/").split("/")
        if seg and len(seg) > 1
    ]
    # Also strip file extensions from keywords
    keywords = [kw.rsplit(".", 1)[0] if "." in kw else kw for kw in keywords]

    if not keywords:
        keywords = ["index", "home", "app", "main"]

    for map_file in map_files[:10]:
        try:
            content = map_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        content_lower = content.lower()
        if any(kw in content_lower for kw in keywords):
            lines = content.splitlines()[:200]
            rel_path = map_file.relative_to(codebase)
            excerpts.append(f"### {rel_path}\n" + "\n".join(lines))

    if not excerpts:
        root_map = codebase / "_MAP.md"
        if root_map.exists():
            try:
                content = root_map.read_text(encoding="utf-8")
                lines = content.splitlines()[:100]
                excerpts.append("### _MAP.md (root)\n" + "\n".join(lines))
            except (OSError, UnicodeDecodeError):
                pass

    return "\n\n".join(excerpts) if excerpts else "(no _MAP.md excerpts found)"


def _get_api_key() -> str:
    """Retrieve the Anthropic API key."""
    try:
        cred_path = Path("/mnt/skills/user/api-credentials/scripts")
        if cred_path.exists():
            sys.path.insert(0, str(cred_path))
            from credentials import get_anthropic_api_key
            return get_anthropic_api_key()
    except (ImportError, ValueError):
        pass

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key

    raise ValueError(
        "No Anthropic API key found. Set ANTHROPIC_API_KEY or configure "
        "the api-credentials skill."
    )


def _get_api_url() -> str:
    """Build the Anthropic API messages URL."""
    cf_account = os.environ.get("CF_ACCOUNT_ID", "").strip()
    cf_gateway = os.environ.get("CF_GATEWAY_ID", "").strip()
    if cf_account and cf_gateway:
        return (
            f"https://gateway.ai.cloudflare.com/v1/"
            f"{cf_account}/{cf_gateway}/anthropic/v1/messages"
        )
    return "https://api.anthropic.com/v1/messages"


def analyze_page(
    page: PageInfo,
    codebase: Path,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """Generate a behavioral description of a page by analyzing its source code.

    Args:
        page: PageInfo with path and URL.
        codebase: Path to codebase root.
        model: Claude model for text analysis.

    Returns:
        Dict with 'path', 'url', 'description', 'error', 'source': 'code'.
    """
    source_code = _read_source_context(codebase, page.path)
    if source_code.startswith("(no "):
        return {
            "path": page.path,
            "url": page.url,
            "description": "",
            "error": f"NO_SOURCE: no source files found for {page.path}",
            "source": "code",
        }

    map_excerpts = _find_relevant_map_excerpts(codebase, page.path)

    prompt = ANALYZE_PROMPT.format(
        path=page.path,
        url=page.url,
        source_code=source_code,
        map_excerpts=map_excerpts,
    )

    api_key = _get_api_key()
    import urllib.request

    payload = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }).encode("utf-8")

    api_url = _get_api_url()
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        return {
            "path": page.path,
            "url": page.url,
            "description": "",
            "error": f"API call failed: {e}",
            "source": "code",
        }

    description = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            description += block["text"]

    return {
        "path": page.path,
        "url": page.url,
        "description": description,
        "error": "",
        "source": "code",
    }


def analyze_pages(
    pages: list[PageInfo],
    codebase: Path,
    model: str = "claude-sonnet-4-6",
) -> list[dict]:
    """Analyze all pages via code reading.

    Args:
        pages: List of discovered pages.
        codebase: Path to codebase root.
        model: Claude model for text analysis.

    Returns:
        List of description dicts with 'source': 'code'.
    """
    descriptions = []
    for page in pages:
        desc = analyze_page(page, codebase, model)
        descriptions.append(desc)
    return descriptions
