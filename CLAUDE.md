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

## Skill Development Workflow

When modifying skills in this repository, follow this sequence:

### Before Executing ANY Code

```bash
# 1. Explore the skill directory
ls -la skill-name/

# 2. Check for CLAUDE.md (skill-specific development guide)
if [ -f skill-name/CLAUDE.md ]; then
    echo "⚠️  CLAUDE.md exists - READ THIS FIRST"
    cat skill-name/CLAUDE.md
fi

# 3. Understand the module structure
find skill-name/ -name "*.py" -o -name "*.md"

# 4. Check for symlinks
ls -la .claude/skills/skill-name 2>/dev/null
```

### CLAUDE.md Files Take Priority

If a skill has a `CLAUDE.md` file:
- It contains environment-specific context (Claude Code vs Claude.ai)
- It documents development practices for that specific skill
- It may instruct you to use the skill itself during development (meta-usage)
- **Always read it before writing code**

### Meta-Usage Pattern

Some skills (like `remembering`) should be used to track their own development:

```python
# Example: Use remembering to track work on remembering
from remembering import remember, journal

journal(topics=["muninn-v0.4.0"],
        my_intent="Adding hybrid retrieval with embeddings")

remember("Vector search implementation uses cosine similarity with 0.4 weight",
         "decision", tags=["muninn", "architecture"], conf=0.9)
```

This creates a feedback loop where the skill improves itself while tracking its own improvement.
