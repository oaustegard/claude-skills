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

## Code Maps

This repository has navigable code maps generated via the mapping-codebases skill.

### Using the Maps

**When exploring this codebase, ALWAYS start with `_MAP.md` files** rather than directly reading source files:

1. **Start at the root** - Read `/home/user/claude-skills/_MAP.md` for a high-level overview
2. **Navigate hierarchically** - Each directory has its own `_MAP.md` with:
   - Subdirectory links for drilling down
   - File-level symbol exports (classes, functions, methods)
   - Import previews showing dependencies
   - Function signatures (Python, partial TypeScript)
3. **Read source files only when necessary** - After identifying relevant files via maps

**Why this matters**: This repository has 36 skills with scripts, references, and supporting files. Maps provide structure without overwhelming context windows.

### Keeping Maps Fresh

**CRITICAL - Before ANY git commit:**

```bash
# Refresh all _MAP.md files to reflect code changes
python /home/user/claude-skills/mapping-codebases/scripts/codemap.py /home/user/claude-skills --skip uploads,assets

# Then stage and commit
git add .
git commit -m "your commit message"
```

**Why**: _MAP.md files are generated from AST analysis and drift from source code as files change. Outdated maps mislead future Claude instances and developers.

**Integration with commit workflow:**
- Run mapping BEFORE staging files
- Include updated _MAP.md files in your commit
- This ensures maps always reflect the committed code state

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

### CRITICAL: Skills Have Multiple Documentation Files

**SKILL.md is the source of truth** - it's what users see and what triggers releases.

