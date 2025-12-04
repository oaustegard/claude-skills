# Creating Skills

Create portable, reusable expertise that extends Claude's capabilities across contexts.

## When to Create Skills

Skills are appropriate when:
- Capability needed across multiple projects/conversations
- Procedural knowledge that applies broadly (not project-specific)
- Instructions should activate automatically on trigger patterns
- Want portable expertise that loads progressively on-demand

Not appropriate when:
- Context is project-specific (use Project instructions instead)
- One-off task (use standalone prompt instead)
- See main crafting-instructions guidance for detailed decision framework

## Skill Structure

Every skill is a directory containing:
- `SKILL.md` (required): Frontmatter + imperative instructions
- `scripts/` (optional): Executable code for deterministic operations
- `references/` (optional): Detailed docs loaded on-demand
- `assets/` (optional): Templates/files used in output

Create this structure directly:
```bash
mkdir -p skill-name/{scripts,references,assets}
```

Delete unused directories before packaging.

## Naming Convention

Use gerund form (verb + -ing):
- ✅ `processing-pdfs`, `analyzing-data`, `creating-reports`
- ❌ `pdf-helper`, `data-tool`, `report-maker`

Requirements:
- Lowercase letters, numbers, hyphens only
- Max 64 characters
- No reserved words (anthropic, claude)

## Frontmatter Requirements

```yaml
---
name: skill-name
description: [Action verbs] [what]. Use for: [trigger patterns].
---
```

**name:** Follow naming convention above

**description:** (max 1024 chars)
- **Lead with action verbs**: "Create", "Generate", "Analyze", "Extract" (imperative, not descriptive)
- **State capabilities concisely**: What the skill does in active voice
- **Explicit trigger section**: "Use for:" followed by comma-separated patterns
- **Trigger specificity**: File types (.docx, .pptx), keywords (chart, visualize), task verbs (debug, optimize), user phrases
- **No XML tags, no procedural steps**

**Strong examples:**
- "Create and edit PowerPoint presentations (.pptx) with layouts and formatting. Use for: slide creation, presentation requests, .pptx file mentions, pitch deck generation."
- "Analyze and optimize SQL query performance. Use for: slow query debugging, EXPLAIN output analysis, optimization requests, database performance tuning."
- "Generate interactive data visualizations using Vega-Lite. Use for: chart creation, plotting data, visualization requests, uploaded CSV/JSON with charting intent."

**Weak examples:**
- "I can help create presentations" (first person, passive, no triggers)
- "Presentation creator" (descriptive noun, no actions, no triggers)
- "Creates PowerPoint presentations. Use when users mention slides" (descriptive "Creates", weak "Use when", incomplete triggers)
- "Advanced presentation tool with animations and transitions" (implementation details, no actions or triggers)

**Pattern:** `[Verb] [Verb] [Verb] [object/domain]. Use for: [trigger1], [trigger2], [trigger3].`

The description determines skill activation—imperative verbs and explicit triggers are critical.

## Writing Effective SKILL.md

Apply crafting-instructions core principles when writing skill instructions:
- **Imperative Construction**: Direct commands, not suggestions
- **Strategic Over Procedural**: Goals and decision frameworks, not step-by-step
- **Trust Base Behavior**: Claude knows basics, specify only skill-specific needs
- **Positive Directive Framing**: State what to do, not what to avoid
- **Provide Context**: Explain WHY for non-obvious requirements

**Model-aware skill writing:**
Skills may be executed by any Claude model. Write for robustness:
- Lead with goals (Opus) but include decision frameworks (Sonnet)
- Provide WHY context (both benefit, Opus leverages more)
- Include 1-2 examples (Sonnet benefits; Opus uses if helpful)
- State explicit edge case handling rather than assuming inference

If skill is known to run on a specific model, calibrate:
- **Sonnet:** More procedural detail, explicit conditions, concrete examples
- **Opus:** More strategic, principle-based, trust judgment for unstated cases

See main crafting-instructions guidance (§ Core Optimization Principles) for details.

## Bundled Resources Patterns

### scripts/
Add when Claude would repeatedly write similar code:
- Validation logic (schema checking, format verification)
- Complex transformations (data normalization, format conversion)
- Deterministic operations requiring exact consistency

