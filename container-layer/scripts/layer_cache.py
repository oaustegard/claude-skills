"""
Layer cache: snapshot filesystem paths into a tarball and store/retrieve
via GitHub Releases on a designated repo.

Cache key = SHA-256 of Containerfile contents, used as the release tag.
"""

import json
import os
import subprocess
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional


TARBALL_NAME = "layer.tar.gz"


def _gh_api(
    endpoint: str,
    token: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    content_type: str = "application/json",
    timeout: int = 30,
) -> Optional[dict]:
    """Make a GitHub API request."""
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    if data and content_type:
        headers["Content-Type"] = content_type
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _find_release(repo: str, tag: str, token: str) -> Optional[dict]:
    """Find a release by tag."""
    return _gh_api(f"/repos/{repo}/releases/tags/{tag}", token)


def _create_release(repo: str, tag: str, token: str) -> dict:
    """Create a release (or return existing one)."""
    existing = _find_release(repo, tag, token)
    if existing:
        return existing
    
    payload = json.dumps({
        "tag_name": tag,
        "name": f"Container Layer {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')} {tag}",
        "body": "Auto-generated container layer cache. Safe to delete.",
        "draft": False,
        "prerelease": True,
    }).encode()
    
    result = _gh_api(f"/repos/{repo}/releases", token, method="POST", data=payload)
    if not result:
        raise RuntimeError(f"Failed to create release {tag} on {repo}")
    return result


def _upload_asset(upload_url: str, filepath: str, token: str):
    """Upload a release asset."""
    # upload_url has {?name,label} template suffix — strip it
    upload_url = upload_url.split("{")[0]
    upload_url += f"?name={TARBALL_NAME}"
    
    with open(filepath, "rb") as f:
        data = f.read()
    
    size_mb = len(data) / (1024 * 1024)
    print(f"  Uploading {size_mb:.1f} MB...")
    
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/gzip",
        "Content-Length": str(len(data)),
    }
    
    req = urllib.request.Request(upload_url, data=data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
        print(f"  Uploaded: {result.get('browser_download_url', 'ok')}")


def _find_asset_url(release: dict) -> Optional[str]:
    """Find the layer tarball asset URL in a release."""
    for asset in release.get("assets", []):
        if asset["name"] == TARBALL_NAME:
            return asset["url"]  # API URL (needs Accept header for download)
    return None


def try_restore(repo: str, tag: str, token: str) -> bool:
    """
    Try to restore a cached layer from GitHub Releases.
    Returns True if successfully restored, False if cache miss.
    """
    print(f"  Checking cache: {repo} @ {tag}")
    
    release = _find_release(repo, tag, token)
    if not release:
        print("  Cache miss: no release found")
        return False
    
    asset_url = _find_asset_url(release)
    if not asset_url:
        print("  Cache miss: release exists but no tarball asset")
        return False
    
    # Download the asset
    print("  Cache hit — downloading layer...")
    
    tarball = "/tmp/_layer_restore.tar.gz"
    
    # Use curl for the download since it handles redirects well
    cmd = (
        f'curl -sL -H "Authorization: token {token}" '
        f'-H "Accept: application/octet-stream" '
        f'"{asset_url}" -o "{tarball}"'
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    
    if result.returncode != 0 or not os.path.exists(tarball):
        print(f"  Download failed: {result.stderr.strip()}")
        return False
    
    size_mb = os.path.getsize(tarball) / (1024 * 1024)
    print(f"  Downloaded {size_mb:.1f} MB — extracting...")
    
    # Extract from root to restore absolute paths
    result = subprocess.run(
        f'tar -xzf "{tarball}" -C / 2>&1',
        shell=True, capture_output=True, text=True, timeout=120,
    )
    
    os.remove(tarball)
    
    if result.returncode != 0:
        # Some permission errors are expected and harmless
        errors = [l for l in result.stderr.splitlines() if "Cannot" not in l]
        if errors:
            print(f"  Extraction warnings: {'; '.join(errors[:3])}")
    
    print("  Layer restored")
    return True


def build_and_push(
    snapshot_paths: list[str],
    repo: str,
    tag: str,
    token: str,
):
    """
    Create a tarball from snapshot_paths and upload as a GitHub Release asset.
    """
    if not snapshot_paths:
        print("  No paths to snapshot")
        return
    
    # Filter to existing paths
    existing = [p for p in snapshot_paths if os.path.exists(p)]
    if not existing:
        print("  No existing paths to snapshot")
        return
    
    print(f"  Paths to snapshot:")
    for p in existing:
        # Get size
        size = subprocess.run(
            f'du -sh "{p}" 2>/dev/null | cut -f1',
            shell=True, capture_output=True, text=True,
        ).stdout.strip()
        print(f"    {p} ({size})")
    
    tarball = "/tmp/_layer_build.tar.gz"
    
    # Build tarball with absolute paths (rooted at /)
    paths_str = " ".join(f'"{p}"' for p in existing)
    cmd = f'tar -czf "{tarball}" {paths_str} 2>&1'
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    
    if not os.path.exists(tarball):
        print(f"  Tarball creation failed: {result.stderr.strip()}")
        return
    
    size_mb = os.path.getsize(tarball) / (1024 * 1024)
    print(f"  Layer tarball: {size_mb:.1f} MB")
    
    if size_mb > 2000:
        print(f"  WARNING: tarball is {size_mb:.0f} MB — GitHub release assets max at 2GB")
        os.remove(tarball)
        return
    
    # Create release and upload
    try:
        # Delete existing release if present (to replace the asset)
        existing_release = _find_release(repo, tag, token)
        if existing_release:
            _gh_api(
                f"/repos/{repo}/releases/{existing_release['id']}",
                token, method="DELETE",
            )
            print("  Replaced existing cache entry")
        
        release = _create_release(repo, tag, token)
        _upload_asset(release["upload_url"], tarball, token)
        print(f"  ✓ Layer cached as {repo} release: {tag}")
    except Exception as e:
        print(f"  Cache push failed: {e}")
    finally:
        if os.path.exists(tarball):
            os.remove(tarball)
