#!/usr/bin/env python3
"""
Phase 3: DESCRIBE — Claude vision API prose generation.

Sends screenshots + accessibility trees + _MAP.md excerpts to Claude API
to generate behavioral descriptions, interaction inventories, and invariants.
"""

import base64
import json
import os
import sys
from pathlib import Path

from .capture import PageCapture

# Description prompt template sent to Claude vision
DESCRIBE_PROMPT = """\
You are documenting a web application's features for developer agents who cannot see the UI.

I'm showing you a screenshot of a page at `{path}` ({url}), along with its accessibility tree \
(interactive elements) and relevant code map excerpts.

Produce a structured description with these sections:

1. **What the user sees:** A concise prose description of the page — layout, key content areas, \
visual hierarchy. Describe what a sighted user would see.

2. **Interactions:** Bullet list of interactive elements and what they do. Format:
   - "Button/Link/Input label" → what happens when activated

3. **Invariants:** Behavioral rules this page must satisfy. These are testable assertions, not \
descriptions. Think: "What must always be true for this page to be correct?" Examples:
   - "Page renders without authentication"
   - "List shows at most 10 items per page"
   - "Submit button is disabled until all required fields are filled"

4. **Code:** Reference source files that implement this page's behavior. Use the _MAP.md excerpts \
provided to link features to code. Format: `src/file.js` :linenum

Keep descriptions factual and concise. Do not speculate about features not visible in the screenshot.

## Accessibility Tree (interactive elements)
```
{a11y_tree}
```

## Code Map Excerpts
```
{map_excerpts}
```
"""


def _load_screenshot_base64(screenshot_path: str) -> str:
    """Load a screenshot file and return base64-encoded content.

    Args:
        screenshot_path: Path to PNG file.

    Returns:
        Base64-encoded string.
    """
    with open(screenshot_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("ascii")


def _find_relevant_map_excerpts(codebase: Path, page_path: str) -> str:
    """Find _MAP.md excerpts potentially relevant to a page.

    Searches for _MAP.md files in common UI directories and extracts
    entries that might relate to the page path.

    Args:
        codebase: Path to the codebase root.
        page_path: URL path of the page (e.g., '/dashboard').

    Returns:
        Concatenated relevant _MAP.md excerpts.
    """
    excerpts = []

    # Gather all _MAP.md files
    map_files = list(codebase.rglob("_MAP.md"))

    # Extract route-relevant keywords from the page path
    keywords = [
        seg.lower()
        for seg in page_path.strip("/").split("/")
        if seg and len(seg) > 1
    ]

    if not keywords:
        keywords = ["index", "home", "app", "main", "landing"]

    for map_file in map_files[:10]:  # Cap to avoid excessive reads
        try:
            content = map_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Check if any keyword appears in this map file
        content_lower = content.lower()
        if any(kw in content_lower for kw in keywords):
            # Include a trimmed version (first 200 lines max)
            lines = content.splitlines()[:200]
            rel_path = map_file.relative_to(codebase)
            excerpts.append(f"### {rel_path}\n" + "\n".join(lines))

    if not excerpts:
        # Fall back to root _MAP.md
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
    """Retrieve the Anthropic API key.

    Returns:
        API key string.

    Raises:
        ValueError: If no API key is found.
    """
    # Try api-credentials skill first
    try:
        cred_path = Path("/mnt/skills/user/api-credentials/scripts")
        if cred_path.exists():
            sys.path.insert(0, str(cred_path))
            from credentials import get_anthropic_api_key
            return get_anthropic_api_key()
    except (ImportError, ValueError):
        pass

    # Fall back to environment variable
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key

    raise ValueError(
        "No Anthropic API key found. Set ANTHROPIC_API_KEY or configure "
        "the api-credentials skill."
    )


def _get_api_url() -> str:
    """Build the Anthropic API messages URL, routing through CF gateway if available.

    Returns:
        Full URL for the messages endpoint.
    """
    cf_account = os.environ.get("CF_ACCOUNT_ID", "").strip()
    cf_gateway = os.environ.get("CF_GATEWAY_ID", "").strip()
    if cf_account and cf_gateway:
        return (
            f"https://gateway.ai.cloudflare.com/v1/"
            f"{cf_account}/{cf_gateway}/anthropic/v1/messages"
        )
    return "https://api.anthropic.com/v1/messages"


def describe_page(
    capture: PageCapture,
    codebase: Path,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """Generate a behavioral description of a captured page using Claude vision.

    Args:
        capture: PageCapture with screenshot and accessibility tree.
        codebase: Path to codebase root for _MAP.md lookup.
        model: Claude model to use for vision.

    Returns:
        Dict with 'path', 'description' (raw markdown from Claude), and 'error' if any.
    """
    if capture.capture_error:
        return {
            "path": capture.page.path,
            "url": capture.page.url,
            "description": "",
            "error": capture.capture_error,
        }

    if not capture.screenshot_path or not Path(capture.screenshot_path).exists():
        return {
            "path": capture.page.path,
            "url": capture.page.url,
            "description": "",
            "error": "No screenshot available",
        }

    api_key = _get_api_key()
    screenshot_b64 = _load_screenshot_base64(capture.screenshot_path)
    map_excerpts = _find_relevant_map_excerpts(codebase, capture.page.path)

    prompt = DESCRIBE_PROMPT.format(
        path=capture.page.path,
        url=capture.page.url,
        a11y_tree=capture.a11y_tree or "(not captured)",
        map_excerpts=map_excerpts,
    )

    # Call Claude API via HTTP (no SDK dependency)
    import urllib.request

    payload = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
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
            "path": capture.page.path,
            "url": capture.page.url,
            "description": "",
            "error": f"API call failed: {e}",
        }

    # Extract text from response
    description = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            description += block["text"]

    return {
        "path": capture.page.path,
        "url": capture.page.url,
        "description": description,
        "error": "",
    }


def describe_all_pages(
    captures: list[PageCapture],
    codebase: Path,
    model: str = "claude-sonnet-4-6",
) -> list[dict]:
    """Describe all captured pages using Claude vision.

    Args:
        captures: List of PageCapture results.
        codebase: Path to codebase root.
        model: Claude model for vision.

    Returns:
        List of description dicts.
    """
    descriptions = []
    for capture in captures:
        desc = describe_page(capture, codebase, model)
        descriptions.append(desc)
    return descriptions
