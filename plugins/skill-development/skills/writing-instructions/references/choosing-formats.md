# Choosing Between Formats

When to use Skills, Project instructions, or Standalone prompts — and when to combine them.

## Core Distinction

**Project instructions** = "Here's what you need to know" — declarative knowledge, always loaded, workspace-scoped.
**Skills** = "Here's how to do things" — procedural knowledge, loaded on-demand, portable across contexts.
**Prompts** = "Do this now" — ephemeral direction, conversational refinement, one-off context.

## Decision Framework

```
Is this a one-off request with unique context?
└─ YES → Standalone prompt

Does this capability need to work across multiple projects?
└─ YES → Skill

Does this knowledge need to be available for every conversation in a workspace?
└─ YES → Project instructions

Is this primarily reference material or procedural knowledge?
├─ Reference material → Project instructions
└─ Procedures/methods → Skill

Are you approaching context limits?
└─ YES → Use Skills for procedures (progressive disclosure saves tokens)

Do multiple people need this in a shared workspace?
└─ YES → Project instructions (team collaboration)

Is this organization-wide or project-specific?
├─ Organization-wide → Skill
└─ Project-specific → Project instructions
```

## Comparison

| Aspect | Project Instructions | Skills | Prompts |
|--------|---------------------|--------|---------|
| **Scope** | Single workspace | All conversations | Current conversation |
| **Loading** | Always present | On-demand | Immediate |
| **Content** | Reference, context | Procedures, methods | Ad-hoc direction |
| **Token usage** | Always loaded | Progressive disclosure | Per-message |
| **Collaboration** | Team shared | Individual or org-deployed | Individual |
| **Persistence** | Workspace lifetime | Permanent | Ephemeral |
| **Best for** | What to know | How to do things | Do this now |

## Combined Approaches

### Project + Skills (most powerful combination)

Projects provide persistent context while Skills provide portable methods. This separation keeps each focused and independently updatable.

**Example:** A "Legal Contract Review" project contains 50+ template contracts and company policies (reference material). Skills like `contract-analysis` and `risk-assessment` provide the review methodology (procedures). Without Skills, Claude reinvents the methodology each conversation. Without the Project, Claude lacks the specific reference material.

### Project + Skills for Large Context

When a project approaches context limits, moving procedures into Skills reclaims space. Skills use progressive disclosure — they only load when relevant, preserving project context for knowledge.

### Cross-Project Skills

When multiple projects need the same execution patterns (deployment checklists, security audits, documentation standards), Skills prevent duplicating procedures in each project's instructions.

## Anti-Patterns

**Duplicating procedures across projects.** If three client projects all contain the same deployment checklist, extract it into a Skill.

**Putting reference material in Skills.** Skills should contain procedures, not Q4 market data. Put reference material in Projects.

**Using project instructions for portable capabilities.** If the same capability is needed across projects, it belongs in a Skill.

**Using Skills for workspace-specific knowledge.** Company policies and team directories belong in a Project, not a Skill.

## Migration Patterns

### Project-Only → Project + Skills

**When:** Project instructions exceed ~1000 words and include procedures.

Identify procedural content (analysis methods, document generation steps, review frameworks). Extract into Skills. Keep context and requirements in the project. The project gets smaller and more focused; the Skills become reusable.

### Skills-Only → Skills + Project

**When:** You repeatedly paste the same context into conversations that use the same Skills.

Create a project with the shared context (competitor docs, market data, strategy). Skills remain available everywhere. The project provides a workspace where that context is always present.

### Repeated Prompts → Skill

**When:** You catch yourself typing the same instructions across conversations.

Extract the pattern into a Skill. Common candidates: code review standards, analysis frameworks, document templates, data processing pipelines.

### Repeated Prompts → Project Instructions

**When:** The same prompt applies to every conversation in a workspace.

Move it into project instructions. Common candidates: domain-specific approach, team standards, output format requirements.
