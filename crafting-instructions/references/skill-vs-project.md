# Skills vs Projects: Detailed Comparison

Comprehensive guide to understanding when to use Skills versus Project instructions, and when to combine them.

## Core Distinction

**Projects:** "Here's what you need to know" (declarative knowledge)
- Static reference material always loaded
- Background knowledge for specific initiative
- Team workspace with shared context

**Skills:** "Here's how to do things" (procedural knowledge)
- Dynamic expertise loading on-demand
- Portable capabilities across conversations
- Methods that work everywhere

## When to Augment Projects with Skills

### Scenario 1: Reference Material + Capabilities

You have extensive domain knowledge but need consistent execution methods.

**Example:**
- **Project:** "Legal Contract Review"
  - Contains: 50+ template contracts, past negotiations, company policies
- **Add Skills:** 
  - `contract-analysis` - How to structure reviews systematically
  - `redline-standards` - How to mark changes consistently
  - `risk-assessment` - How to evaluate clause liability

**Why both?** Project provides "what" (your contracts and policies). Skills provide "how" (review procedures). Without Skills, Claude infers methodology each time. With Skills, consistent frameworks apply automatically.

### Scenario 2: Large Context + Selective Capabilities

Project approaches context limits but needs specialized capabilities.

**Example:**
- **Project:** "Product Development"
  - Contains: Specs, user research, competitive analysis (approaching 200K tokens)
- **Add Skills:**
  - `technical-writing` - Documentation generation
  - `user-feedback-analysis` - Systematic insight extraction
  - `api-documentation` - Standardized API docs

**Why both?** Skills use progressive disclosure—they only load when relevant, preserving project context window for knowledge rather than procedures.

### Scenario 3: Cross-Project Capabilities

Multiple projects need same execution patterns.

**Example:**
- **Projects:** "Client A Implementation", "Client B Implementation", "Client C Implementation"
- **Add Skills:**
  - `deployment-checklist` - Consistent deployment procedures
  - `security-audit` - Standard security reviews
  - `documentation-generator` - Uniform documentation

**Why Skills here?** Rather than duplicating procedures in each project's instructions, Skills provide portable capabilities across all projects.

## When to Augment Skills with Projects

### Scenario 1: Skill Needs Context Boundaries

General-purpose Skill needs scoping to specific reference material.

**Example:**
- **Skill:** `competitive-analysis` - General framework for analyzing competitors
- **Add Project:** "Q4 Market Intelligence"
  - Contains: Recent industry reports, your product roadmap, target market data

**Why both?** Skill provides methodology that works for any competitive analysis. Project provides specific context and reference materials for THIS quarter's analysis.

### Scenario 2: Team Collaboration on Specialized Tasks

Multiple team members need shared knowledge while using Skills.

**Example:**
- **Skills:** `brand-guidelines`, `content-review`, `seo-optimization`
- **Add Project:** "Website Redesign 2025"
  - Contains: Design mockups, copy drafts, stakeholder feedback
  - Team shared workspace

**Why both?** Skills ensure consistent execution across team. Project provides shared context and conversation history for alignment.

### Scenario 3: Initiative-Specific Data + Reusable Methods

Time-bound work with specific data needs but proven methods.

**Example:**
- **Skills:** `financial-modeling`, `data-visualization`, `risk-analysis`
- **Add Project:** "2025 Budget Planning"
  - Contains: Historical data, department requests, economic forecasts

**Why both?** Skills provide proven analytical frameworks. Project contains this year's specific data and maintains conversation continuity throughout budget cycle.

## Decision Framework

