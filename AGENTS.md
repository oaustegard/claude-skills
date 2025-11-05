# AGENTS.md

This file provides guidance to LLM Agents when working with code in this repository.

## Repository Overview

This is a collection of Claude Skills - custom extensions that enhance Claude's capabilities through structured prompt engineering. Each skill is packaged as a directory containing a SKILL.md file with frontmatter metadata and optional supporting resources (scripts, references, assets).

**Important Context**: This repository is deprecated and read-only. Skills shown here demonstrate patterns but may reference environments/features that differ from the current Claude Code CLI environment you're running in. When working on skills, verify current environment capabilities rather than assuming the patterns shown here still apply.

## Repository Structure

```
claude-skills/
├── skill-name/              # Each directory = one skill
│   ├── SKILL.md            # Required: frontmatter + instructions to Claude
│   ├── scripts/            # Optional: executable code for deterministic operations
│   ├── references/         # Optional: detailed docs loaded on demand
│   └── assets/             # Optional: templates, files used in output
├── uploads/                # Drop zone for .zip files (triggers automation)
├── creating-skill/         # Meta-skill: instructions for creating skills
└── .github/workflows/      # Automation for skill uploads
    └── skill-upload.yml
```

### Key Principles

1. **SKILL.md as interface**: Each skill's SKILL.md contains YAML frontmatter (`name`, `description`) followed by imperative instructions written TO Claude, not documentation ABOUT Claude
2. **Progressive disclosure**: Keep SKILL.md concise (~500 lines max), move detailed content to references/
3. **Naming convention**: Use gerund form (e.g., `creating-mcp-servers`, `processing-pdfs`)
4. **Token efficiency**: Every line should justify its context window cost

## Working with Skills

### Creating a New Skill

**Note**: The init_skill.sh script shown below expects to run in a specific skill development environment (references `/home/claude/`, `/mnt/user-data/outputs/`, etc.) which differs from this repository checkout.

The conceptual workflow when creating skills:

1. Initialize structure:
   ```bash
   creating-skill/scripts/init_skill.sh --name skill-name
   ```

2. Edit SKILL.md with required frontmatter:
   ```yaml
   ---
   name: skill-name
   description: What it does. Use when [trigger patterns].
   ---
   ```

3. Add supporting resources to scripts/, references/, or assets/ as needed

4. Delete unused directories

5. Package as ZIP:
   ```bash
   cd /home/claude
   zip -r skill-name.zip skill-name/ -x "*.git*"
   ```

### Uploading Skills (Automated Workflow)

When a .zip file is pushed to `uploads/`:

1. GitHub Actions workflow `skill-upload.yml` is triggered
2. Validates skill structure (must contain SKILL.md at root)
3. Runs security checks (path traversal, blocked file types, zip bomb)
4. Extracts to root directory as `skill-name/`
5. Creates PR with changes
6. Deletes original .zip from uploads/

**Security validations**:
- Path traversal detection
- Blocks executables/binaries (.exe, .dll, .so, .jar, nested archives)
- Max 1000 files per skill
- Scripts (.sh, .py, .js) are allowed as reviewable text

### Skill Frontmatter Requirements

**name**:
- Lowercase letters, numbers, hyphens only
- Max 64 characters
- No reserved words (anthropic, claude)

**description**:
- Max 1024 characters
- Third person voice ("Processes files" not "I process files")
- Include WHAT it does and WHEN to use it (trigger patterns)
- No XML tags

## Key Skills in This Repository

### Meta-Skills (Skills for Creating Skills)

- **creating-skill**: Comprehensive guide for skill creation workflow, structure, and patterns. Start here when building new skills.
- **versioning-skills**: Git-based workflow for tracking changes during skill development
- **asking-questions**: When and how to ask clarifying questions during implementation

### Domain-Specific Skills

- **creating-mcp-servers**: Build production-ready MCP servers using FastMCP v2 with progressive disclosure patterns
- **creating-bookmarklets**: Create browser bookmarklets
- **developing-preact**: Preact development patterns and guidance
- **updating-knowledge**: Patterns for updating Claude's knowledge through context
- **hello-demo**: Simple skill demonstrating asset delivery pattern
- **check-tools**: Tool checking utilities
- **convening-experts**: Pattern for multi-expert collaboration

## Important Implementation Patterns

### 1. Progressive Disclosure

For skills with extensive content:
- Keep core workflow in SKILL.md
- Move detailed docs to references/ (loaded on-demand)
- Store output assets in assets/ (not loaded into context)

### 2. Skill.md Structure

```markdown
---
name: skill-name
description: Brief description. Use when [triggers].
---

# Skill Title

When users request [trigger]:
1. [Action]
2. [Action]

## Workflow A

For [condition]:
- [Instruction]

## Advanced Topics

See [references/details.md](references/details.md) for...
```

### 3. Scripts Pattern

Add scripts/ when Claude would repeatedly write similar code:
- Validation logic
- Format transformations
- Complex deterministic operations

Scripts should have explicit error handling and no "magic numbers".

### 4. Token Efficiency

Challenge each line:
- Does Claude really need this explanation?
- Can I assume Claude knows this?
- Does this justify its token cost?

Prefer code examples over verbose explanations.

## Git Workflow

This repository follows standard git practices:

```bash
# Create feature branch
git checkout -b feature-name

# Make changes
git add .
git commit -m "feat: description"

# Push
git push -u origin feature-name

# Create PR via GitHub UI or gh CLI
gh pr create --title "..." --body "..."
```

## Common Tasks

### Viewing a Skill's Structure

```bash
ls -R skill-name/
```

### Testing SKILL.md Frontmatter

```bash
head -20 skill-name/SKILL.md  # Check first 20 lines for frontmatter
```

### Finding Skills by Pattern

```bash
grep -r "pattern-name" */SKILL.md
```

### Packaging Multiple Skills

```bash
for dir in skill-*/; do
  skill=$(basename "$dir")
  zip -r "${skill}.zip" "$dir" -x "*.git*"
done
```

## Architecture Notes

### Skill Discovery and Activation

The frontmatter `description` field is critical - it contains trigger patterns that help Claude decide when to activate a skill. The description should be specific about:
- File types that trigger it (.pptx, .pdf, etc.)
- Keywords (MCP, bookmarklet, etc.)
- Task types (creating, analyzing, optimizing, etc.)

### Context Window Management

Skills are loaded progressively:
1. **Metadata** (name + description): Always loaded
2. **SKILL.md body**: Loaded when skill triggers
3. **Bundled resources**: Loaded as needed by Claude

This three-tier loading enables context-efficient skill ecosystems.

### Validation and Quality

Before uploading a skill:
- [ ] Frontmatter validates (name/description requirements)
- [ ] SKILL.md under 500 lines (move extras to references/)
- [ ] Written in imperative voice (instructions TO Claude)
- [ ] No over-explanations of basic concepts
- [ ] Scripts tested if present
- [ ] Unused directories deleted

## Anti-Patterns to Avoid

- Writing documentation ABOUT Claude instead of instructions TO Claude
- First person in descriptions ("I can help..." → "Processes...")
- Over-explaining what Claude already knows
- Nesting references deeply (file1→file2→file3)
- Including executables or binaries in skills
- Creating README.md or CHANGELOG.md (not needed for skills)
- Skills over 500 lines without splitting to references/

## License

MIT License - See LICENSE file
