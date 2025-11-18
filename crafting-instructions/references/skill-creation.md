# Skill Creation Decision Guide

When and how to create Skills, with reference to the comprehensive **creating-skill** skill.

## When to Create a Skill

Create a skill when:

### Repeated Procedures
You find yourself giving the same instructions across multiple conversations.

**Signal:** "I've explained this workflow 3+ times"

**Example:** Instead of repeatedly explaining "review code for security using OWASP standards", create a `security-review` skill.

### Portable Expertise
The knowledge applies across many contexts, not just one project.

**Test:** "Would this be useful in completely different projects?"

**Example:** Excel formula patterns, data analysis frameworks, documentation standards.

### Auto-Activation Desired
You want Claude to recognize and apply this expertise automatically.

**Signal:** "Claude should know to do this when I mention X"

**Example:** When user uploads a PDF form, Claude should remember the form-filling workflow.

### Consistent Quality Standards
You need specific quality or methodology applied consistently.

**Signal:** "The output needs to follow these patterns every time"

**Example:** Brand guidelines, code review checklists, report templates.

## When NOT to Create a Skill

### One-Time Procedures
If it won't be repeated, use a prompt or project instruction.

**Instead:** Simple prompt for one-off tasks.

### Project-Specific Context
If it only applies to one initiative or workspace.

**Instead:** Project instructions with persistent context.

### Rapidly Changing Requirements
If the procedures are still evolving and unstable.

**Instead:** Project instructions you can easily update.

### Simple Operations
If Claude already handles it well without guidance.

**Instead:** Trust Claude's base capabilities.

## Skill vs Project Quick Check

Ask: "Does this teach Claude HOW to do something, or give it context about WHAT to know?"

- **HOW to do** → Skill (procedural knowledge)
- **WHAT to know** → Project (declarative knowledge)

Ask: "Will this be used across multiple projects/conversations?"

- **Yes** → Skill (portable)
- **No** → Project instructions (scoped)

Ask: "Should Claude activate this automatically when relevant?"

- **Yes** → Skill (auto-triggered)
- **No** → Project instructions (always loaded)

## Creating Skills: The Comprehensive Resource

For complete guidance on creating skills, use the **creating-skill** skill:

**What creating-skill covers:**
- Skill structure and file organization
- Progressive disclosure architecture
- Frontmatter requirements (name, description)
- When to add scripts/, references/, assets/
- Packaging and distribution
- Version control integration
- Quality checklists
- Anti-patterns to avoid

**When to use creating-skill:**
Once you've decided to create a skill (using this guide), delegate to creating-skill for the mechanics of actually building it.

## Quick Overview: Skill Mechanics

For users who want basic understanding before diving into creating-skill:

### Skill Structure

**Simple skill:**
```
skill-name/
└── SKILL.md (all instructions)
```

**Medium skill:**
```
skill-name/
├── SKILL.md (overview and core instructions)
└── references/ (detailed domain knowledge)
```

**Complex skill:**
```
skill-name/
├── SKILL.md (overview and workflow)
├── scripts/ (executable code)
├── references/ (detailed docs)
└── assets/ (templates, resources)
```

### Progressive Disclosure

Skills load in stages:
1. **Metadata** (name + description) - Always scanned
2. **SKILL.md body** - Loaded when skill triggers
3. **Bundled resources** - Loaded as needed by Claude

This means you can have many skills available without overwhelming context.

### Activation

Skills activate when:
- User mentions keywords from description
- Task matches patterns in description
- Claude determines skill is relevant
- Description includes "use proactively" for auto-triggering

## Decision Examples

### Example 1: Security Review Process

**Context:** You want Claude to review code for security vulnerabilities using OWASP standards.

**Question:** Skill or project instruction?

**Analysis:**
- Will you use this across multiple projects? YES
- Is it procedural knowledge (HOW to review)? YES
- Should it auto-activate when reviewing code? YES
- Is it portable expertise? YES

**Decision:** Create a **skill** called `security-review`

### Example 2: Q4 Marketing Campaign

**Context:** You have campaign strategy docs, competitor analysis, and target audience research for Q4.

