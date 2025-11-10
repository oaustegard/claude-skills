---
name: creating-skill
description: Creates Skills for Claude. Use when users request creating/updating skills, need skill structure guidance, or mention extending Claude's capabilities through custom skills.
---

# Creating Skills

When users request skill creation, follow this workflow.

## Skill Creation Workflow

### Step 1: Gather Requirements

Ask the user:
- "What tasks should this skill support?"
- "Can you give examples of how it would be used?"
- "What would trigger this skill?"

Gather concrete examples before proceeding.

### Step 2: Determine Skill Complexity

**Simple skill** (SKILL.md only):
- Single workflow or pattern
- All guidance fits in ~200 lines
- No repeated code generation

**Medium skill** (SKILL.md + references):
- Multiple workflows or domains
- Detailed reference material (API docs, schemas)
- 200-500 lines total

**Complex skill** (SKILL.md + references + scripts):
- Deterministic operations needed (validation, transformation)
- Would require Claude to repeatedly write similar code

**Decision:** 
- Will Claude repeatedly write similar code? → Add scripts/
- Is there detailed domain knowledge (>100 lines)? → Add references/
- Are there templates or assets for output? → Add assets/
- Everything fits in SKILL.md? → SKILL.md only

### Step 3: Initialize Skill Structure

Run the initialization script:

```bash
scripts/init_skill.sh --name <skill-name>
```

**Naming convention:** Use gerund form (verb + -ing):
- Good: `processing-pdfs`, `analyzing-spreadsheets`, `creating-reports`
- Bad: `pdf-helper`, `spreadsheet-tool`, `report-maker`

This creates:
```
skill-name/
├── SKILL.md (template with TODOs)
├── scripts/ (for executable code)
├── references/ (for detailed docs)
└── assets/ (for templates/output files)
```

Delete unused directories.

### Step 4: Write SKILL.md

**Use `create_file` to write complete files.** Never use `str_replace` to replace entire file contents - this wastes tokens. After init_skill.sh creates templates, use `create_file` to overwrite them efficiently.

#### Required Frontmatter

```yaml
---
name: skill-name
description: What the skill does. Use when [trigger patterns].
---
```

**name requirements:**
- Lowercase letters, numbers, hyphens only
- Max 64 characters
- No reserved words (anthropic, claude)

**description requirements:**
- Max 1024 characters
- Third person voice ("Processes files" not "I process files")
- Include WHAT it does and WHEN to use it
- List trigger patterns: file types, keywords, tasks
- No XML tags

**Good descriptions:**
- "Creates PowerPoint presentations. Use when users mention slides, .pptx files, or presentations."
- "Analyzes SQL queries. Use when debugging slow queries or optimizing database operations."

**Bad descriptions:**
- "I can help you create presentations" (first person)
- "Presentation creator" (no trigger patterns)
- "Creates presentations with slides and animations using advanced features" (too much implementation detail)

#### Body Structure

Write in imperative voice with clear instructions:

```markdown
# Skill Name

When users request [trigger]:
1. [Action]
2. [Action]
3. [Action]

## Workflow Pattern A

For [condition]:
- [Instruction]
- [Instruction]

## Workflow Pattern B

For [different condition]:
- [Different instruction]
```

**Key principles:**
- Direct instructions to Claude, not documentation about Claude
- Assume Claude's intelligence - don't over-explain
- Use code examples over verbose explanations
- Keep SKILL.md under 500 lines
- Progressive disclosure: move detailed content to references/

For computational workflows, see [references/environment-reference.md](references/environment-reference.md) for file structure, pre-installed packages, and common patterns.

### Step 5: Version Control Integration

**REQUIRED: Use versioning-skills after ANY file modification.**

After initializing the skill:

```bash
cd /home/claude/skill-name
git init && git add . && git commit -m "Initial: skill structure"
```

After each str_replace or create_file operation:

```bash
cd /home/claude/skill-name
git add .
git commit -m "Update: describe change"
```

**Commit message patterns:**
- `"Initial: skill structure"` - After init_skill.sh
- `"Add: [feature]"` - New functionality
- `"Fix: [issue]"` - Corrections
- `"Update: [section]"` - Content changes
- `"Refactor: [component]"` - Structural changes

This enables rollback, change comparison, and experimental branching. See versioning-skills for full capabilities.

### Step 6: Add Bundled Resources

