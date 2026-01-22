# getting-env Skill Map

## Structure
```
getting-env/
├── SKILL.md              # Skill documentation
├── _MAP.md               # This file
├── scripts/
│   └── getting_env.py    # Main module
└── assets/
    └── example.env       # Example credential file format
```

## Module: scripts/getting_env.py

### Core Functions
- `get_env(key, default=None, *, required=False, validator=None) -> str | None`
- `load_env(path: str | Path) -> dict[str, str]`
- `load_all(force_reload=False) -> dict[str, str]`

### Environment Detection
- `detect_environment() -> str`
  Returns: "claude.ai", "claude-code-desktop", "claude-code-web", "codex", "jules", "unknown"

### Utilities
- `mask_secret(value, show_chars=4) -> str`
- `debug_info() -> dict`
- `get_loaded_sources() -> list[str]`

### Internal Parsers (not part of public API)
- `_parse_env_file(path)` - .env KEY=value format
- `_parse_single_value_file(path, key_name)` - Single value files
- `_parse_json_settings(path)` - Claude Code settings.json
- `_parse_toml_env(path)` - Codex config.toml

### Source Loaders (not part of public API)
- `_load_os_environ()`
- `_load_claude_ai_project()`
- `_load_claude_code()`
- `_load_codex()`
- `_load_jules()`
- `_load_dotenv_files()`

## Dependencies
- Standard library only (os, json, pathlib, typing, re)
- No external packages required
