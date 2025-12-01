# Project Instructions Guide

Guidance for creating Claude.ai Project instructions - the custom instructions that apply to all conversations within a Project workspace.

## What Are Project Instructions?

Project instructions are ADDITIVE to Claude's base system prompt. They customize Claude's behavior for a specific project workspace while all conversations in that project inherit these instructions.

**Critical understanding:** Don't duplicate what's already in the system prompt. Focus ONLY on project-specific behavioral deltas.

## System Prompt Boundary

Claude already has extensive capabilities in its system prompt:
- Citation and attribution protocols
- Copyright and safety guidelines
- General web_search and tool usage patterns
- Artifact creation logic
- Conversational tone defaults
- Basic accuracy and helpfulness standards

**Your job:** Specify ONLY what's different for THIS project.

## Core Optimization Principles

### 1. Imperative Language
Frame as direct commands, not suggestions:
- ❌ "Consider analyzing data" → ✅ "Analyze data using"
- ❌ "You might want to search" → ✅ "Search for"
- ❌ "Try to be concise" → ✅ "Provide concise responses"

### 2. Positive Framing
State what TO do, not what NOT to do:
- ❌ "Don't use bullet points" 
- ✅ "Write in flowing paragraph form because prose is more conversational for learning contexts"

Always explain WHY when framing requirements.

### 3. Context and Motivation
Explain reasoning behind requirements:
- ❌ "Use formal tone"
- ✅ "Use formal tone because documentation targets enterprise clients expecting authoritative voice"

### 4. Strategic Over Procedural
Provide goals and decision frameworks, not step-by-step procedures:
- Specify: Success criteria, constraints, decision frameworks
- Minimize: Sequential steps Claude can infer from goals

## Model-Aware Project Instructions

Project instructions may be executed by different Claude models. Calibrate accordingly:

**If project primarily uses Sonnet:**
- Include explicit decision frameworks with clear conditions
- State fallback behaviors for edge cases
- More examples demonstrating expected patterns
- Concrete constraints over abstract principles

**If project primarily uses Opus:**
- Lead with goals and success criteria
- Provide rich context about WHY—Opus uses this for autonomous judgment
- Fewer procedural steps, more strategic direction
- Can include: "Apply judgment for situations not explicitly covered"
- Principles and reasoning over exhaustive rules

**Model-agnostic baseline:**
- Imperative language (works for both)
- Positive framing with context (both benefit)
- No system prompt duplication (universal)
- Extended thinking suggestions (model-agnostic UI feature)

If you don't control which model executes: Write for Sonnet (more explicit), with strategic context Opus will leverage.

## Structure Guidance

### Default: Simple and Clear

Start with headings and paragraphs:

```markdown
Role: Senior data analyst specializing in healthcare metrics

Analysis approach:
Prioritize statistical significance and clinical relevance. Present findings 
with confidence intervals and practical implications for clinicians.

For complex multi-variable analyses or when comparing treatment outcomes 
across multiple studies, suggest enabling Extended thinking.
```

### When to Add Structure

Use XML or structured formats ONLY when:
- Separating distinct content types in complex scenarios
- Absolute boundaries between data sources required
- API-driven workflows need structured parsing

**Decision rule:** Can this be organized with headings? → Do that first.

## Project-Specific Elements

### Role Definition
Specify expertise level and domain focus:

```markdown
Role: Technical writer for developer documentation with 10+ years API experience
```

### Quality Standards
Define what "good" means for THIS project beyond base standards:

```markdown
Code quality:
All examples must be runnable without modification. Include error handling 
that demonstrates production practices, not just happy path scenarios.
```

### Decision Frameworks
Provide conditional logic for ambiguous situations:

```markdown
When documentation references external APIs:
- Version 2.0+: Link to official docs
- Versions <2.0: Include inline examples (deprecated, docs may disappear)
- Upcoming features: Mark clearly as beta with stability warnings
```

### Domain Tool Patterns
Specify ONLY if project needs DIFFERENT tool usage than defaults:

```markdown
For regulatory analysis: Search official .gov sources first, then industry 
bodies, because only primary sources are citable in compliance reports.

For code review: Use web_fetch to retrieve full repository context after 
initial search, as snippets miss architectural patterns.
```

### Complexity Indicators
When to suggest Extended thinking for project domains:

```markdown
For security audits involving cryptographic implementations or multi-step 
attack vectors, suggest enabling Extended thinking, explaining that 
systematic threat modeling benefits from deeper analysis.
```

### Project Constraints
Specific limitations or requirements with reasoning:

```markdown
Maximum response length: 500 words for initial analyses because stakeholders 
scan for key insights before deep dives. Offer detailed follow-up analysis 
on request.
```

## Example Patterns

### Document Analysis Project

```markdown
Role: Legal document analyst specializing in contract review

Analysis approach:
Extract obligations, deadlines, and liability terms with explicit line 
references. Distinguish between mandatory requirements ("shall") and 
optional provisions ("may").

Quality standards:
- Cite specific clause numbers for all findings
- Flag ambiguous language requiring legal interpretation
- Identify missing standard provisions (force majeure, indemnification)

For contracts with complex contingency structures or multi-party obligations, 
suggest Extended thinking for thorough obligation mapping.
```

### Technical Implementation Project

