#!/usr/bin/env python3
"""
Generate human-in-the-loop auth instructions for gated pages.

When pages require authentication, this module produces step-by-step
instructions the user can follow to manually capture those pages.
"""

from pathlib import Path

from .capture import PageCapture


def generate_auth_instructions(
    captures: list[PageCapture],
    screenshots_dir: Path,
) -> str:
    """Generate manual capture instructions for gated pages.

    Args:
        captures: List of PageCapture results (filters to gated pages).
        screenshots_dir: Directory where screenshots should be saved.

    Returns:
        Formatted instruction text, or empty string if no gated pages.
    """
    gated = [c for c in captures if c.page.gated]
    if not gated:
        return ""

    lines = [
        "## Gated Pages — Manual Capture Required",
        "",
        "The following pages require authentication and could not be captured automatically.",
        "Follow these steps to capture them manually, then re-run with `--incremental`.",
        "",
        "### Prerequisites",
        "- webctl must be running: `webctl start --mode unattended`",
        "- You must be authenticated in the browser session",
        "",
        "### Steps",
        "",
    ]

    for i, capture in enumerate(gated, 1):
        page = capture.page
        slug = page.path.strip("/").replace("/", "-") or "index"
        screenshot_file = screenshots_dir / f"{slug}.png"
        a11y_file = screenshots_dir.parent / "captures" / f"{slug}-a11y.txt"

        lines.append(f"**Page {i}: `{page.path}`** ({page.gate_reason})")
        lines.append("")
        lines.append(f"1. Navigate to the page:")
        lines.append(f"   ```bash")
        lines.append(f'   webctl navigate "{page.url}"')
        lines.append(f"   ```")
        lines.append(f"2. Complete authentication if prompted")
        lines.append(f"3. Capture screenshot:")
        lines.append(f"   ```bash")
        lines.append(f'   webctl screenshot --path "{screenshot_file}"')
        lines.append(f"   ```")
        lines.append(f"4. Capture accessibility tree:")
        lines.append(f"   ```bash")
        lines.append(f'   webctl snapshot --interactive-only > "{a11y_file}"')
        lines.append(f"   ```")
        lines.append("")

    lines.extend([
        "### After Manual Capture",
        "",
        "Re-run mapping-webapp with `--incremental` to describe the newly captured pages:",
        "```bash",
        "python /mnt/skills/user/mapping-webapp/scripts/featuremap.py \\",
        "  --app-url <APP_URL> --codebase <CODEBASE> --incremental",
        "```",
    ])

    return "\n".join(lines)
