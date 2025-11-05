# Skill Optimization Techniques

## Skill Discovery Optimization ("Tool SEO")

Make your skill easy for Claude to discover and use appropriately.

### In the Description Field

Include key terms and triggers users might mention:
- Use action verbs matching user intent
- Consider phrases like "use proactively" for auto-triggering
- For critical skills: "MUST BE USED when..." for high-priority scenarios

**Example:**
```yaml
description: "Processes Excel spreadsheets with formulas and formatting. Use proactively when users mention Excel, .xlsx files, spreadsheets, or data analysis tasks requiring structured output."
```

## Token Budget Management

For skills used in resource-constrained environments:

### Minimize Initialization Cost

- Keep SKILL.md under 500 lines
- Use progressive disclosure aggressively
- Move verbose examples to reference files
- Create lightweight wrapper scripts instead of large inline code blocks

### Track Context Usage

- Monitor which files Claude loads most often
- Consider splitting frequently-used vs. rarely-used content
- Use mutually exclusive reference files for different domains

### Context-Aware Organization

For skills with multiple domains:
```
bigquery-skill/
├── SKILL.md (navigation only)
└── references/
    ├── finance.md
    ├── sales.md
    └── product.md
```

Claude loads only the relevant domain file, keeping other domains at zero context cost.

## Model-Specific Optimization

### For Claude Haiku

- Provide more explicit guidance
- Fewer assumptions about implicit knowledge
- More structured workflows
- Clearer validation steps

### For Claude Sonnet

- Balance between guidance and flexibility
- Moderate detail level
- Standard approaches work well

### For Claude Opus

- Assume more intelligence
- Focus on edge cases and subtleties
- Less hand-holding needed
- Can handle more implicit instructions

**Strategy**: If supporting multiple models, aim for Sonnet-level detail (works reasonably well for all three).

## Making Intent Clear

When bundling code, make execution intent explicit:

### For Execution

```markdown
Run `analyze_form.py` to extract fields
Do not modify the script, execute as-is
```

### For Reference

```markdown
See `analyze_form.py` for the extraction algorithm details
Review the implementation if you need to understand field detection logic
```

## File Organization for Efficiency

### Descriptive Naming

- Good: `stripe_payment_webhook_handler.py`
- Bad: `handler.py`

### Domain-Based Structure

- Good: `references/authentication/`, `references/payment/`
- Bad: `docs/file1.md`, `docs/file2.md`

### Table of Contents for Long Files

For reference files >100 lines, include TOC at top:

```markdown
# API Reference

## Table of Contents
- [Authentication](#authentication)
- [Payments](#payments)
- [Webhooks](#webhooks)
...

## Authentication
...
```

This lets Claude see full scope when previewing without loading entire file.

## Bundle Comprehensive Resources

No context penalty for unbundled resources until accessed. Include:
- Complete API docs
- Extensive examples
- Large datasets
- Detailed guides

Claude loads only what's needed for each task.

## Validation Script Patterns

For operations prone to errors:
1. Extract structured plan from Claude's intent
2. Validate plan with deterministic script
3. Execute only after validation passes

This catches errors early without context cost of loading full validation logic into Claude's reasoning.