When updating a skill, you MUST update ALL relevant files:
- `SKILL.md` - User-facing documentation, version in frontmatter, installation instructions
- `README.md` - Auto-generated but may exist in development
- Implementation files (scripts/*.py, etc.)
- Any other documentation

**Common FAILURE pattern:**
```bash
# Update implementation
Edit codemap.py (✓)

# Update README.md
Edit README.md (✓)

# Forget SKILL.md (✗ CRITICAL FAILURE)
# - Users get outdated installation instructions
# - Version not bumped → no release triggered
# - Frontmatter description outdated
```

**CORRECT workflow:**
```bash
# 1. Update implementation files
Edit scripts/codemap.py

# 2. Update README.md (if exists)
Edit README.md

# 3. Update SKILL.md (REQUIRED)
Edit SKILL.md:
  - Bump version in frontmatter
  - Update installation instructions
  - Update examples to match new features
  - Update limitations section

# 4. Verify all files consistent
grep -n "tree-sitter" skill-name/*.md skill-name/scripts/*.py
# All should show updated package names
```

**Version bumping triggers releases:**
- Change `metadata.version` in SKILL.md frontmatter
- Semantic versioning: major.minor.patch
- New features = minor bump (0.2.0 → 0.3.0)
- Bug fixes = patch bump (0.2.0 → 0.2.1)
- Breaking changes = major bump (0.2.0 → 1.0.0)

### Skill Naming and Metadata Guidelines

**CRITICAL Requirements:**

1. **Always use `metadata.version` in the frontmatter** - Not just `version`, but specifically `metadata.version` field
2. **Never name a skill with "Claude" in it** - Skill names must not contain "Claude" (e.g., avoid "claude-helper", "invoking-claude")
3. **Always use gerund form as the first word** - Skill names must start with a gerund (verb+ing form):
   - ✅ CORRECT: `creating-mcp-servers`, `processing-pdfs`, `updating-knowledge`
   - ❌ WRONG: `mcp-creator`, `pdf-processor`, `knowledge-update`

These are non-negotiable requirements for all skills in this repository.

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

## PR Reviews and Code Testing

When asked to review a PR, follow this rigorous testing workflow:

### Pre-Flight: Verify Branch Setup

**CRITICAL**: Distinguish between the PR branch (source) and your development branch (target).

```bash
# 1. FIRST: Check what development branch you should use
# (Usually specified in task instructions as claude/review-pr-XXX-<session-id>)

# 2. Create or checkout your development branch
git checkout -b claude/review-pr-XXX-<session-id>

# 3. Fetch the PR branch for reading/testing
git fetch origin pull/XXX/head:pr-XXX-review

# 4. Verify you're on YOUR branch, not the PR branch
git branch --show-current  # Should show claude/review-pr-XXX-<session-id>
```

**Never** checkout the PR branch directly and start making changes. Always work on your designated development branch.

### Testing Workflow: NO STATIC REVIEWS

**RULE**: Never write a code review without running the code. Static analysis misses critical issues.

**CRITICAL**: If you encounter an error while attempting to run code:
1. **DO NOT give up** - Try to fix it (install dependencies, check paths, etc.)
2. **DO NOT proceed with static review** - Keep trying alternatives
3. **DO report failures to the user** - "I tried to test but hit X error, attempted Y and Z solutions, still blocked. How should I proceed?"
4. **NEVER NEVER NEVER** silently fail to test and not tell the user you didn't test

Example of **INEXCUSABLE** behavior:
```bash
$ python3 script.py --help
ModuleNotFoundError: No module named 'foo'

# Then proceeding with static review without:
# - Trying to install 'foo'
# - Telling the user you couldn't run tests
# - Asking for help
```

Example of **CORRECT** behavior:
```bash
$ python3 script.py --help
ModuleNotFoundError: No module named 'foo'

# Immediately try to fix:
$ uv pip install --system foo
# Or: pip install foo
# Or: check if already installed but wrong name

# If all attempts fail, REPORT:
"I attempted to test the code but encountered ModuleNotFoundError.
I tried:
- uv pip install --system foo (failed: X)
- pip install foo (failed: Y)
- searching for alternative package names (found Z)
Should I proceed differently or do you want to provide the dependency?"
```

**Required steps:**

1. **Research dependencies first**
   ```bash
   # Check if packages are maintained
   # Find latest versions
   # Identify breaking changes
   ```

2. **Install dependencies**
   ```bash
   # Use uv (preferred) or pip
   uv pip install --system <packages>

   # Verify installation
   python3 -c "import package_name; print(package_name.__version__)"
   ```

3. **Run the code with test inputs**
   ```bash
   # Don't just check --help
   # Create test files and run actual operations

   # Example for codemap.py:
   mkdir -p /tmp/test
   cat > /tmp/test/sample.py << 'EOF'
   class TestClass:
       def method(self): pass
   EOF
   python3 script.py --dry-run /tmp/test
   ```

4. **Test multiple scenarios**
   - Happy path (normal inputs)
   - Edge cases (empty files, malformed code)
   - Multiple languages/formats if applicable
   - Error conditions

5. **Document actual behavior**
   - Include input/output examples from real runs
   - Note what works vs what doesn't
   - Compare expected vs actual behavior

### Review Document Format

**Do**:
- Include "Testing Results" section with actual outputs
- Show concrete examples: Input → Output
- Mark issues with severity: 🔴 Critical, 🟡 Important, 🟢 Nice-to-have
- Provide fix recommendations with code snippets

**Don't**:
- Write purely theoretical reviews
- Guess at behavior without testing
- Create multiple review documents (iterate on one)
- Assume code works because it "looks right"

### Dependency Updates

When finding unmaintained or outdated dependencies:

1. **Research alternatives**
   - Check if package is maintained
   - Find recommended replacements
   - Verify compatibility

2. **Update proactively**
   - Don't wait for user to ask
   - Update import statements
   - Update documentation (README, requirements)
   - Test that updates work

3. **Use modern tooling**
   - Prefer `uv` over `pip` for this project
   - Note Python version requirements
   - Document why changes were made

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

### Handoff Execution Expectations

**When the user gives you a handoff, execute it immediately.** Handoffs are actionable work items that should be completed, not deferred or questioned. If a handoff seems irrelevant to the current environment (e.g., Claude.ai-specific features while in Claude Code), remember that this repository serves multiple Claude environments and the handoff may be relevant for other contexts.
