---
name: api-credentials
description: "Retrieve API credentials for Anthropic, Google, and GitHub from config files or environment variables. Use when skills need stored API keys for external service invocations in local development environments."
metadata:
  version: 0.0.3
---

# API Credentials Management

**Deprecated for hosted environments.** Skills now read credentials directly from project knowledge files (`ANTHROPIC_API_KEY.txt`, `GOOGLE_API_KEY.txt`, `GITHUB_API_KEY.txt` or `API_CREDENTIALS.json`). See [orchestrating-agents](../orchestrating-agents/SKILL.md#setup), [invoking-gemini](../invoking-gemini/SKILL.md#setup), [invoking-github](../invoking-github/SKILL.md#quick-start). This skill remains useful for **local development** or backward compatibility.

**⚠️ Never commit actual credentials — config.json is gitignored.**

## Usage

All providers follow the same pattern — import from `scripts/credentials.py`:

```python
import sys
sys.path.append('/home/user/claude-skills/api-credentials/scripts')
from credentials import get_anthropic_api_key, get_google_api_key, get_github_api_key

api_key = get_anthropic_api_key()  # or get_google_api_key(), get_github_api_key()
# Raises ValueError with setup guidance if not configured
```

## Setup

**Option 1 — Config file** (recommended):
```bash
cp /home/user/claude-skills/api-credentials/assets/config.json.example \
   /home/user/claude-skills/api-credentials/config.json
```
```json
{
  "anthropic_api_key": "sk-ant-api03-...",
  "google_api_key": "AIzaSy...",
  "github_api_key": "ghp_..."
}
```

**Option 2 — Environment variables**:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export GOOGLE_API_KEY="AIzaSy..."
export GITHUB_TOKEN="ghp_..."
```

**Priority**: config.json → environment variable → ValueError.

## Available Functions

| Function | Returns | Notes |
|----------|---------|-------|
| `get_anthropic_api_key()` | `str` | Raises `ValueError` if missing |
| `get_google_api_key()` | `str` | Raises `ValueError` if missing |
| `get_github_api_key()` | `str` | Raises `ValueError` if missing |
| `get_api_key_masked(key)` | `str` | Safe for logging (`sk-ant-...xyz`) |
| `verify_credential(provider)` | `bool` | No exception; providers: `anthropic`, `google`, `github` |

## Security

- Never commit `config.json` with real credentials
- Never log or display full API keys — use `get_api_key_masked()`
- Rotate keys regularly; use environment variables in shared environments
