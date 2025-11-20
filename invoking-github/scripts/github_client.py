#!/usr/bin/env python3
"""
GitHub API Client for Claude.ai Chat Environments

Provides programmatic GitHub operations (read/write/commit/PR) using REST API.
Designed for claude.ai chat where native git access isn't available.
"""

import json
import sys
import base64
from pathlib import Path
from typing import Dict, List, Optional
from urllib import request, error, parse


class GitHubAPIError(Exception):
    """
    Custom exception for GitHub API errors.

    Attributes:
        message: Error description
        status_code: HTTP status code (if applicable)
        response: Full response data (if available)
    """
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


def get_github_token() -> str:
    """
    Get GitHub API token from project knowledge files.

    Priority order:
    1. Individual file: /mnt/project/GITHUB_API_KEY.txt
    2. Combined file: /mnt/project/API_CREDENTIALS.json

    Returns:
        str: GitHub Personal Access Token

    Raises:
        ValueError: If no token found in any source
    """
    # Pattern 1: Individual key file (recommended)
    key_file = Path("/mnt/project/GITHUB_API_KEY.txt")
    if key_file.exists():
        try:
            token = key_file.read_text().strip()
            if token:
                return token
        except (IOError, OSError) as e:
            raise ValueError(
                f"Found GITHUB_API_KEY.txt but couldn't read it: {e}\n"
                f"Please check file permissions or recreate the file"
            )

    # Pattern 2: Combined credentials file
    creds_file = Path("/mnt/project/API_CREDENTIALS.json")
    if creds_file.exists():
        try:
            with open(creds_file) as f:
                config = json.load(f)
                token = config.get("github_api_key", "").strip()
                if token:
                    return token
        except (json.JSONDecodeError, IOError, OSError) as e:
            raise ValueError(
                f"Found API_CREDENTIALS.json but couldn't parse it: {e}\n"
                f"Please check file format"
            )

    # No token found - provide helpful error message
    raise ValueError(
        "No GitHub API token found!\n\n"
        "Add a project knowledge file using one of these methods:\n\n"
        "Option 1 (recommended): Individual file\n"
        "  File: GITHUB_API_KEY.txt\n"
        "  Content: ghp_...\n\n"
        "Option 2: Combined file\n"
        "  File: API_CREDENTIALS.json\n"
        "  Content: {\"github_api_key\": \"ghp_...\"}\n\n"
        "Generate token at: https://github.com/settings/tokens\n"
        "Required scopes:\n"
        "  - Classic token: 'repo' scope\n"
        "  - Fine-grained token: Repository permissions → Contents (read/write) + Pull requests (read/write)\n\n"
        "Note: GitHub OAuth in claude.ai UI is not accessible to skills"
    )


def _make_api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict] = None,
    token: Optional[str] = None
) -> Dict:
    """
    Make authenticated GitHub API request.

    Args:
        endpoint: API endpoint (e.g., "/repos/owner/name/contents/file")
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        data: Request body (will be JSON-encoded)
        token: GitHub API token (if None, will fetch automatically)

    Returns:
        Dict: Parsed JSON response

    Raises:
        GitHubAPIError: On API errors
    """
    if token is None:
        token = get_github_token()

    url = f"https://api.github.com{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Claude-Invoking-GitHub-Skill/1.0"
    }

    # Prepare request
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode('utf-8')
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with request.urlopen(req) as response:
            response_data = response.read().decode('utf-8')
            if response_data:
                return json.loads(response_data)
            return {}

    except error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_body)
            error_message = error_json.get('message', str(e))
        except json.JSONDecodeError:
            error_message = error_body or str(e)

        # Provide helpful error messages based on status code
        if e.code == 401:
            raise GitHubAPIError(
                "Authentication failed. Please check your GitHub token is valid and not expired.",
                status_code=401,
                response=error_json if 'error_json' in locals() else None
            )
        elif e.code == 403:
            if 'rate limit' in error_message.lower():
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded. Please wait before making more requests.",
                    status_code=403,
                    response=error_json if 'error_json' in locals() else None
                )
            else:
                raise GitHubAPIError(
                    f"Access denied. Check that your token has required permissions: {error_message}",
                    status_code=403,
                    response=error_json if 'error_json' in locals() else None
                )
        elif e.code == 404:
            raise GitHubAPIError(
                f"Resource not found: {error_message}",
                status_code=404,
                response=error_json if 'error_json' in locals() else None
            )
        elif e.code == 409:
            raise GitHubAPIError(
                f"Conflict: {error_message}. The resource may have been modified concurrently.",
                status_code=409,
                response=error_json if 'error_json' in locals() else None
            )
        elif e.code == 422:
            raise GitHubAPIError(
                f"Validation failed: {error_message}",
                status_code=422,
                response=error_json if 'error_json' in locals() else None
            )
        else:
            raise GitHubAPIError(
                f"GitHub API error ({e.code}): {error_message}",
                status_code=e.code,
                response=error_json if 'error_json' in locals() else None
            )

    except error.URLError as e:
        raise GitHubAPIError(f"Network error: {e.reason}")


