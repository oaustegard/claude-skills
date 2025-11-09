#!/usr/bin/env python3
"""
API Credentials Management Module

Provides secure retrieval of API keys for multiple providers (Anthropic, Google)
from config files or environment variables.
"""

import json
import os
from pathlib import Path


def get_anthropic_api_key() -> str:
    """
    Retrieves the Anthropic API key from available sources.

    Priority order:
    1. config.json in the api-credentials skill directory
    2. ANTHROPIC_API_KEY environment variable

    Returns:
        str: The Anthropic API key

    Raises:
        ValueError: If no API key is found in any source
    """
    # Determine the skill directory (parent of scripts/)
    skill_dir = Path(__file__).parent.parent
    config_path = skill_dir / "config.json"

    # Try config.json first
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('anthropic_api_key', '').strip()
                if api_key:
                    return api_key
        except (json.JSONDecodeError, IOError) as e:
            # If config exists but is malformed, we should know about it
            raise ValueError(
                f"Error reading config.json: {e}\n"
                f"Please check the file at: {config_path}"
            )

    # Try environment variable
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if api_key:
        return api_key

    # No key found - provide helpful error message
    raise ValueError(
        "No Anthropic API key found!\n\n"
        "Please configure your API key using one of these methods:\n\n"
        "Option 1: Create config.json\n"
        f"  1. Copy: cp {skill_dir}/assets/config.json.example {skill_dir}/config.json\n"
        f"  2. Edit {skill_dir}/config.json and add your API key\n\n"
        "Option 2: Set environment variable\n"
        "  export ANTHROPIC_API_KEY='sk-ant-api03-...'\n\n"
        "Get your API key from: https://console.anthropic.com/settings/keys"
    )


def get_google_api_key() -> str:
    """
    Retrieves the Google API key for Gemini and other Google services.

    Priority order:
    1. config.json in the api-credentials skill directory
    2. GOOGLE_API_KEY environment variable

    Returns:
        str: The Google API key

    Raises:
        ValueError: If no API key is found in any source
    """
    # Determine the skill directory (parent of scripts/)
    skill_dir = Path(__file__).parent.parent
    config_path = skill_dir / "config.json"

    # Try config.json first
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('google_api_key', '').strip()
                if api_key:
                    return api_key
        except (json.JSONDecodeError, IOError) as e:
            # If config exists but is malformed, we should know about it
            raise ValueError(
                f"Error reading config.json: {e}\n"
                f"Please check the file at: {config_path}"
            )

    # Try environment variable
    api_key = os.environ.get('GOOGLE_API_KEY', '').strip()
    if api_key:
        return api_key

    # No key found - provide helpful error message
    raise ValueError(
        "No Google API key found!\n\n"
        "Please configure your API key using one of these methods:\n\n"
        "Option 1: Create config.json\n"
        f"  1. Copy: cp {skill_dir}/assets/config.json.example {skill_dir}/config.json\n"
        f"  2. Edit {skill_dir}/config.json and add your API key\n\n"
        "Option 2: Set environment variable\n"
        "  export GOOGLE_API_KEY='AIzaSy...'\n\n"
        "Get your API key from: https://console.cloud.google.com/apis/credentials"
    )


def get_api_key_masked(api_key: str) -> str:
    """
    Returns a masked version of an API key for logging/display purposes.

    Args:
        api_key: The API key to mask

    Returns:
        str: Masked API key (e.g., "sk-ant-...xyz" or "AIzaSy...xyz")
    """
    if len(api_key) > 16:
        return f"{api_key[:10]}...{api_key[-4:]}"
    return "***"


def get_github_api_key() -> str:
    """
    Retrieves the GitHub API token (Personal Access Token).

    Priority order:
    1. config.json in the api-credentials skill directory
    2. GITHUB_TOKEN environment variable
    3. GITHUB_API_KEY environment variable

    Returns:
        str: The GitHub API token

    Raises:
        ValueError: If no API key is found in any source
    """
    # Determine the skill directory (parent of scripts/)
    skill_dir = Path(__file__).parent.parent
    config_path = skill_dir / "config.json"

    # Try config.json first
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('github_api_key', '').strip()
                if api_key:
                    return api_key
        except (json.JSONDecodeError, IOError) as e:
            # If config exists but is malformed, we should know about it
            raise ValueError(
                f"Error reading config.json: {e}\n"
                f"Please check the file at: {config_path}"
            )

    # Try environment variables (GitHub Actions uses GITHUB_TOKEN)
    api_key = os.environ.get('GITHUB_TOKEN', '').strip()
    if api_key:
        return api_key

    api_key = os.environ.get('GITHUB_API_KEY', '').strip()
    if api_key:
        return api_key

    # No key found - provide helpful error message
    raise ValueError(
        "No GitHub API token found!\n\n"
        "Please configure your API token using one of these methods:\n\n"
        "Option 1: Create config.json\n"
        f"  1. Copy: cp {skill_dir}/assets/config.json.example {skill_dir}/config.json\n"
        f"  2. Edit {skill_dir}/config.json and add your GitHub token\n\n"
        "Option 2: Set environment variable\n"
        "  export GITHUB_TOKEN='ghp_...'\n\n"
        "Get your token from: https://github.com/settings/tokens\n"
        "Required scopes: repo (for private repos) or public_repo (for public repos only)"
    )


def verify_credential(provider: str) -> bool:
    """
    Verify that a credential is configured for a provider.

    Args:
        provider: Provider name ('google', 'anthropic', or 'github')

    Returns:
        True if credential exists and is non-empty, False otherwise
    """
    credential_map = {
        'google': get_google_api_key,
        'anthropic': get_anthropic_api_key,
        'github': get_github_api_key,
    }

    getter = credential_map.get(provider.lower())
    if not getter:
        return False

    try:
        key = getter()
        return bool(key)
    except ValueError:
        return False


if __name__ == "__main__":
    # Self-test for all providers
    print("API Credentials Self-Test")
    print("=" * 50)

    providers = {
        'anthropic': get_anthropic_api_key,
        'google': get_google_api_key,
        'github': get_github_api_key
    }

    for provider_name, getter_func in providers.items():
        try:
            key = getter_func()
            masked = get_api_key_masked(key)
            print(f"✓ {provider_name.capitalize()} API key found: {masked}")
            print(f"  Key length: {len(key)} characters")
        except ValueError as e:
            print(f"✗ {provider_name.capitalize()} API key not configured")
            # Don't print full error in summary
        print()

    print("=" * 50)
    print("Configuration status:")
    for provider in ['anthropic', 'google', 'github']:
        configured = verify_credential(provider)
        status = "✓ Configured" if configured else "✗ Not configured"
        print(f"  {provider.capitalize()}: {status}")
