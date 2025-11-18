# Bundled Resources Reference

Detailed guidance for adding scripts, references, assets, and other resources to skills.

## Package Dependencies

Reference [environment-reference.md](environment-reference.md) for pre-installed packages.

### Package Reference Patterns

If package is already installed:
- Reference version directly: "Uses pandas 2.3.3 (pre-installed)"
- Skip installation instructions

If package is NOT installed:
- Include installation: "Install: `pip install <pkg> --break-system-packages`"

**Examples:**
- **Bad:** "Use the pdf library"
- **Good:** "Uses pypdf 5.9.0 (pre-installed)"
- **Good:** "Install: `pip install pdfplumber --break-system-packages`"

**Environment context:**
- claude.ai supports package installation (npm, PyPI, GitHub)
- API environments may not support package installation
- Always specify versions for pre-installed packages

## MCP Tools

### Fully Qualified Names

Always use fully qualified names when referencing MCP tools: `ServerName:tool_name`

**Why:** Without the server prefix, tools may not be found or may collide with other tools.

**Examples:**
- `BigQuery:bigquery_schema` - Access BigQuery schema tool
- `GitHub:create_issue` - Create GitHub issues
- `Slack:post_message` - Post to Slack channels
- `PostgreSQL:execute_query` - Execute database queries

### Common MCP Patterns in Skills

**Conditional MCP usage:**
```markdown
If GitHub MCP is available:
1. Use `GitHub:create_issue` to file the bug
2. Use `GitHub:create_pr` to submit the fix

Otherwise:
1. Generate issue content in markdown
2. Provide as output for manual filing
```

**Required vs optional:**
```markdown
## Prerequisites

**Required:**
- MCP server: GitHub

**Optional:**
- MCP server: Jira (for ticket cross-linking)
```

**Error handling:**
```markdown
Attempt to use `ServerName:tool_name`. If tool not found:
- Fall back to manual workflow
- Inform user of missing MCP server
```

## scripts/ Directory

Executable code for deterministic operations that Claude would repeatedly write.

### When to Add Scripts

**Add scripts when:**
- Validation logic is complex (multi-field form validation, schema checking)
- Transformation logic is deterministic (format conversion, data normalization)
- Operations have fragile edge cases (date parsing, encoding detection)
- Claude would write similar code repeatedly (>3 times per skill usage)

**Don't add scripts when:**
- Simple operations Claude handles well (basic file operations)
- Logic varies significantly by context (custom business rules)
- Code is obvious and short (<10 lines of Python)

### Script Structure

**Required elements:**
```python
#!/usr/bin/env python3
# scripts/script_name.py
# One-line description of what this does

import sys  # Minimal imports only

def main_function(param):
    """Clear docstring explaining inputs/outputs."""
    # Implementation
    pass

if __name__ == "__main__":
    # Explicit argument parsing
    if len(sys.argv) < 2:
        print("Usage: script_name.py <param>", file=sys.stderr)
        sys.exit(1)

    result = main_function(sys.argv[1])

    # Explicit exit codes
    sys.exit(0 if result else 1)
```

**Best practices:**
- Explicit error handling (no silent failures)
- Clear error messages (explain what went wrong and how to fix)
- No "magic numbers" (document all constants)
- Minimal dependencies (use stdlib when possible)
- Exit codes: 0 = success, 1+ = failure

### Script Examples

**Validation script:**
```python
#!/usr/bin/env python3
# scripts/validate_form_mapping.py
# Validates PDF form field mapping JSON

import json, sys

REQUIRED_FIELDS = ['name', 'email', 'date']
ALLOWED_TYPES = ['text', 'checkbox', 'signature']

def validate_mapping(mapping):
    """Validates form field mapping structure."""
    errors = []

    # Check required fields present
    for field in REQUIRED_FIELDS:
        if field not in mapping:
            errors.append(f"Missing required field: {field}")

    # Check field types valid
    for field, config in mapping.items():
        if config.get('type') not in ALLOWED_TYPES:
            errors.append(f"Invalid type for {field}: {config.get('type')}")

    return errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_form_mapping.py <mapping.json>", file=sys.stderr)
        sys.exit(1)

    try:
        with open(sys.argv[1]) as f:
            mapping = json.load(f)
    except Exception as e:
        print(f"Error reading mapping file: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate_mapping(mapping)

    if errors:
        print("Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    print("Validation passed")
    sys.exit(0)
```