**Question:** Skill or project instruction?

**Analysis:**
- Will you use this across multiple contexts? NO (Q4 specific)
- Is it primarily reference material (WHAT to know)? YES
- Does it need to persist in one workspace? YES
- Is it time-bound context? YES

**Decision:** Create a **project** called "Q4 Marketing Campaign"

### Example 3: Excel Formula Patterns

**Context:** You frequently work with Excel and have specific formula patterns and data analysis approaches.

**Question:** Skill or project instruction?

**Analysis:**
- Will you use this across multiple projects? YES (any Excel work)
- Is it procedural knowledge (HOW to analyze)? YES
- Should it auto-activate for Excel files? YES
- Is it portable expertise? YES

**Decision:** Create a **skill** called `excel-analysis`

### Example 4: Client Implementation

**Context:** You're implementing for Acme Corp with their specific requirements, SOW, and technical constraints.

**Question:** Skill or project instruction?

**Analysis:**
- Will you use this across contexts? NO (Acme specific)
- Is it primarily reference material? YES (requirements, SOW)
- Does it need to persist in workspace? YES
- Should team members access it? YES (Team plan)

**Decision:** Create a **project** called "Acme Corp Implementation"

But also use **skills** like:
- `deployment-checklist` (reusable procedure)
- `documentation-generator` (reusable capability)
- `security-audit` (reusable process)

## Combining Skills with Projects

Often the best solution uses both:

**Pattern:** Project for context + Skills for capabilities

**Example:**
- **Project:** "Healthcare Analytics Q1" (patient data, regulations, goals)
- **Skills:** `hipaa-compliance` (procedures), `clinical-metrics` (calculations)

**Why both:**
- Project provides persistent, initiative-specific context
- Skills provide portable, reusable procedures
- Together: Context-aware + methodologically consistent

## Migration Paths

### From Repeated Prompts to Skill

**Signal:** You've typed similar instructions 3+ times in different conversations.

**Action:**
1. Capture the common elements
2. Identify trigger patterns (keywords, file types, tasks)
3. Use creating-skill to build the skill
4. Test across diverse contexts

### From Project to Skill

**Signal:** Other projects need the same procedures.

**Action:**
1. Extract procedural content from project
2. Make it context-independent
3. Create skill with that methodology
4. Update projects to use the skill

### From Skill to Project

**Signal:** Skill is only used in one project and has project-specific details.

**Action:**
1. Copy skill content to project instructions
2. Add project-specific context
3. Remove skill if no longer needed elsewhere

## Next Steps

**If you've decided to create a skill:**

Use the **creating-skill** skill for comprehensive guidance on:
- File structure and organization
- Writing effective SKILL.md instructions
- Progressive disclosure strategies
- Adding scripts, references, and assets
- Version control and packaging
- Testing and iteration

**If you're still deciding:**

Review [skill-vs-project.md](skill-vs-project.md) for detailed comparison and use cases.

**If you want a project instead:**

See [project-instructions.md](project-instructions.md) for guidance on crafting effective project custom instructions.

## Common Questions

### "Can I turn this prompt into a skill?"

Ask:
- Have I used this prompt 3+ times? → Maybe
- Will I use it across different contexts? → Probably yes
- Does it teach HOW to do something? → Yes, skill material
- Does it just provide context/data? → No, not skill material

### "Should my skill include project-specific details?"

No. Skills should be context-independent. Project-specific details belong in project instructions. The skill provides the methodology; the project provides the context.

### "Can skills use information from projects?"

Yes. A skill activated within a project can access that project's knowledge base. Skills provide capabilities; projects provide context.

### "How many skills is too many?"

No limit. Skills use progressive disclosure - they only load when relevant. You can have dozens of skills without performance impact.

## Summary

**Create a skill when:**
- Repeated procedures across contexts
- Portable expertise
- Auto-activation desired
- Consistent quality needed

**Use creating-skill for:**
- Complete skill creation workflow
- File structure and organization
- Progressive disclosure implementation
- Packaging and distribution

**Use project instructions for:**
- Initiative-specific context
- Reference material for one workspace
- Team collaboration space
- Time-bound information
