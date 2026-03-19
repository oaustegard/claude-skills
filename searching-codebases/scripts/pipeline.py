#!/usr/bin/env python3
"""
pipeline.py — full codebase search pipeline in a single invocation.

Orchestrates: download → map → index → search → extract → report
One tool call. One structured report. No drift.

Usage:
    python3 pipeline.py REPO_PATH_OR_URL "query1" ["query2" ...] [OPTIONS]

Options:
    --skip DIRS         Comma-separated dirs to skip (default: tests,.github)
    --top N             Results per query (default: 5)
    --map-only          Stop after mapping (structural overview only)
    --no-map            Skip mapping step (faster, loses _MAP.md enrichment)
    --branch NAME       Git branch for tarball download (default: main)

Output:
    Structured markdown report to stdout.
    Progress/diagnostics to stderr.

Examples:
    python3 pipeline.py https://github.com/org/repo "auth flow" "error handling"
    python3 pipeline.py ./local-repo "retry logic" --top 10
    python3 pipeline.py https://github.com/org/repo --map-only
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

# Import flowing from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flowing import task, Flow, StepState

# Import code_rag from same directory
from code_rag import Index, _format_grouped


# ── Constants ────────────────────────────────────────────────────

VENV_PYTHON = "/home/claude/.venv/bin/python"
CODEMAP_SCRIPT = None  # resolved at runtime
DEFAULT_SKIP = "tests,.github,.husky,locale,migrations,__snapshots__,coverage,target,docs,vendor"


# ── Helpers ──────────────────────────────────────────────────────

def _find_codemap() -> str:
    """Locate codemap.py from mapping-codebases skill."""
    candidates = [
        "/mnt/skills/organization/mapping-codebases/scripts/codemap.py",
        "/mnt/skills/user/mapping-codebases/scripts/codemap.py",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://") or s.startswith("github.com/")


def _parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner/repo from various GitHub URL formats."""
    url = url.rstrip("/")
    if url.startswith("github.com/"):
        url = "https://" + url
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not m:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    return m.group(1), m.group(2)


def _read_file_safe(path: str, max_lines: int = 200) -> str:
    """Read a file, truncating if too large."""
    try:
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            return "".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)\n"
        return "".join(lines)
    except OSError:
        return ""


# ── Pipeline configuration (parsed args, shared across tasks) ───

class PipelineConfig:
    def __init__(self, args: argparse.Namespace):
        self.source = args.source
        self.queries = args.queries or []
        self.skip = args.skip
        self.top_k = args.top
        self.map_only = args.map_only
        self.no_map = args.no_map
        self.branch = args.branch
        self.codemap_script = _find_codemap()


# Global config — set in main(), read by tasks
CFG: PipelineConfig = None  # type: ignore


# ── Task definitions ─────────────────────────────────────────────