```
Does capability need to persist across multiple projects/conversations?
├─ YES → Skill
└─ NO → Project custom instructions

Does knowledge need to be available for every conversation in workspace?
├─ YES → Project knowledge base
└─ NO → Skill (loads on-demand)

Is the "thing" primarily reference material or procedural knowledge?
├─ Reference → Project
└─ Procedure → Skill

Are you approaching context limits?
├─ YES → Consider Skills for procedures (progressive disclosure saves tokens)
└─ NO → Either works, choose based on reusability needs

Do multiple people need this in a shared workspace?
├─ YES → Project (team collaboration)
└─ NO → Either works based on other factors

Is this knowledge organization-wide or project-specific?
├─ Organization-wide → Skill
└─ Project-specific → Project
```

## Detailed Comparison Table

| Aspect | Projects | Skills |
|--------|----------|--------|
| **Scope** | Single workspace | All conversations |
| **Loading** | Always present | On-demand (when relevant) |
| **Content type** | Reference material, context | Procedures, methods, code |
| **Token usage** | Full context always loaded | Progressive disclosure |
| **Collaboration** | Yes (Team/Enterprise plans) | Individual (unless org-deployed) |
| **Persistence** | Workspace conversations | Across all contexts |
| **Best for** | "What you need to know" | "How to do things" |
| **Updates** | Edit project knowledge | Update skill files |
| **Portability** | Workspace-specific | Portable everywhere |
| **Size limit** | 200K context (10x with RAG) | ~5K per skill typical |
| **Team sharing** | Built-in | Via distribution |

## Real-World Examples

### Example 1: Research Agent

**Setup:**
```
Project: "Competitive Intelligence"
├─ Knowledge: Industry reports, competitor docs, customer feedback
└─ Instructions: "Analyze competitors through lens of our product strategy"

Skills:
├─ competitive-analysis (framework for systematic evaluation)
└─ gdrive-navigation (how to efficiently search company Drive)
```

**Why both?**
- Project: Provides "what we know about our market"
- Skills: Provide "how to analyze competitors systematically"
- Result: Contextually aware + methodologically consistent research agent

### Example 2: Development Team

**Setup:**
```
Project: "Backend API Development"
├─ Knowledge: API specs, database schema, integration requirements
└─ Instructions: "Follow RESTful principles, document all endpoints"

Skills:
├─ python-best-practices (coding standards)
├─ api-documentation (how to document endpoints)
└─ security-review (how to audit for vulnerabilities)
```

**Why both?**
- Project: Specific API requirements and team context
- Skills: Reusable development practices across all projects
- Result: Project-specific implementation with consistent quality standards

### Example 3: Content Creation

**Setup:**
```
Project: "Marketing Campaign Q4"
├─ Knowledge: Brand guidelines, campaign brief, target personas
└─ Instructions: "All content should emphasize sustainability angle"

Skills:
├─ brand-voice (how to match company tone)
├─ seo-optimization (how to optimize for search)
└─ content-calendar (how to plan publication schedule)
```

**Why both?**
- Project: Campaign-specific messaging and context
- Skills: Portable content creation capabilities
- Result: On-brand, optimized content for this campaign

## Anti-Patterns to Avoid

### ❌ Duplicating Procedures Across Projects

**Bad:**
```
Project A Instructions: "When analyzing data, first clean, then normalize, 
then apply statistical tests..."

Project B Instructions: "When analyzing data, first clean, then normalize, 
then apply statistical tests..."

Project C Instructions: "When analyzing data, first clean, then normalize, 
then apply statistical tests..."
```

**Good:**
```
Skill: data-analysis
└─ Contains systematic analysis procedures

Projects A, B, C:
└─ Contain project-specific data and context
```

### ❌ Putting Reference Material in Skills

**Bad:**
```
Skill: q4-market-data
└─ Contains: Q4 competitor reports, market trends, customer data
```

**Good:**
```
Project: "Q4 Market Intelligence"
└─ Contains: Q4 reports, trends, customer data

Skill: competitive-analysis
└─ Contains: How to analyze market data systematically
```

### ❌ Project Instructions for Cross-Project Capabilities

**Bad:**
```
Project: "Client A Implementation"
Instructions: 
- Security review checklist: [10 steps]
- Deployment procedure: [15 steps]
- Documentation format: [standards]

[Repeat in every client project...]
```