**Transformation script:**
```python
#!/usr/bin/env python3
# scripts/convert_csv_to_json.py
# Converts CSV to nested JSON structure

import csv, json, sys

def convert_to_nested_json(csv_path, output_path):
    """Converts flat CSV to nested JSON by category."""
    data = {}

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = row.pop('category', 'uncategorized')
            if category not in data:
                data[category] = []
            data[category].append(row)

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: convert_csv_to_json.py <input.csv> <output.json>", file=sys.stderr)
        sys.exit(1)

    try:
        convert_to_nested_json(sys.argv[1], sys.argv[2])
        print(f"Converted {sys.argv[1]} to {sys.argv[2]}")
        sys.exit(0)
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        sys.exit(1)
```

### Invoking Scripts from SKILL.md

**Standard pattern:**
```markdown
1. Generate mapping file
2. Validate: `python scripts/validate_form_mapping.py mapping.json`
3. If validation fails (exit code 1): Fix errors and retry
4. Only proceed when validation passes (exit code 0)
5. Apply mapping to PDF
```

**With error handling:**
```markdown
Run validation:
```bash
python scripts/validate_form_mapping.py mapping.json
if [ $? -eq 0 ]; then
    echo "Validation passed"
    # Proceed with next step
else
    echo "Validation failed - review errors above"
    # Fix and retry
fi
```
```

## references/ Directory

Documentation loaded on-demand for specific use cases or detailed information.

### When to Use references/

**Move content to references/ when:**
- Content exceeds 100 lines
- Applies to specific use cases only (not every task)
- Contains detailed reference material (API docs, schemas, specs)
- Would clutter SKILL.md if included inline
- SKILL.md approaches 500 line limit

**Keep content in SKILL.md when:**
- Core workflow information (used in every task)
- Essential decision trees (determines which path to take)
- Brief examples (under 20 lines)
- Critical context (needed to understand the skill)

### Organization Strategy

**Group by domain/use case, not by topic:**

**Good (domain-based):**
```
references/
├── sales-workflows.md      # Sales team workflows
├── finance-workflows.md    # Finance team workflows
└── api-integration.md      # API integration patterns
```

**Bad (topic-based):**
```
references/
├── validation.md           # Validation patterns
├── formatting.md           # Formatting patterns
└── examples.md             # Various examples
```

**Why:** When user asks about sales, load only `sales-workflows.md`. Domain-based organization minimizes unnecessary context loading.

### Reference File Structure

**Template:**
```markdown
# Reference Title

> **Purpose:** One-line explanation of what this covers
> **When to use:** Specific triggers or use cases

## Section 1: Core Concept

[Detailed explanation]

### Subsection

[Examples, code, patterns]

## Section 2: Advanced Topics

[More detailed content]

## Common Patterns

[Reusable recipes]

## Troubleshooting

[Common issues and solutions]
```

### Navigation in SKILL.md

**Clear pointers to references:**
```markdown
## Advanced Features

For API integration patterns, see [references/api-integration.md](references/api-integration.md).

For database schema details, see [references/database-schemas.md](references/database-schemas.md).
```

**Conditional loading:**
```markdown
**Working with sales data?** → See [references/sales-workflows.md](references/sales-workflows.md)
**Working with finance data?** → See [references/finance-workflows.md](references/finance-workflows.md)
```

### Reference Depth

**Keep references one level deep** - avoid chaining references:

**Good:**
```markdown
<!-- In SKILL.md -->
See [references/api.md](references/api.md) for API details.

<!-- In references/api.md -->
[Complete API documentation and examples]
```

**Bad:**
```markdown
<!-- In SKILL.md -->
See [references/api.md](references/api.md) for API details.

<!-- In references/api.md -->
Basic info here. For details, see [references/api-advanced.md](references/api-advanced.md).

<!-- In references/api-advanced.md -->
Detailed info here. For schema, see [references/api-schemas.md](references/api-schemas.md).
```

**Why:** Deep nesting requires multiple file loads and increases cognitive overhead.

## assets/ Directory

Files used in output, not loaded into context.

### When to Use assets/

**Add to assets/ when:**
- Templates that skills copy/modify (PowerPoint templates, HTML boilerplate)
- Static resources for output (logos, fonts, images)
- Sample data for testing (small CSV files, JSON examples)
- Boilerplate code (starter files, configuration templates)

