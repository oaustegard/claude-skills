# Advanced Workflow Patterns

## Validation Scripts and Error Handling

For fragile operations, create validation scripts that catch errors early.

### Example: PDF Form Filling with Validation

````markdown
## PDF form filling workflow

1. Extract form structure: `python scripts/extract_fields.py input.pdf fields.json`
2. **Validate field mappings**: `python scripts/validate_boxes.py fields.json`
   - Returns: "OK" or lists conflicts
3. Apply values: `python scripts/fill_form.py input.pdf fields.json output.pdf`
````

### Why Validation Scripts Work

- Machine-verifiable checks
- Specific error messages: "Field 'signature_date' not found. Available fields: customer_name, order_total, signature_date_signed"
- Early error detection before destructive changes
- Clear debugging paths

### Script Best Practices

- Make scripts solve problems rather than punt to Claude
- Include explicit, helpful error handling
- Avoid "voodoo constants" - justify all hardcoded values
- Document what each script does and when to use it

## Create Verifiable Intermediate Outputs

The "plan-validate-execute" pattern catches errors early by having Claude create a plan in structured format, validate with a script, then execute.

### Problem Example

User asks Claude to update 50 form fields in a PDF based on a spreadsheet. Without validation, Claude might:
- Reference non-existent fields
- Create conflicting values
- Miss required fields
- Apply updates incorrectly

### Solution: Plan-Validate-Execute

Workflow becomes: analyze → **create plan file** → **validate plan** → execute → verify

Add intermediate `changes.json` file validated before applying changes.

### Why This Pattern Works

- **Catches errors early**: Validation finds problems before changes applied
- **Machine-verifiable**: Scripts provide objective verification
- **Reversible planning**: Claude can iterate on plan without touching originals
- **Clear debugging**: Error messages point to specific problems

### When to Use

Batch operations, destructive changes, complex validation rules, high-stakes operations.

## Use Visual Analysis

When inputs can be rendered as images, have Claude analyze them:

````markdown
## Form layout analysis

1. Convert PDF to images:
   ```bash
   python scripts/pdf_to_images.py form.pdf
   ```

2. Analyze each page image to identify form fields
3. Claude can see field locations and types visually
````

Claude's vision capabilities help understand layouts and structures difficult to describe programmatically.

## Workflow Pattern Examples

### Sequential Workflow (Low Ambiguity)

```markdown
## Deploy application

1. Run tests: `npm test`
2. Build production: `npm run build`
3. Deploy: `python scripts/deploy.py --environment prod`
4. Verify deployment: Check output for "Deployment successful"
```

### Conditional Workflow (Medium Ambiguity)

```markdown
## Process customer data

1. Validate input format
2. If CSV format:
   - Use pandas for processing
3. If JSON format:
   - Use json module for processing
4. Transform according to schema in `references/schema.md`
5. Output to database
```

### Open-Ended Workflow (High Ambiguity)

```markdown
## Analyze codebase

1. Identify the primary language and frameworks
2. Review architecture and organization
3. Check for common issues:
   - Security vulnerabilities
   - Performance bottlenecks
   - Code quality concerns
4. Generate report with findings and recommendations
```

## XML Tags for Structure

Claude was trained with XML tags in training data. Use them to structure complex skills:

```markdown
<workflow>
1. <step>Validate input</step>
2. <step>Process data</step>
3. <step>Generate output</step>
</workflow>

<examples>
<example type="simple">...</example>
<example type="complex">...</example>
</examples>
```

Especially useful for:
- Complex multi-step workflows
- Organizing multiple examples
- Structuring reference material
- Separating instructions from metadata
