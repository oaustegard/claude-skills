"""
Resolve code sources to a local directory path.

Handles: GitHub URLs, local directories, uploaded archives,
uploaded files, project knowledge files.
"""

import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional


WORK_DIR = "/home/claude/code-search-workspace"


def resolve(source: str, branch: str = "main") -> str:
    """
    Resolve a source to a local directory path.

    Args:
        source: GitHub URL, local path, or "uploads" / "project"
        branch: Git branch for GitHub URLs

    Returns:
        Absolute path to a directory containing the code
    """
    # GitHub URL
    if source.startswith(("http://", "https://")):
        return _resolve_github(source, branch)

    # Explicit "uploads" keyword
    if source.lower() in ("uploads", "uploaded"):
        return _resolve_uploads()

    # Explicit "project" keyword
    if source.lower() in ("project", "project-knowledge"):
        return _resolve_project()

    # Archive file path
    p = os.path.expanduser(source)
    if os.path.isfile(p):
        return _resolve_archive(p)

    # Local directory
    if os.path.isdir(p):
        return os.path.abspath(p)

    raise FileNotFoundError(f"Cannot resolve source: {source}")


def _resolve_github(url: str, branch: str) -> str:
    """Download a GitHub repo tarball and extract it."""
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse GitHub URL: {url}")

    owner, repo = parts[0], parts[1]
    dest = os.path.join(WORK_DIR, f"{owner}-{repo}")

    # Clean previous download
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)

    tarball_url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{branch}"
    tar_path = os.path.join(dest, "repo.tar.gz")

    for attempt in range(3):
        try:
            urllib.request.urlretrieve(tarball_url, tar_path)
            with tarfile.open(tar_path) as tf:
                tf.extractall(dest)
            os.remove(tar_path)
            # Find extracted directory
            for entry in os.listdir(dest):
                ep = os.path.join(dest, entry)
                if os.path.isdir(ep):
                    return ep
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Failed to download {owner}/{repo}@{branch}: {e}")
            continue

    return dest


def _resolve_uploads() -> str:
    """Use uploaded files from /mnt/user-data/uploads/."""
    uploads = "/mnt/user-data/uploads"
    if not os.path.isdir(uploads):
        raise FileNotFoundError("No uploads directory found")

    entries = os.listdir(uploads)
    if not entries:
        raise FileNotFoundError("No uploaded files found")

    # If there's a single archive, extract it
    archives = [e for e in entries if e.endswith((".zip", ".tar.gz", ".tgz", ".tar"))]
    if len(archives) == 1 and len(entries) == 1:
        return _resolve_archive(os.path.join(uploads, archives[0]))

    # Otherwise use the uploads directory as-is
    return uploads


def _resolve_project() -> str:
    """Use project knowledge files from /mnt/project/."""
    project = "/mnt/project"
    if not os.path.isdir(project):
        raise FileNotFoundError("No project directory found")
    return project


def _resolve_archive(path: str) -> str:
    """Extract an archive to a temp directory."""
    dest = os.path.join(WORK_DIR, "extracted")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)

    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            zf.extractall(dest)
    elif path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path) as tf:
            tf.extractall(dest)
    elif path.endswith(".tar"):
        with tarfile.open(path) as tf:
            tf.extractall(dest)
    else:
        raise ValueError(f"Unknown archive format: {path}")

    # If archive contained a single directory, return that
    entries = os.listdir(dest)
    if len(entries) == 1 and os.path.isdir(os.path.join(dest, entries[0])):
        return os.path.join(dest, entries[0])
    return dest


def count_files(root: str, skip_dirs: set = None) -> int:
    """Quick file count for deciding whether indexing is worthwhile."""
    skip = skip_dirs or {".git", "node_modules", "__pycache__", ".venv", "venv",
                         "dist", "build", ".next", "target", "vendor"}
    count = 0
    for _, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        count += len(files)
    return count