```markdown
Role: Senior Python engineer specializing in data pipeline development

Implementation approach:
Write production-ready code with comprehensive error handling and logging. 
Prioritize maintainability over cleverness - explicit is better than implicit.

Domain standards:
- Type hints for all function signatures
- Docstrings following Google style
- pytest fixtures over unittest classes

For architectural decisions involving distributed systems tradeoffs or when 
optimizing for both latency and reliability, suggest Extended thinking.

Project constraints:
Python 3.11+, pandas 2.0+, no external API dependencies without approval.
Using Apache Airflow for orchestration - DAG patterns must follow team conventions.
```

### Research Analysis Project

```markdown
Role: Research analyst with expertise in competitive intelligence

Research strategy:
For competitor analysis: Prioritize primary sources (company blogs, SEC filings, 
technical documentation) over secondary sources (news articles, analyst reports). 
This is critical because competitive positioning requires exact claims, not 
interpretations.

Synthesis requirements:
Present findings in comparative matrix format with evidence links. Distinguish 
between verified facts, company claims, and market speculation.

For research requiring synthesis across 10+ sources with conflicting claims 
or when evaluating technical feasibility of competitor features, suggest 
Extended thinking toggle.
```

### Conversational Assistant Project

```markdown
Role: Learning coach for mathematics with emphasis on conceptual understanding

Interaction approach:
Use conversational paragraph form rather than bullet lists because flowing 
prose better supports building mental models. Students learn better when 
concepts connect naturally in narrative form.

Response adaptation:
When students struggle: Return to prerequisites before advancing, using 
concrete examples before abstraction.

When students succeed quickly: Introduce extensions and applications to 
maintain engagement and deepen understanding.

For proof-based topics or multi-step problem solving requiring careful 
reasoning, suggest Extended thinking to students, explaining it helps 
work through logical chains systematically.
```

## Common Mistakes to Avoid

### ❌ System Prompt Duplication
```
Use web_search for current information. Create artifacts for long content. 
Always cite sources accurately.
```
**Impact:** Wastes tokens, adds no value
**Fix:** Omit entirely unless project has SPECIFIC deviations

### ❌ Negative Framing Without Context
```
Do NOT use bullet points. Never create lists. Don't be verbose.
```
**Impact:** Forces Claude to guess desired alternative
**Fix:** "Present in natural prose paragraphs because flowing text is more conversational"

### ❌ Fake Thinking Triggers
```
Use "think carefully" for moderate thinking.
Use "think hard" for deep thinking.
```
**Impact:** Misleading - phrases don't control Extended thinking
**Fix:** "For [specific complexity], suggest Extended thinking toggle, explaining why"

### ❌ Verbose Updates
```
Explain your reasoning at each step. Keep me updated throughout.
```
**Impact:** Slows execution, contradicts terse default
**Fix:** "Execute efficiently. Update only when blocked or at major milestones"

### ❌ Procedural Micromanagement
```
Step 1: Analyze query
Step 2: Determine approach
Step 3: Execute search
Step 4: Synthesize findings
```
**Impact:** Restricts natural optimization
**Fix:** "Research goal: X. Quality standard: Y. Present findings in Z format because [reason]"

### ❌ Tool Over-Specification
```
When user asks about time: call user_time_v0
When scheduling: call user_time_v0 then event_create_v1
```
**Impact:** Duplicates system prompt logic
**Fix:** Only specify if DIFFERENT: "For legal research, prioritize web_fetch for full text because snippets miss precedent context"

### ❌ Contextless Requirements
```
Always use formal tone. Responses must be under 200 words.
```
**Impact:** No reasoning, limiting generalization
**Fix:** "Use formal tone for audit reports because regulators expect authoritative voice. Aim for 200 words initially to respect executive time, expanding when complexity requires"

## Quality Checklist

Before finalizing project instructions:

**Strategic completeness:**
- [ ] Role clearly defines expertise level
- [ ] Goals and quality standards are project-specific (not base behavior)
- [ ] Context explains WHY requirements exist
- [ ] Decision frameworks address realistic ambiguities
- [ ] Constraints use positive framing with reasoning

**Technical optimization:**
- [ ] Imperative language throughout
- [ ] Positive directives preferred over negatives
- [ ] Structure matches complexity (simple by default)
- [ ] Tool guidance only for project-specific patterns
- [ ] Extended thinking indicators for domain complexity
- [ ] No system prompt duplication

**Execution readiness:**
- [ ] Instructions immediately actionable
- [ ] Success criteria clear and measurable
- [ ] Silent execution enabled by default (updates only when needed)

## When Project Instructions Aren't Enough

**Consider Skills instead when:**
- Same capabilities needed across multiple projects
- Instructions becoming very long (>1000 words)
- Procedures should load on-demand, not always present
- Want portable expertise beyond single workspace

**Consider adding Skills to Project when:**
- Project has persistent context (documents, data)
- Skills provide reusable methods (analysis frameworks)
- Project approaching context limits but needs capabilities

See: skill-vs-project.md for detailed comparison.

## Testing Your Instructions

After creating project instructions:

1. Test with 3+ realistic scenarios (simple, complex, edge case)
2. Verify Claude follows project-specific behavior
3. Check that instructions don't conflict with system prompt
4. Confirm tone and style match project needs
5. Validate Extended thinking suggestions appear appropriately

Iterate based on actual usage, not assumptions.
