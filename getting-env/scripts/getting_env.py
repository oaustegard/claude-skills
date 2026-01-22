#!/usr/bin/env python3
"""
Universal Environment Variable Loader for AI Agent Environments

Loads environment variables and secrets from any supported AI coding environment:
- Claude.ai Projects (project knowledge files)
- Claude Code (desktop & web)
- OpenAI Codex
- Jules (Google)
- Standard environments (.env files, shell env vars)

Usage:
    from getting_env import get_env, load_env, detect_environment
    
    # Get a single variable (searches all sources)
    api_key = get_env("MY_API_KEY")
    
    # With default
    api_key = get_env("MY_API_KEY", default="")
    
    # Detect current environment
    env_type = detect_environment()  # "claude.ai", "claude-code", "codex", "jules", "unknown"
    
    # Bulk load from a specific file
    vars = load_env("/path/to/.env")
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

__version__ = "1.0.0"

# Module-level cache
_cache: Dict[str, str] = {}
_loaded_sources: List[str] = []


# =============================================================================
# Environment Detection
# =============================================================================

def detect_environment() -> str:
    """
    Detect which AI agent environment we're running in.
    
    Returns:
        One of: "claude.ai", "claude-code-desktop", "claude-code-web", 
                "codex", "jules", "unknown"
    """
    # Claude.ai Projects: /mnt/project exists and is populated
    if Path("/mnt/project").is_dir():
        # Claude.ai web chat has /mnt/skills and /mnt/user-data
        if Path("/mnt/skills").exists() and Path("/mnt/user-data").exists():
            return "claude.ai"
    
    # Claude Code: ~/.claude directory exists with settings
    claude_home = Path.home() / ".claude"
    if claude_home.is_dir():
        if (claude_home / "settings.json").exists():
            return "claude-code-desktop"
    
    # OpenAI Codex: ~/.codex directory or CODEX_HOME env var
    codex_home = os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    if Path(codex_home).is_dir():
        return "codex"
    
    # Jules: /home/jules is the standard user
    if Path("/home/jules").exists() or os.environ.get("JULES_SESSION_ID"):
        return "jules"
    
    # Claude Code on web may not have ~/.claude but has container markers
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE"):
        return "claude-code-web"
    
    return "unknown"


# =============================================================================
# File Parsing Utilities
# =============================================================================

def _parse_env_file(path: Path) -> Dict[str, str]:
    """
    Parse a .env file into a dict.
    
    Handles:
    - KEY=value
    - KEY="value with spaces"
    - KEY='value with spaces'
    - export KEY=value
    - # comments
    - Empty lines
    
    Args:
        path: Path to .env file
        
    Returns:
        Dict of key-value pairs
    """
    env = {}
    if not path.exists():
        return env
    
    for line in path.read_text().splitlines():
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        
        # Handle 'export KEY=value' format
        if line.startswith('export '):
            line = line[7:]
        
        # Must have an equals sign
        if '=' not in line:
            continue
        
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        
        # Remove surrounding quotes
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        
        env[key] = value
    
    return env


def _parse_single_value_file(path: Path, key_name: str) -> Dict[str, str]:
    """
    Parse a single-value file (like turso-token.txt) into a dict.
    
    Handles:
    - Plain value
    - KEY=value format (extracts just the value)
    
    Args:
        path: Path to the file
        key_name: Key name to use if file contains just a value
        
    Returns:
        Dict with the key-value pair
    """
    if not path.exists():
        return {}
    
    content = path.read_text().strip()
    
    # Check if it's already in KEY=value format
    if '=' in content and '\n' not in content:
        key, _, value = content.partition('=')
        return {key.strip(): value.strip()}
    
    # Plain value
    return {key_name: content}


def _parse_json_settings(path: Path) -> Dict[str, str]:
    """
    Parse env vars from a Claude Code settings.json file.
    
    Looks for the "env" block:
    {
        "env": {
            "MY_VAR": "value"
        }
    }
    
    Args:
        path: Path to settings.json
        
    Returns:
        Dict of env vars from the "env" block
    """
    if not path.exists():
        return {}
    
    try:
        data = json.loads(path.read_text())
        return data.get("env", {})
    except (json.JSONDecodeError, IOError):
        return {}


def _parse_toml_env(path: Path) -> Dict[str, str]:
    """
    Parse environment variables from a Codex config.toml file.
    
    Looks for shell_environment_policy.set block.
    Basic TOML parsing - doesn't handle all TOML features.
    
    Args:
        path: Path to config.toml
        
    Returns:
        Dict of env vars
    """
    if not path.exists():
        return {}
    
    env = {}
    try:
        content = path.read_text()
        # Simple parsing for common patterns
        # Look for set = { KEY = "value", ... }
        import re
        
        # Find shell_environment_policy.set or [shell_environment_policy] set = 
        match = re.search(r'set\s*=\s*\{([^}]+)\}', content)
        if match:
            pairs = match.group(1)
            for pair_match in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', pairs):
                env[pair_match.group(1)] = pair_match.group(2)
    except IOError:
        pass
    
    return env


# =============================================================================
# Source Loading Functions
# =============================================================================

def _load_os_environ() -> Dict[str, str]:
    """Load all environment variables from os.environ."""
    return dict(os.environ)


def _load_claude_ai_project() -> Dict[str, str]:
    """
    Load environment variables from Claude.ai project knowledge.
    
    Searches /mnt/project for:
    - *.env files (KEY=value format)
    - *-token.txt, *-key.txt, *-secret.txt files (single value)
    """
    env = {}
    project_dir = Path("/mnt/project")
    
    if not project_dir.is_dir():
        return env
    
    # Load all .env files
    for env_file in project_dir.glob("*.env"):
        env.update(_parse_env_file(env_file))
    
    # Load single-value credential files
    patterns = ["*-token.txt", "*-key.txt", "*-secret.txt", "*_TOKEN.txt", "*_KEY.txt"]
    for pattern in patterns:
        for cred_file in project_dir.glob(pattern):
            # Derive key name from filename
            # e.g., "turso-token.txt" -> "TURSO_TOKEN"
            stem = cred_file.stem.upper().replace("-", "_")
            env.update(_parse_single_value_file(cred_file, stem))
    
    return env


def _load_claude_code() -> Dict[str, str]:
    """
    Load environment variables from Claude Code settings.
    
    Searches:
    - ~/.claude/settings.json (user settings)
    - ~/.claude/settings.local.json (user local settings)  
    - .claude/settings.json (project settings)
    - .claude/settings.local.json (project local settings)
    """
    env = {}
    
    # User settings (lower priority)
    user_claude = Path.home() / ".claude"
    for filename in ["settings.json", "settings.local.json"]:
        env.update(_parse_json_settings(user_claude / filename))
    
    # Project settings (higher priority)
    project_claude = Path.cwd() / ".claude"
    for filename in ["settings.json", "settings.local.json"]:
        env.update(_parse_json_settings(project_claude / filename))
    
    return env


def _load_codex() -> Dict[str, str]:
    """
    Load environment variables from OpenAI Codex configuration.
    
    Searches:
    - $CODEX_HOME/config.toml or ~/.codex/config.toml
    - .codex/config.toml (project)
    """
    env = {}
    
    # User config
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    env.update(_parse_toml_env(codex_home / "config.toml"))
    
    # Project config (higher priority)
    env.update(_parse_toml_env(Path.cwd() / ".codex" / "config.toml"))
    
    return env


def _load_jules() -> Dict[str, str]:
    """
    Load environment variables for Jules environment.
    
    Jules primarily uses:
    - Standard environment variables set in Jules config UI
    - .env files in repo root
    """
    env = {}
    
    # Jules mostly relies on env vars set via UI, but check .env in common locations
    for path in [Path.cwd() / ".env", Path.home() / ".env"]:
        env.update(_parse_env_file(path))
    
    return env


def _load_dotenv_files() -> Dict[str, str]:
    """
    Load environment variables from standard .env file locations.
    
    Searches (in order, later overrides earlier):
    - ~/.env
    - ./.env
    - ./.env.local
    """
    env = {}
    
    paths = [
        Path.home() / ".env",
        Path.cwd() / ".env",
        Path.cwd() / ".env.local",
    ]
    
    for path in paths:
        env.update(_parse_env_file(path))
    
    return env


# =============================================================================
# Main API
# =============================================================================

def load_all(force_reload: bool = False) -> Dict[str, str]:
    """
    Load environment variables from all detected sources.
    
    Sources are loaded in priority order (later sources override earlier):
    1. OS environment variables (lowest - can be overridden)
    2. Platform-specific sources (Claude.ai, Claude Code, Codex, Jules)
    3. Standard .env files
    4. OS environment variables again (highest - explicit env vars win)
    
    Results are cached. Use force_reload=True to refresh.
    
    Args:
        force_reload: If True, clear cache and reload from all sources
        
    Returns:
        Dict of all loaded environment variables
    """
    global _cache, _loaded_sources
    
    if _cache and not force_reload:
        return _cache.copy()
    
    _cache.clear()
    _loaded_sources.clear()
    
    env_type = detect_environment()
    
    # Base: OS environment (can be overridden by file configs)
    _cache.update(_load_os_environ())
    _loaded_sources.append("os.environ")
    
    # Platform-specific sources
    if env_type == "claude.ai":
        _cache.update(_load_claude_ai_project())
        _loaded_sources.append("claude.ai:/mnt/project/")
    
    if env_type in ("claude-code-desktop", "claude-code-web"):
        _cache.update(_load_claude_code())
        _loaded_sources.append("claude-code:~/.claude/ + .claude/")
    
    if env_type == "codex":
        _cache.update(_load_codex())
        _loaded_sources.append("codex:~/.codex/config.toml")
    
    if env_type == "jules":
        _cache.update(_load_jules())
        _loaded_sources.append("jules:.env")
    
    # Standard .env files (can override platform sources)
    dotenv_vars = _load_dotenv_files()
    if dotenv_vars:
        _cache.update(dotenv_vars)
        _loaded_sources.append("dotenv:.env files")
    
    # OS environ again - explicit env vars should win over all file sources
    # This ensures `export VAR=x && python ...` works as expected
    _cache.update(_load_os_environ())
    
    return _cache.copy()


def get_env(
    key: str,
    default: Optional[str] = None,
    *,
    required: bool = False,
    validator: Optional[Callable[[str], bool]] = None,
) -> Optional[str]:
    """
    Get an environment variable from any available source.
    
    Searches all sources (cached after first load):
    1. OS environment variables
    2. Platform-specific sources (Claude.ai project, Claude Code settings, etc.)
    3. Standard .env files
    
    Args:
        key: Environment variable name
        default: Default value if not found
        required: If True, raise ValueError when not found
        validator: Optional function to validate the value
        
    Returns:
        The value, or default if not found
        
    Raises:
        ValueError: If required=True and key not found, or if validator fails
    
    Example:
        api_key = get_env("TURSO_TOKEN", required=True)
        port = get_env("PORT", default="8080")
    """
    env = load_all()
    value = env.get(key)
    
    if value is None:
        if required:
            env_type = detect_environment()
            raise ValueError(_get_missing_key_message(key, env_type))
        return default
    
    if validator and not validator(value):
        raise ValueError(f"Environment variable {key} failed validation")
    
    return value


def load_env(path: str | Path) -> Dict[str, str]:
    """
    Load environment variables from a specific file.
    
    Automatically detects file format:
    - .env, .local, no extension: KEY=value format
    - .json: JSON with "env" block
    - .toml: TOML with shell_environment_policy.set
    - .txt: Single value file
    
    Args:
        path: Path to the environment file
        
    Returns:
        Dict of loaded variables (also merged into cache)
    """
    global _cache
    
    path = Path(path)
    
    if path.suffix in ('.json',):
        loaded = _parse_json_settings(path)
    elif path.suffix in ('.toml',):
        loaded = _parse_toml_env(path)
    elif path.suffix in ('.txt',):
        key_name = path.stem.upper().replace("-", "_")
        loaded = _parse_single_value_file(path, key_name)
    else:
        loaded = _parse_env_file(path)
    
    _cache.update(loaded)
    return loaded


def mask_secret(value: str, show_chars: int = 4) -> str:
    """
    Mask a secret value for safe logging/display.
    
    Args:
        value: The secret value
        show_chars: Number of characters to show at start and end
        
    Returns:
        Masked value like "sk-a...xyz"
    
    Example:
        >>> mask_secret("sk-ant-api03-abcdef123456")
        'sk-a...3456'
    """
    if len(value) <= show_chars * 2:
        return "***"
    return f"{value[:show_chars]}...{value[-show_chars:]}"


def get_loaded_sources() -> List[str]:
    """Return list of sources that were loaded."""
    return _loaded_sources.copy()


def debug_info() -> Dict[str, Any]:
    """
    Get debug information about the current environment.
    
    Returns:
        Dict with environment type, loaded sources, and masked key previews
    """
    env = load_all()
    
    # Only show keys that look like credentials
    credential_patterns = ['KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'CREDENTIAL', 'AUTH']
    masked_creds = {}
    
    for key, value in env.items():
        if any(pattern in key.upper() for pattern in credential_patterns):
            masked_creds[key] = mask_secret(value)
    
    return {
        "environment": detect_environment(),
        "sources": get_loaded_sources(),
        "credential_keys": list(masked_creds.keys()),
        "credentials_masked": masked_creds,
    }


# =============================================================================
# Error Messages
# =============================================================================

def _get_missing_key_message(key: str, env_type: str) -> str:
    """Generate a helpful error message for a missing environment variable."""
    
    base_msg = f"Required environment variable '{key}' not found."
    
    hints = {
        "claude.ai": f"""
{base_msg}