def read_file(repo: str, path: str, branch: str = "main") -> str:
    """
    Read a file from GitHub repository.

    Args:
        repo: Repository in format "owner/name"
        path: File path within repository
        branch: Branch name (default: main)

    Returns:
        str: File content

    Raises:
        GitHubAPIError: If file not found or access denied

    Example:
        >>> content = read_file("octocat/Hello-World", "README", "main")
        >>> print(content)
    """
    endpoint = f"/repos/{repo}/contents/{path}"
    params = {"ref": branch}
    endpoint_with_params = f"{endpoint}?{parse.urlencode(params)}"

    response = _make_api_request(endpoint_with_params, method="GET")

    if response.get("type") != "file":
        raise GitHubAPIError(f"'{path}' is not a file (type: {response.get('type')})")

    # GitHub returns content as base64-encoded
    content_b64 = response.get("content", "")
    content = base64.b64decode(content_b64).decode('utf-8')

    return content


def commit_file(
    repo: str,
    path: str,
    content: str,
    branch: str,
    message: str,
    create_branch_from: Optional[str] = None
) -> Dict:
    """
    Commit a single file (create or update).

    Args:
        repo: Repository in format "owner/name"
        path: File path within repository
        content: New file content
        branch: Target branch
        message: Commit message
        create_branch_from: If branch doesn't exist, create from this branch

    Returns:
        Dict with commit_sha, branch, file_path

    Raises:
        GitHubAPIError: On conflicts or auth failures

    Example:
        >>> result = commit_file(
        ...     repo="user/repo",
        ...     path="README.md",
        ...     content="# Hello World",
        ...     branch="main",
        ...     message="Update README"
        ... )
        >>> print(f"Committed: {result['commit_sha']}")
    """
    # Check if branch exists, create if needed
    if create_branch_from:
        _ensure_branch_exists(repo, branch, create_branch_from)

    # Get current file SHA if it exists (needed for updates)
    file_sha = None
    try:
        current_file = _make_api_request(
            f"/repos/{repo}/contents/{path}?ref={branch}",
            method="GET"
        )
        file_sha = current_file.get("sha")
    except GitHubAPIError as e:
        if e.status_code != 404:
            raise  # Re-raise if not a "file not found" error
        # File doesn't exist, will be created

    # Encode content as base64
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    # Commit file
    data = {
        "message": message,
        "content": content_b64,
        "branch": branch
    }

    if file_sha:
        data["sha"] = file_sha  # Required for updates

    response = _make_api_request(
        f"/repos/{repo}/contents/{path}",
        method="PUT",
        data=data
    )

    return {
        "commit_sha": response["commit"]["sha"],
        "branch": branch,
        "file_path": path
    }