**Good:**
```
Skills:
├─ security-review (reusable across all clients)
├─ deployment-procedure (consistent deployment)
└─ documentation-standards (uniform docs)

Projects: Client A, B, C
└─ Contain client-specific requirements only
```

### ❌ Skill for Workspace-Specific Knowledge

**Bad:**
```
Skill: team-onboarding-materials
└─ Contains: Company policies, team directory, internal tools
```

**Good:**
```
Project: "Team Onboarding"
└─ Contains: Policies, directory, tool access
    (Shared workspace for new hires)
```

## Combined Approach Benefits

Using Projects AND Skills together creates powerful workflows:

**Benefit 1: Separation of Concerns**
- Project: Domain knowledge and context
- Skills: Methods and procedures
- Result: Clean separation, easy to update each independently

**Benefit 2: Token Efficiency**
- Project: Always-relevant context
- Skills: Load only when needed
- Result: Maximum context window utilization

**Benefit 3: Reusability**
- Project: Initiative-specific
- Skills: Organization-wide
- Result: Build once, use everywhere

**Benefit 4: Collaboration**
- Project: Team shared workspace
- Skills: Individual or org-deployed capabilities
- Result: Team context + portable expertise

**Benefit 5: Evolution**
- Project: Update as initiative evolves
- Skills: Refine as methods improve
- Result: Both improve independently

## Migration Patterns

### From Project-Only to Project + Skills

**When:** Project instructions exceed ~1000 words and include procedures

**Process:**
1. Identify procedural content in project instructions
2. Extract procedures into Skills
3. Keep context and requirements in project
4. Test that capabilities still work
5. Iterate based on usage

**Example:**
```
Before: Project "Data Science"
├─ 2000 words of instructions
    ├─ 60%: How to clean data, run analyses, create visualizations
    └─ 40%: Project goals, data sources, quality standards

After: Project "Data Science"
├─ 800 words: Goals, data sources, quality standards

+ Skills:
  ├─ data-cleaning (extracted procedures)
  ├─ statistical-analysis (extracted methods)
  └─ data-visualization (extracted techniques)
```

### From Skills-Only to Skills + Project

**When:** Using same Skills repeatedly on related work

**Process:**
1. Identify common context needed across conversations
2. Create project with that context
3. Keep Skills for capabilities
4. Use project for related conversations
5. Skills still work everywhere else

**Example:**
```
Before: Skills
├─ competitive-analysis
└─ market-research

Repeatedly pasting: competitor docs, market data, strategy docs

After: Project "Market Intelligence"
├─ Competitor docs, market data, strategy
└─ Uses competitive-analysis and market-research skills

Skills remain available everywhere
Project provides workspace for market-related work
```

## When Neither Is Right

### Use Standalone Prompts When:
- One-off request with unique context
- Experimenting with approaches
- Task doesn't need persistence
- No reuse expected

### Use Other Tools When:
- Need data access → MCP
- Need specialized agents → Subagents (Claude Code)
- Need API integration → API with custom instructions
- Need organization-wide deployment → Enterprise features

## Summary: Quick Decision Guide

**Choose Project when:**
- ✓ Need persistent context for workspace
- ✓ Team collaboration required
- ✓ Background knowledge for initiative
- ✓ Workspace-scoped behavior

**Choose Skill when:**
- ✓ Capability needed across contexts
- ✓ Procedural knowledge to teach
- ✓ Want automatic activation
- ✓ Portable expertise desired

**Choose Both when:**
- ✓ Have persistent context AND reusable methods
- ✓ Large knowledge base AND specialized procedures
- ✓ Team workspace AND consistent capabilities
- ✓ Want maximum efficiency and flexibility

**Choose Neither when:**
- ✓ One-off request
- ✓ Simple prompt suffices
- ✓ No persistence needed
- ✓ Experimenting with approaches
