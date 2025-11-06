---
name: api-credentials
description: Manages API credentials for external services (Google/Gemini, etc). Use when skills need to authenticate with third-party APIs.
---

# API Credentials Management

When skills need to call external APIs, use this skill to manage credentials securely.

## Supported Providers

- Google (Gemini API, Vertex AI, etc.)
- Extensible for additional providers

## Configuration

Credentials are stored in `/home/claude/config.json`:

```json
{
  "google_api_key": "your-api-key-here",
  "anthropic_api_key": "your-anthropic-key-here"
}
```

**Setup:**

1. User creates `/home/claude/config.json` with their credentials
2. Skills import and use credential functions from `scripts/credentials.py`

**Example config.json:**

See `scripts/config.json.example` for template.

## Usage in Skills

Import the credentials module:

```python
import sys
sys.path.append('/mnt/skills/api-credentials/scripts')
from credentials import get_google_api_key, get_anthropic_api_key

# Get API key
api_key = get_google_api_key()
if not api_key:
    print("Error: Google API key not configured")
    print("Create /home/claude/config.json with 'google_api_key' field")
    sys.exit(1)

# Use the API key
# ... your API calls here ...
```

## Error Handling

Functions return `None` if:
- Config file doesn't exist
- Required field is missing
- Field value is empty

Skills should check for `None` and provide clear user instructions.

## Adding New Providers

To support additional providers:

1. Add field to `config.json.example`
2. Add getter function to `credentials.py`:
   ```python
   def get_provider_api_key():
       return _get_credential('provider_api_key')
   ```
3. Update this documentation

## Security Notes

- Config file stays in `/home/claude/` (ephemeral work directory)
- Never commit actual credentials to git
- Skills should never log or display API keys
- Use environment-specific paths (not hardcoded)

## Token Efficiency

This pattern avoids:
- Repeated credential handling code in every skill
- Long documentation about config files in each skill
- User confusion about where to put credentials

Instead: One central pattern, reusable across all skills.