Scripts should have explicit error handling and clear variable names.

### references/
Add when:
- SKILL.md approaching 500 lines
- Detailed domain knowledge (API docs, schemas, specifications)
- Content applies to specific use cases only, not core workflow

Keep references one level deep (avoid file1 → file2 → file3 chains).

### assets/
Add for:
- Templates users will receive in output
- Files copied/referenced but not loaded into context
- Images, fonts, static resources

Assets save tokens—they're used but not read into context.

**Decision framework:** Will Claude repeatedly generate similar code? → scripts/. Is there extensive domain knowledge? → references/. Are there output templates? → assets/. Otherwise SKILL.md only.

## Progressive Disclosure

Skills load in three tiers:
1. **Metadata** (name + description): Always loaded for all skills
2. **SKILL.md body**: Loaded when skill activates
3. **Bundled resources**: Loaded as Claude reads them

Keep SKILL.md focused on core workflows (~500 lines max). Move detailed content to references/ for on-demand loading. This enables context-efficient skill ecosystems.

## Token Efficiency

Challenge each line: Does Claude really need this explanation? Can I assume Claude knows this? Does this justify its token cost?

Prefer concise patterns:
- Code examples over verbose explanations
- Decision frameworks over exhaustive lists
- Strategic goals over procedural steps

## Packaging & Delivery

Create ZIP archive:
```bash
cd /home/claude
zip -r /mnt/user-data/outputs/skill-name.zip skill-name/
```

Verify contents:
```bash
unzip -l /mnt/user-data/outputs/skill-name.zip
```

Show user the packaged structure:
```bash
tree skill-name/
# or
ls -lhR skill-name/
```

Provide download link:
```markdown
[Download skill-name.zip](computer:///mnt/user-data/outputs/skill-name.zip)
```

## Version Control (Optional)

For skills under active development, track changes:
```bash
cd /home/claude/skill-name
git init && git add . && git commit -m "Initial: skill structure"
```

After modifications:
```bash
git add . && git commit -m "Update: description of change"
```

See **versioning-skills** for advanced patterns (rollback, branching, comparison).

## Best Practices

**Structure:**
- Lead with clear overview of what skill enables
- Group related instructions together
- Use headings that describe goals, not procedures
- Reference other skills/resources when appropriate

**Instructions:**
- Write TO Claude (imperative commands) not ABOUT Claude (documentation)
- Assume Claude's intelligence—avoid over-explaining basics
- Show code examples for complex patterns
- Specify success criteria, let Claude determine approach
- Use fully qualified names for MCP tools: `ServerName:tool_name` (prevents collisions)

**Content:**
- Keep frequently-used guidance in SKILL.md
- Move detailed/specialized content to references/
- Include WHY context for non-obvious requirements
- Use consistent terminology throughout

**Resources:**
- Only add bundled resources that solve real problems
- Scripts should have error handling and clear outputs
- References should be focused and topic-specific
- Delete unused directories before packaging

**Testing:**
- Test with 3+ real scenarios (simple, complex, edge case)
- Verify skill activates on expected trigger patterns
- Confirm bundled resources are accessible and functional
- Iterate based on actual usage, not assumptions

## Quality Checklist

Before providing skill to user:

**Metadata:**
- [ ] Name: lowercase, hyphens, gerund form, max 64 chars
- [ ] Description: third person, includes WHAT + WHEN triggers, max 1024 chars, no XML

**Structure:**
- [ ] SKILL.md under 500 lines (move extras to references/)
- [ ] Unused directories deleted
- [ ] References one level deep (no long chains)

**Content:**
- [ ] Imperative voice throughout
- [ ] Positive directives (not negative restrictions)
- [ ] Strategic goals over procedural steps where possible
- [ ] Context provided for non-obvious requirements
- [ ] Examples perfectly demonstrate desired patterns
- [ ] Consistent terminology

**Resources:**
- [ ] Scripts solve actual problems (not punting to Claude)
- [ ] Scripts have error handling and clear outputs
- [ ] References are focused and topic-specific
- [ ] Assets are templates/files for output

**Testing:**
- [ ] Tested on 3+ real scenarios
- [ ] Activates on expected triggers
- [ ] Bundled resources accessible
- [ ] Package structure verified
