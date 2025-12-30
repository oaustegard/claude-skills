@AGENTS.md

## Claude Code on the Web Development

This repository is frequently developed via Claude Code on the web. Key workflow considerations:

### Branch and PR Lifecycle

When making follow-up changes within a session after a PR has been created:

1. **Check PR status first** - The user may have already merged and deleted the working branch
2. **Fetch latest from main** - `git fetch origin main` to see current state
3. **Create a new branch if needed** - If the previous branch was deleted, create a fresh branch from main
4. **Don't assume your branch still exists** - PRs are often merged quickly in this workflow

```bash
# Before making secondary changes, always check:
git fetch origin main
git log --oneline origin/main -3  # See if your PR was merged

# If branch was deleted, start fresh:
git checkout main
git pull origin main
git checkout -b claude/new-feature-<session-id>
```

### Why This Matters

- Claude Code web sessions can span user interactions where PRs get merged between messages
- The user may merge and delete branches without explicitly telling Claude
- Attempting to push to a deleted branch will fail with 403 errors
- Always verify branch state before assuming continuity

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

## Remembering Skill and Handoff Process

**CRITICAL**: When working with the `remembering` skill OR discussing handoffs, ALWAYS read `/home/user/claude-skills/remembering/CLAUDE.md` FIRST.

Why:
- The remembering skill's CLAUDE.md contains comprehensive documentation about handoff workflows
- Handoffs are stored IN the remembering system as memories
- Querying handoffs requires using the remembering skill itself
- The remembering/CLAUDE.md has critical context about how to query and complete handoffs

**Do this immediately** when:
- User mentions "remembering" skill
- User asks about handoffs
- User asks to check handoff status
- User references Muninn (the memory system)

```bash
# ALWAYS do this first:
cat /home/user/claude-skills/remembering/CLAUDE.md
```

Then use the remembering skill to query handoffs:
```python
import sys
sys.path.insert(0, '/home/user/claude-skills')
from remembering import recall, handoff_pending

# Check for handoffs - multiple approaches:
# 1. Formal pending handoffs (tagged "handoff" + "pending")
pending = handoff_pending()

# 2. All handoff-related memories (broader search)
all_handoffs = recall(tags=["handoff"], n=50)

# 3. Specific handoff topics
topic_handoffs = recall(tags=["handoff", "openai"], n=10)
```
