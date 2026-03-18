"""Render an llms.txt file from a Registry."""

from .schema import Registry


def render_llms_txt(registry: Registry) -> str:
    """Produce a plain-text skill catalog for LLM consumption."""
    lines = [
        "# Claude Skills Registry",
        f"> {registry.skill_count} skills for Claude Code and Claude.ai.",
        f"> Repository: https://github.com/{registry.repository}",
        f"> Generated: {registry.generated_at}",
        "",
        "## Skills",
        "",
    ]

    deprecated_lines: list[str] = []

    for name in sorted(registry.skills):
        entry = registry.skills[name]
        ver = f" (v{entry.version})" if entry.version else ""
        url = f"https://github.com/{registry.repository}/tree/main/{entry.directory}"

        dep_tag = ""
        if entry.deprecated:
            target = entry.superseded_by or "TBD"
            dep_tag = f" [DEPRECATED -> {target}]"
            deprecated_lines.append(
                f"- {name} -> use {target} instead"
            )

        # Truncate description to first sentence or 200 chars
        desc = entry.description
        if len(desc) > 200:
            desc = desc[:197] + "..."

        lines.append(f"- [{name}]({url}){ver}{dep_tag}: {desc}")

    if deprecated_lines:
        lines.extend(["", "## Deprecated Skills", ""])
        lines.extend(deprecated_lines)

    lines.append("")
    return "\n".join(lines)