In Claude.ai Projects, set this by:
1. Go to Project Settings > Knowledge
2. Upload a file named '{key.lower()}.txt' containing just the value, OR
3. Upload a '{key.lower()}.env' file with {key}=your_value_here
""",
        "claude-code-desktop": f"""
{base_msg}

In Claude Code, set this by:
1. Add to ~/.claude/settings.json:
   {{"env": {{"{key}": "your_value_here"}}}}
   
2. Or set as environment variable:
   export {key}="your_value_here"
""",
        "claude-code-web": f"""
{base_msg}

Set as environment variable:
   export {key}="your_value_here"
""",
        "codex": f"""
{base_msg}

In OpenAI Codex, set this by:
1. Add to setup script (writes to ~/.bashrc):
   echo 'export {key}="your_value_here"' >> ~/.bashrc

2. Or in ~/.codex/config.toml:
   [shell_environment_policy]
   set = {{ {key} = "your_value_here" }}
   
Note: Secrets are only available during setup phase, not agent phase.
""",
        "jules": f"""
{base_msg}

In Jules (Google), set this by:
1. Go to Environment Settings in your Jules project
2. Add {key} as an environment variable or secret
   
Alternatively, add to .env file in your repo root:
   {key}=your_value_here
""",
        "unknown": f"""
{base_msg}

Set as environment variable:
   export {key}="your_value_here"
   
Or add to .env file in working directory:
   {key}=your_value_here
"""
    }
    
    return hints.get(env_type, hints["unknown"])


# =============================================================================
# CLI Interface
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Get specific key
        key = sys.argv[1]
        value = get_env(key)
        if value:
            print(value)
        else:
            print(f"Not found: {key}", file=sys.stderr)
            sys.exit(1)
    else:
        # Print debug info
        info = debug_info()
        print(f"Environment: {info['environment']}")
        print(f"Sources: {', '.join(info['sources'])}")
        print(f"Credential keys found: {', '.join(info['credential_keys']) or 'none'}")
        if info['credentials_masked']:
            print("\nMasked values:")
            for k, v in info['credentials_masked'].items():
                print(f"  {k}: {v}")
