"""Spoke repo discovery and registry for Muninn's hub workspace.

Manages a curated registry of repos (spokes) that Muninn works on from the
claude-workspace hub. Registry lives in Turso config; live GitHub state is
fetched on-demand via `gh` CLI or `github_api()`.

v1.0.0: Initial implementation — list, status, add, remove, discover.
"""

import json
import subprocess
from datetime import datetime, UTC

from .config import config_get, config_set


REGISTRY_KEY = "spoke-registry"
REGISTRY_CATEGORY = "ops"


def _gh_api(endpoint: str) -> dict | list | None:
    """Call GitHub API via gh CLI. Returns parsed JSON or None on failure."""
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback to github_api() from boot module
    try:
        from .boot import github_api
        return github_api(endpoint)
    except Exception:
        return None


def _load_registry() -> dict:
    """Load spoke registry from Turso. Returns dict with 'spokes' list."""
    raw = config_get(REGISTRY_KEY)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {"spokes": [], "owner": "oaustegard"}


def _save_registry(registry: dict) -> None:
    """Save spoke registry to Turso."""
    registry["updated"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    config_set(REGISTRY_KEY, json.dumps(registry), REGISTRY_CATEGORY)


def spokes_list() -> list[dict]:
    """Return registered spokes from Turso config. No GitHub API calls.

    Returns:
        List of spoke dicts with repo, description, tags, etc.
    """
    return _load_registry().get("spokes", [])


def spokes_status(repos: list[str] = None) -> str:
    """Fetch live GitHub state for registered spokes.

    Args:
        repos: Optional list of repo short names to check. None = all.

    Returns:
        Formatted status report string.
    """
    registry = _load_registry()
    spokes = registry.get("spokes", [])

    if not spokes:
        return "No spokes registered. Use spokes_add() or spokes_discover() to get started."

    if repos:
        spokes = [s for s in spokes if s["repo"].split("/")[-1] in repos]

    lines = [f"# SPOKE STATUS ({len(spokes)} repos)\n"]

    for spoke in spokes:
        repo = spoke["repo"]
        name = repo.split("/")[-1]

        # Fetch live data from GitHub
        data = _gh_api(f"repos/{repo}")
        if data:
            pushed = data.get("pushed_at", "")[:10]
            issues = data.get("open_issues_count", 0)
            lang = data.get("language", "?")
            desc = data.get("description", spoke.get("description", ""))

            lines.append(f"## {name}")
            lines.append(f"  {desc}")
            lines.append(f"  lang: {lang} | issues: {issues} | pushed: {pushed}")

            tags = spoke.get("tags", [])
            if tags:
                lines.append(f"  tags: {', '.join(tags)}")
        else:
            lines.append(f"## {name}")
            lines.append(f"  (could not reach GitHub)")

        lines.append("")

    return "\n".join(lines)


def spokes_add(repo: str, tags: list[str] = None, description: str = None) -> dict:
    """Register a new spoke repo.

    Args:
        repo: Full repo slug, e.g. "oaustegard/remex"
        tags: Optional list of tags, e.g. ["library", "active"]
        description: Optional description. Fetched from GitHub if omitted.

    Returns:
        The new spoke entry dict.
    """
    registry = _load_registry()

    # Check for duplicates
    existing = [s for s in registry["spokes"] if s["repo"] == repo]
    if existing:
        raise ValueError(f"Spoke '{repo}' already registered")

    # Fetch metadata from GitHub if description not provided
    if not description:
        data = _gh_api(f"repos/{repo}")
        if data:
            description = data.get("description", "")

    spoke = {
        "repo": repo,
        "description": description or "",
        "tags": tags or [],
        "last_synced": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    registry["spokes"].append(spoke)
    _save_registry(registry)
    return spoke


def spokes_remove(repo: str) -> bool:
    """Remove a spoke from the registry.

    Args:
        repo: Full repo slug, e.g. "oaustegard/remex"

    Returns:
        True if removed, False if not found.
    """
    registry = _load_registry()
    before = len(registry["spokes"])
    registry["spokes"] = [s for s in registry["spokes"] if s["repo"] != repo]

    if len(registry["spokes"]) < before:
        _save_registry(registry)
        return True
    return False


def spokes_discover(owner: str = "oaustegard") -> str:
    """List all repos for owner, flag which are registered vs not.

    Args:
        owner: GitHub username/org to scan.

    Returns:
        Formatted discovery report.
    """
    registry = _load_registry()
    registered = {s["repo"] for s in registry.get("spokes", [])}

    # Fetch all repos (paginated)
    repos = _gh_api(f"users/{owner}/repos?per_page=100&sort=pushed&direction=desc")
    if not repos:
        return f"Could not fetch repos for {owner}"

    lines = [f"# REPOS FOR {owner} ({len(repos)} found)\n"]

    active = []
    inactive = []

    for r in repos:
        full_name = r.get("full_name", "")
        desc = r.get("description", "") or ""
        pushed = r.get("pushed_at", "")[:10]
        is_fork = r.get("fork", False)
        is_archived = r.get("archived", False)
        is_registered = full_name in registered

        entry = {
            "name": full_name,
            "desc": desc[:60],
            "pushed": pushed,
            "fork": is_fork,
            "archived": is_archived,
            "registered": is_registered,
        }

        if is_archived or (is_fork and not is_registered):
            inactive.append(entry)
        else:
            active.append(entry)

    lines.append("## Active / Owned")
    for e in active:
        marker = "✓" if e["registered"] else "·"
        fork_tag = " [fork]" if e["fork"] else ""
        lines.append(f"  {marker} {e['name']}{fork_tag} — {e['desc']} ({e['pushed']})")

    if inactive:
        lines.append(f"\n## Archived / Forks ({len(inactive)} hidden)")
        lines.append(f"  {', '.join(e['name'].split('/')[-1] for e in inactive[:10])}")
        if len(inactive) > 10:
            lines.append(f"  ... and {len(inactive) - 10} more")

    lines.append(f"\n✓ = registered spoke | · = not registered")
    lines.append(f"Use spokes_add('owner/repo') to register")

    return "\n".join(lines)


def spokes_summary() -> str:
    """One-line summary for boot output. No API calls.

    Returns:
        Short string like "remex, claude-skills, muninn.austegard.com (3 spokes)"
    """
    spokes = spokes_list()
    if not spokes:
        return ""
    names = [s["repo"].split("/")[-1] for s in spokes]
    return f"{', '.join(names)} ({len(names)} spokes)"
