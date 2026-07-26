"""
Invoking GitHub Skill - GitHub API Client for Claude.ai Chat

Provides programmatic GitHub operations for claude.ai chat environments
where native git access isn't available.
"""

from .github_client import (
    GitHubAPIError,
    commit_file,
    commit_files,
    create_pull_request,
    get_github_token,
    read_file,
)

__all__ = [
    'GitHubAPIError',
    'commit_file',
    'commit_files',
    'create_pull_request',
    'get_github_token',
    'read_file'
]

__version__ = "1.0.0"