**Don't add to assets/ when:**
- Files are examples for Claude to learn from (use references/ instead)
- Content needs to be in Claude's context (use SKILL.md or references/)
- Files are outputs of the skill (generate these, don't bundle)

### Asset Types

**Templates:**
```
assets/
├── presentation-template.pptx     # PowerPoint template
├── report-template.docx           # Word template
├── dashboard-template.html        # HTML template
└── config-template.json           # Configuration template
```

**Static resources:**
```
assets/
├── company-logo.png
├── brand-fonts/
│   ├── Roboto-Regular.ttf
│   └── Roboto-Bold.ttf
└── icons/
    ├── success.svg
    └── error.svg
```

**Sample data:**
```
assets/
├── sample-sales.csv              # Example sales data
├── sample-customers.json         # Example customer data
└── test-form-fields.json         # Test form configuration
```

### Using Assets in SKILL.md

**Template pattern:**
```markdown
## Creating Presentation

1. Copy template: `cp /mnt/skills/user/my-skill/assets/template.pptx working.pptx`
2. Modify slides using python-pptx
3. Save to outputs: `cp working.pptx /mnt/user-data/outputs/presentation.pptx`
```

**Resource injection:**
```markdown
## Branding

Add company logo from assets:
```python
from PIL import Image
logo = Image.open('/mnt/skills/user/my-skill/assets/company-logo.png')
# ... use in output ...
```
```

**Sample data for testing:**
```markdown
## Testing

Test with sample data:
```bash
python scripts/process.py /mnt/skills/user/my-skill/assets/sample-data.csv
```

Verify output before processing user data.
```

### Asset Best Practices

**Keep assets small:**
- Images: Compress appropriately (logos <100KB, photos <500KB)
- Templates: Remove unused elements
- Sample data: Minimal representative examples (not full datasets)

**Use portable paths:**
```python
# Good: Relative to skill location
skill_dir = '/mnt/skills/user/my-skill'
logo_path = f'{skill_dir}/assets/logo.png'

# Bad: Hardcoded absolute paths
logo_path = '/home/claude/logo.png'  # Won't work in different environments
```

**Document asset usage:**
```markdown
## Assets Included

- `assets/template.pptx`: Base presentation template (includes title slide, section dividers)
- `assets/logo.png`: Company logo (used in header/footer)
- `assets/sample-data.csv`: Test dataset (100 rows of sample sales data)
```

## Directory Cleanup

**Delete unused directories after creating skill structure:**

```bash
# After creating skill directories, delete what you don't need
cd /home/claude/skill-name

# No scripts needed?
rm -rf scripts/

# No references needed?
rm -rf references/

# No assets needed?
rm -rf assets/
```

**Why:** Empty directories add clutter and confusion. Only keep directories you actually use.

## Complete Example Structure

**Simple skill** (SKILL.md only):
```
skill-name/
└── SKILL.md
```

**Medium skill** (with references):
```
skill-name/
├── SKILL.md
└── references/
    ├── api-docs.md
    └── advanced-patterns.md
```

**Complex skill** (full structure):
```
skill-name/
├── SKILL.md
├── scripts/
│   ├── validate.py
│   └── transform.py
├── references/
│   ├── workflows.md
│   └── troubleshooting.md
└── assets/
    ├── template.pptx
    └── sample-data.csv
```

## Testing Bundled Resources

Before packaging:

**Test scripts:**
```bash
# Test with valid input
python scripts/validate.py test-valid.json
echo "Exit code: $?"  # Should be 0

# Test with invalid input
python scripts/validate.py test-invalid.json
echo "Exit code: $?"  # Should be 1

# Test error handling
python scripts/validate.py nonexistent.json
echo "Exit code: $?"  # Should be 2
```

**Verify references load:**
```bash
# Check all reference links are valid
grep -r "references/" SKILL.md
# Verify each file exists

# Check for broken internal links
cd references/
grep -r "](references/" .
# Verify no double-nesting
```

**Test assets accessible:**
```bash
# Verify all assets referenced in SKILL.md exist
grep -r "assets/" SKILL.md
# Check each file exists and is readable

# Check asset file sizes
du -sh assets/*
# Verify no huge files (>5MB each)
```
