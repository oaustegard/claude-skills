---
name: api-credentials
description: Securely manages API credentials for Anthropic Claude API. Use when skills need to access stored API keys or when user wants to configure credentials for Claude API invocations.
---

# API Credentials Management

**⚠️ WARNING: This is a PERSONAL skill - DO NOT share or commit with actual credentials!**

This skill provides secure storage and retrieval of API credentials, specifically for the Anthropic Claude API. It serves as a dependency for other skills that need to invoke Claude programmatically.

## Purpose

- Centralized credential storage for API keys
- Secure retrieval methods for dependent skills
- Clear error messages when credentials are missing
- Support for multiple credential sources (config file, environment variables)

## Usage by Other Skills

Skills that need to invoke Claude API should reference this skill:

```python
import sys
sys.path.append('/home/user/claude-skills/api-credentials/scripts')
from credentials import get_anthropic_api_key

try:
    api_key = get_anthropic_api_key()
    # Use api_key for API calls
except ValueError as e:
    print(f"Error: {e}")
```

## Setup Instructions

### Option 1: Configuration File (Recommended)

1. Copy the example config:
```bash
cp /home/user/claude-skills/api-credentials/assets/config.json.example \
   /home/user/claude-skills/api-credentials/config.json
```

2. Edit `config.json` and add your Anthropic API key:
```json
{
  "anthropic_api_key": "sk-ant-api03-..."
}
```

3. Ensure the config file is in `.gitignore` (already configured)

### Option 2: Environment Variable

Set the environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

Add to your shell profile (~/.bashrc, ~/.zshrc) to persist.

## Priority

The credential retrieval follows this priority:
1. `config.json` in the skill directory (highest priority)
2. `ANTHROPIC_API_KEY` environment variable
3. Error if neither is available

## Security Notes

- **Never commit config.json with real credentials**
- The config.json file should be in .gitignore
- Only config.json.example should be version controlled
- Consider using environment variables in shared/production environments
- Rotate API keys regularly

## File Structure

```
api-credentials/
├── SKILL.md              # This file
├── config.json           # YOUR credentials (gitignored)
├── scripts/
│   └── credentials.py    # Credential retrieval module
└── assets/
    └── config.json.example  # Template for users
```

## Error Handling

When credentials are not found, the module provides clear guidance:
- Where to place config.json
- How to set environment variable
- Link to Anthropic Console for key generation

## Token Efficiency

This skill uses ~200 tokens when loaded but saves repeated credential management code across multiple skills that invoke Claude.