Add scripts/, references/, or assets/ as needed:
- **scripts/**: Executable code for validation/transformation (see [references/bundled-resources.md](references/bundled-resources.md))
- **references/**: Detailed docs for specific use cases (group by domain, keep one level deep)
- **assets/**: Templates and files for output (not loaded into context)

Delete unused directories. For detailed guidance, MCP tool patterns, and examples, see [references/bundled-resources.md](references/bundled-resources.md).

### Step 6: Package Skill

**DO NOT use scripts/package_skill.py - it has been removed.**

Package the skill directly:

```bash
cd /home/claude
zip -r /mnt/user-data/outputs/skill-name.zip skill-name/
```

**Verify contents:**
```bash
unzip -l /mnt/user-data/outputs/skill-name.zip
```

**Critical:** Always show the user the packaged .zip file hierarchy:
```bash
tree skill-name/
# or
ls -lhR skill-name/
```

### Step 7: Provide to User

Link the .zip file to the user:

```markdown
[Download skill-name.zip](computer:///mnt/user-data/outputs/skill-name.zip)
```

## Essential Guidelines

### Concise is Key

The context window is shared. Only include what Claude doesn't already know.

**Challenge each line:**
- Does Claude really need this explanation?
- Can I assume Claude knows this?
- Does this justify its token cost?

**Good (concise):**
```markdown
Extract text with pdfplumber:
```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
```

**Bad (verbose):**
```markdown
PDFs (Portable Document Format) are files that contain text and images. 
To extract text from a PDF, you need a library. We recommend pdfplumber 
because it's easy to use. First install it with pip, then...
```

### Degrees of Freedom

Match specificity to task fragility:

**High freedom** (text instructions): Multiple valid approaches, context-dependent decisions
**Medium freedom** (scripts with parameters): Preferred patterns with flexibility
**Low freedom** (exact scripts): Fragile operations requiring consistency

### Progressive Disclosure

SKILL.md is an overview pointing to details:

1. **Metadata** (name + description): Always loaded
2. **SKILL.md body**: Loaded when skill triggers (~500 lines max)
3. **Bundled resources**: Loaded as needed by Claude

**Pattern:** Keep SKILL.md lean, move detailed content to references/.

**When to split:**
- SKILL.md approaching 500 lines
- Content applies to specific use cases only
- Detailed reference material (API docs, schemas)

**When to keep inline:**
- Core workflow information
- Content used in every task
- Essential decision trees

### Common Patterns

#### Validation Workflow

For quality-critical tasks:

```markdown
1. Create output
2. Validate: `python scripts/validate.py output.json`
3. If errors: Fix and re-validate
4. Only proceed when validation passes
5. Apply changes
```

#### Template Pattern

Provide templates for consistent output:

```markdown
Use this structure:

[template here]

Adapt as needed for the specific context.
```

#### Conditional Workflow

Guide through decision points:

```markdown
**Creating new content?** → Follow creation workflow below
**Editing existing content?** → Follow editing workflow below

## Creation Workflow
[steps]

## Editing Workflow  
[steps]
```

## Advanced Topics

For complex scenarios, see:
- [advanced-patterns.md](references/advanced-patterns.md) - Validation workflows, visual analysis, plan-validate-execute pattern
- [optimization-techniques.md](references/optimization-techniques.md) - Discovery optimization, token budget management, model-specific tuning
- [environment-reference.md](references/environment-reference.md) - Comprehensive environment patterns and detailed documentation

## Quality Checklist

Before providing skill to user:

**Structure:**
- [ ] Name: lowercase, hyphens, max 64 chars
- [ ] Description: third person, what+when, max 1024 chars, no XML
- [ ] SKILL.md under 500 lines
- [ ] References one level deep
- [ ] Unused directories deleted

**Content:**
- [ ] Written in imperative voice (instructions to Claude)
- [ ] No over-explanations of basic concepts
- [ ] Concrete examples, not abstract explanations
- [ ] Consistent terminology throughout
- [ ] Package installation instructions included

**Scripts (if present):**
- [ ] Scripts solve problems (don't punt to Claude)
- [ ] Error handling is explicit
- [ ] All values documented (no "voodoo constants")
- [ ] Scripts tested and working

**Testing:**
- [ ] Tested with 3+ real usage scenarios (simple, complex, failure)
- [ ] Verified skill activates on expected triggers
- [ ] Checked that bundled resources are accessible

## Anti-Patterns to Avoid

**Don't:**
- Use `str_replace` for entire file contents (use `create_file`)
- Write documentation about Claude (write instructions to Claude)
- Over-explain what Claude already knows
- Use first person in descriptions ("I can help...")
- Assume packages are installed without instructions
- Nest references deeply (file1 → file2 → file3)
- Use Windows-style paths (use forward slashes)
- Add unnecessary documentation files (README.md, CHANGELOG.md)
- Create skills without testing them
- Include untested scripts
- Split tiny files unnecessarily
- Write vague error messages in scripts
- Mix terminology for same concept
- Forget MCP server prefixes (use `ServerName:tool_name`)
- Pass file paths to scripts expecting directories

## Iteration

After creating a skill:

1. Use it on real tasks (not synthetic examples)
2. Observe where Claude struggles or succeeds
3. Update SKILL.md or bundled resources based on observations
4. Test again on similar requests
5. Repeat until effective

Skills improve through usage observation, not assumptions.