@task(retry=1)
def resolve_repo():
    """Download repo tarball or validate local path. Returns repo directory."""
    source = CFG.source

    if _is_url(source):
        owner, repo = _parse_github_url(source)
        tarball_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{CFG.branch}"

        work_dir = os.path.join("/home/claude", f"_repo_{repo}")
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        tar_path = os.path.join("/home/claude", f"{repo}.tar.gz")
        print(f"[pipeline] Downloading {owner}/{repo}@{CFG.branch}...", file=sys.stderr)

        result = subprocess.run(
            ["curl", "-sL", "-o", tar_path, tarball_url],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")

        # Verify we got a tarball, not an error page
        size = os.path.getsize(tar_path)
        if size < 1000:
            with open(tar_path, "r", errors="replace") as f:
                content = f.read(500)
            if "Not Found" in content or '"message"' in content:
                raise RuntimeError(f"GitHub API error: {content[:200]}")

        result = subprocess.run(
            ["tar", "xzf", tar_path, "-C", work_dir, "--strip-components=1"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"tar extract failed: {result.stderr}")

        os.remove(tar_path)
        print(f"[pipeline] Extracted to {work_dir} ({size // 1024}KB)", file=sys.stderr)
        return work_dir
    else:
        path = os.path.abspath(source)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Not a directory: {path}")
        print(f"[pipeline] Using local repo: {path}", file=sys.stderr)
        return path


@task
def install_deps():
    """Ensure tree-sitter-language-pack is available for mapping."""
    if CFG.no_map or not CFG.codemap_script:
        return True

    if os.path.exists(VENV_PYTHON):
        # Check if tree-sitter-language-pack is importable
        result = subprocess.run(
            [VENV_PYTHON, "-c", "import tree_sitter_language_pack"],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            print("[pipeline] tree-sitter already installed", file=sys.stderr)
            return True

    print("[pipeline] Installing tree-sitter-language-pack...", file=sys.stderr)
    subprocess.run(
        ["uv", "venv", "/home/claude/.venv"],
        capture_output=True, timeout=30,
    )
    result = subprocess.run(
        ["uv", "pip", "install", "tree-sitter-language-pack",
         "--python", VENV_PYTHON],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"[pipeline] WARN: tree-sitter install failed: {result.stderr[:200]}", file=sys.stderr)
        return False
    return True


@task(depends_on=[resolve_repo, install_deps])
def generate_maps(resolve_repo, install_deps):
    """Run codemap.py to produce _MAP.md files. Returns root map content."""
    repo_path = resolve_repo

    if CFG.no_map:
        return {"skipped": True, "repo_path": repo_path, "root_map": ""}

    if not CFG.codemap_script or not install_deps:
        print("[pipeline] Skipping mapping (unavailable)", file=sys.stderr)
        return {"skipped": True, "repo_path": repo_path, "root_map": ""}

    skip_arg = CFG.skip
    print(f"[pipeline] Mapping codebase (skip: {skip_arg})...", file=sys.stderr)

    result = subprocess.run(
        [VENV_PYTHON, CFG.codemap_script, repo_path, "--skip", skip_arg],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"[pipeline] WARN: codemap failed: {result.stderr[:300]}", file=sys.stderr)
        return {"skipped": True, "repo_path": repo_path, "root_map": ""}

    # Read root _MAP.md
    root_map = os.path.join(repo_path, "_MAP.md")
    content = _read_file_safe(root_map, max_lines=300) if os.path.exists(root_map) else ""

    print(f"[pipeline] Mapping complete ({len(content)} chars root map)", file=sys.stderr)
    return {"skipped": False, "repo_path": repo_path, "root_map": content}


@task(depends_on=[generate_maps])
def search_and_extract(generate_maps):
    """Build index once, run all queries, extract top implementations."""
    map_result = generate_maps
    repo_path = map_result["repo_path"]

    if not CFG.queries:
        return {"searches": [], "repo_path": repo_path}

    # Build index once (benefits from _MAP.md if mapping ran)
    print(f"[pipeline] Building search index...", file=sys.stderr)
    idx = Index()
    idx.build(repo_path)
    stats = idx.stats()
    print(f"[pipeline] Indexed {stats.get('chunks', 0)} chunks from "
          f"{stats.get('files', 0)} files ({stats.get('build_ms', 0)}ms)",
          file=sys.stderr)

    searches = []
    for query in CFG.queries:
        print(f"[pipeline] Searching: '{query}'", file=sys.stderr)
        grouped = idx.search_grouped(query, top_k=CFG.top_k)
        formatted = _format_grouped(grouped) if grouped else "  No results above threshold."

        # Extract context for top hits
        extractions = []
        for filepath, hits in list(grouped.items())[:3]:  # top 3 files
            full_path = os.path.join(repo_path, filepath)
            if not os.path.exists(full_path):
                continue
            for chunk, score in hits[:2]:  # top 2 hits per file
                if score < 0.05:
                    continue
                # Use grep to extract context around the match
                extract = _extract_around(full_path, chunk.line, chunk.name)
                if extract:
                    extractions.append({
                        "file": filepath,
                        "line": chunk.line,
                        "name": chunk.name,
                        "score": score,
                        "code": extract,
                    })

        searches.append({
            "query": query,
            "grouped": formatted,
            "extractions": extractions,
        })

    return {"searches": searches, "repo_path": repo_path}


def _extract_around(filepath: str, line: int, name: str, context: int = 30) -> str:
    """Extract code context around a match point."""
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return ""

    # Find a good start point — look for the definition/declaration
    start = max(0, line - 2)
    end = min(len(lines), line + context)

    # Try to find the actual definition line near the reported line
    for i in range(max(0, line - 5), min(len(lines), line + 5)):
        text = lines[i] if i < len(lines) else ""
        if name in text and any(kw in text for kw in
                                ["def ", "class ", "function ", "const ", "export ",
                                 "async ", "fn ", "pub ", "func "]):
            start = i
            end = min(len(lines), i + context)
            break

    extracted = lines[start:end]
    if not extracted:
        return ""

    # Annotate with line numbers
    numbered = []
    for i, l in enumerate(extracted, start=start + 1):
        numbered.append(f"{i:4d} | {l.rstrip()}")
    return "\n".join(numbered)


@task(depends_on=[generate_maps, search_and_extract])
def compile_report(generate_maps, search_and_extract):
    """Assemble the final structured report."""
    map_result = generate_maps
    search_result = search_and_extract
    repo_path = search_result["repo_path"]

    sections = []

    # Header
    repo_name = os.path.basename(repo_path.rstrip("/"))
    sections.append(f"# Codebase Analysis: {repo_name}\n")

    # README summary (brief)
    readme_path = None
    for name in ["README.md", "README.rst", "README.txt", "README"]:
        p = os.path.join(repo_path, name)
        if os.path.exists(p):
            readme_path = p
            break
    if readme_path:
        readme_content = _read_file_safe(readme_path, max_lines=60)
        sections.append("## Overview (from README)\n")
        sections.append(readme_content)
        sections.append("")

    # Structure map
    if not map_result.get("skipped") and map_result.get("root_map"):
        sections.append("## Code Structure (_MAP.md)\n")
        sections.append(map_result["root_map"])
        sections.append("")

    # Search results
    if search_result.get("searches"):
        sections.append("## Search Results\n")
        for s in search_result["searches"]:
            sections.append(f"### Query: \"{s['query']}\"\n")
            sections.append("**Ranked matches:**")
            sections.append(f"```\n{s['grouped']}\n```\n")

            if s.get("extractions"):
                sections.append("**Extracted implementations:**\n")
                for ext in s["extractions"]:
                    sections.append(f"#### {ext['file']}:{ext['line']} — `{ext['name']}` (score: {ext['score']:.3f})\n")
                    sections.append(f"```\n{ext['code']}\n```\n")

    # Index stats
    sections.append("---")
    sections.append(f"*Pipeline: resolve → "
                    f"{'map → ' if not map_result.get('skipped') else ''}"
                    f"index → search → extract*")

    return "\n".join(sections)


# ── Main ─────────────────────────────────────────────────────────

def main():
    global CFG

    parser = argparse.ArgumentParser(
        description="Full codebase search pipeline — one invocation, one report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s https://github.com/org/repo "auth flow" "error handling"
              %(prog)s ./local-repo "retry logic" --top 10
              %(prog)s https://github.com/org/repo --map-only
        """),
    )
    parser.add_argument("source", help="GitHub URL or local directory path")
    parser.add_argument("queries", nargs="*", help="Search queries (natural language)")
    parser.add_argument("--skip", default=DEFAULT_SKIP,
                        help="Comma-separated directories to skip")
    parser.add_argument("--top", type=int, default=5,
                        help="Results per query (default: 5)")
    parser.add_argument("--map-only", action="store_true",
                        help="Stop after structural mapping")
    parser.add_argument("--no-map", action="store_true",
                        help="Skip mapping (faster, less context)")
    parser.add_argument("--branch", default="main",
                        help="Git branch for download (default: main)")

    args = parser.parse_args()
    CFG = PipelineConfig(args)

    if CFG.map_only:
        # Simplified DAG: just resolve + install + map + report
        terminal = compile_report
    else:
        terminal = compile_report

    flow = Flow(terminal, fail_fast=True)
    results = flow.run()

    # Check for failures
    failed = [r for r in results.values() if r.state == StepState.FAILED]
    if failed:
        print(f"\n[pipeline] FAILED steps:", file=sys.stderr)
        for f in failed:
            print(f"  {f.name}: {f.error}", file=sys.stderr)
        sys.exit(1)

    # Print the compiled report to stdout
    report = flow.value(compile_report)
    print(report)

    # Summary to stderr
    print(f"\n{flow.summary()}", file=sys.stderr)


if __name__ == "__main__":
    main()
