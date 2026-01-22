"""
getting-env: Universal environment variable loader for AI agent environments.

Usage:
    from getting_env import get_env, detect_environment
    
    token = get_env("MY_TOKEN", required=True)
    env = detect_environment()  # "claude.ai", "claude-code-desktop", etc.
"""

from .scripts.getting_env import (
    get_env,
    load_env,
    load_all,
    detect_environment,
    mask_secret,
    debug_info,
    get_loaded_sources,
    __version__,
)

__all__ = [
    "get_env",
    "load_env", 
    "load_all",
    "detect_environment",
    "mask_secret",
    "debug_info",
    "get_loaded_sources",
    "__version__",
]