def commit_files(
    repo: str,
    files: List[Dict[str, str]],
    branch: str,
    message: str,
    create_branch_from: Optional[str] = None
) -> Dict:
    """
    Commit multiple files in a single commit using Git Trees API.

    Args:
        repo: Repository in format "owner/name"
        files: List of dicts with 'path' and 'content' keys
        branch: Target branch
        message: Commit message
        create_branch_from: If branch doesn't exist, create from this branch

    Returns:
        Dict with commit_sha, branch, files_committed (count)

    Raises:
        GitHubAPIError: On failures

    Example:
        >>> files = [
        ...     {"path": "file1.txt", "content": "Content 1"},
        ...     {"path": "dir/file2.txt", "content": "Content 2"}
        ... ]
        >>> result = commit_files(
        ...     repo="user/repo",
        ...     files=files,
        ...     branch="main",
        ...     message="Add multiple files"
        ... )
        >>> print(f"Committed {result['files_committed']} files")
    """
    # Check if branch exists, create if needed
    if create_branch_from:
        _ensure_branch_exists(repo, branch, create_branch_from)

    # Get current branch reference
    ref_data = _make_api_request(f"/repos/{repo}/git/refs/heads/{branch}")
    base_commit_sha = ref_data["object"]["sha"]

    # Get base tree SHA
    base_commit = _make_api_request(f"/repos/{repo}/git/commits/{base_commit_sha}")
    base_tree_sha = base_commit["tree"]["sha"]

    # Create blobs for each file
    tree_items = []
    for file_info in files:
        # Create blob
        blob_data = {
            "content": file_info["content"],
            "encoding": "utf-8"
        }
        blob_response = _make_api_request(
            f"/repos/{repo}/git/blobs",
            method="POST",
            data=blob_data
        )

        tree_items.append({
            "path": file_info["path"],
            "mode": "100644",  # Regular file
            "type": "blob",
            "sha": blob_response["sha"]
        })

    # Create tree
    tree_data = {
        "base_tree": base_tree_sha,
        "tree": tree_items
    }
    tree_response = _make_api_request(
        f"/repos/{repo}/git/trees",
        method="POST",
        data=tree_data
    )

    # Create commit
    commit_data = {
        "message": message,
        "tree": tree_response["sha"],
        "parents": [base_commit_sha]
    }
    commit_response = _make_api_request(
        f"/repos/{repo}/git/commits",
        method="POST",
        data=commit_data
    )

    # Update branch reference
    _make_api_request(
        f"/repos/{repo}/git/refs/heads/{branch}",
        method="PATCH",
        data={"sha": commit_response["sha"]}
    )

    return {
        "commit_sha": commit_response["sha"],
        "branch": branch,
        "files_committed": len(files)
    }


def create_pull_request(
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str = ""
) -> Dict:
    """
    Create a pull request.

    Args:
        repo: Repository in format "owner/name"
        head: Source branch (where your changes are)
        base: Target branch (where you want to merge)
        title: PR title
        body: PR description (supports markdown)

    Returns:
        Dict with number, html_url, state

    Raises:
        GitHubAPIError: If branches invalid or PR already exists

    Example:
        >>> pr = create_pull_request(
        ...     repo="user/repo",
        ...     head="feature-branch",
        ...     base="main",
        ...     title="Add new feature",
        ...     body="## Changes\\n- Added feature X"
        ... )
        >>> print(f"PR created: {pr['html_url']}")
    """
    data = {
        "title": title,
        "head": head,
        "base": base,
        "body": body
    }

    response = _make_api_request(
        f"/repos/{repo}/pulls",
        method="POST",
        data=data
    )

    return {
        "number": response["number"],
        "html_url": response["html_url"],
        "state": response["state"]
    }


def _ensure_branch_exists(repo: str, branch: str, create_from: str) -> None:
    """
    Ensure a branch exists, creating it if necessary.

    Args:
        repo: Repository in format "owner/name"
        branch: Branch name to ensure exists
        create_from: Branch to create from if it doesn't exist

    Raises:
        GitHubAPIError: On failures
    """
    try:
        # Check if branch exists
        _make_api_request(f"/repos/{repo}/git/refs/heads/{branch}")
        # Branch exists, nothing to do
    except GitHubAPIError as e:
        if e.status_code == 404:
            # Branch doesn't exist, create it
            # Get SHA of source branch
            source_ref = _make_api_request(f"/repos/{repo}/git/refs/heads/{create_from}")
            source_sha = source_ref["object"]["sha"]

            # Create new branch
            _make_api_request(
                f"/repos/{repo}/git/refs",
                method="POST",
                data={
                    "ref": f"refs/heads/{branch}",
                    "sha": source_sha
                }
            )
        else:
            raise  # Re-raise other errors


# Export main functions
__all__ = [
    'GitHubAPIError',
    'get_github_token',
    'read_file',
    'commit_file',
    'commit_files',
    'create_pull_request'
]


if __name__ == "__main__":
    # Self-test
    print("GitHub Client Self-Test")
    print("=" * 50)

    try:
        token = get_github_token()
        masked = f"{token[:7]}...{token[-4:]}" if len(token) > 11 else "***"
        print(f"✓ GitHub token found: {masked}")
        print(f"  Token length: {len(token)} characters")
    except ValueError as e:
        print(f"✗ GitHub token not configured")
        print(f"\n{e}")
