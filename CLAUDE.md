@AGENTS.md

## Environment-Specific Tips

### Environment Variable Access

**TL;DR: Use Python's `os.environ` for environment variables, not bash variable expansion.**

When you need to access environment variables (API keys, tokens, etc.):

**Don't**: Struggle with bash variable expansion issues
```bash
# These can fail in subtle ways
echo $MY_VAR
curl -H "Authorization: Bearer $MY_VAR"
```

**Do**: Use Python's `os.environ.get()` directly
```python
import os
api_key = os.environ.get('MY_VAR', '')
# Now you have the value reliably
```

**Why**: Bash variable expansion can behave unpredictably in different contexts (subshells, heredocs, quotes, etc.). Python's environment variable access is consistent and reliable. If bash isn't working after 1-2 attempts, switch to Python immediately rather than trying multiple shell workarounds.
