"""
Invoking GitHub Skill - GitHub API Client for Claude.ai Chat

Provides programmatic GitHub operations for claude.ai chat environments
where native git access isn't available.
"""

from .github_client import (
    GitHubAPIError,
    get_github_token,
    read_file,
    commit_file,
    commit_files,
    create_pull_request
)

__all__ = [
    'GitHubAPIError',
    'get_github_token',
    'read_file',
    'commit_file',
    'commit_files',
    'create_pull_request'
]

__version__ = "1.0.0"
