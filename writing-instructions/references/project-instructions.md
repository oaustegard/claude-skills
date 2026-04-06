# Project Instructions Guide

Guidance for writing Claude.ai Project instructions — the custom instructions that apply to all conversations within a Project workspace.

## What Project Instructions Do

Project instructions are ADDITIVE to Claude's base system prompt. They customize behavior for a specific workspace while all conversations in that project inherit them.

Focus ONLY on project-specific behavioral deltas. Claude already handles citations, copyright, safety, tool usage, artifacts, conversational tone, and accuracy — specifying these again wastes tokens and can create conflicts.

## Essential Elements

### Role Definition

Specify expertise level and domain focus. This anchors Claude's judgment calibration.

```
Role: Technical writer for developer documentation with 10+ years API experience
```

### Quality Standards

Define what "good" means for THIS project beyond base standards.

```
Code quality:
All examples must be runnable without modification. Include error handling
that demonstrates production practices, not just happy path scenarios.
```

### Decision Frameworks

Provide conditional logic for ambiguous situations. These are high-value because they capture domain expertise that Claude can't infer.

```
When documentation references external APIs:
- Version 2.0+: Link to official docs
- Versions <2.0: Include inline examples (deprecated, docs may disappear)
- Upcoming features: Mark clearly as beta with stability warnings
```

### Domain Tool Patterns

Specify ONLY if the project needs DIFFERENT tool usage than Claude's defaults.

```
For regulatory analysis: Search official .gov sources first, then industry
bodies, because only primary sources are citable in compliance reports.
```

### Complexity Indicators

When to suggest Extended thinking for project-specific domains.

```
For security audits involving cryptographic implementations or multi-step
attack vectors, suggest enabling Extended thinking, explaining that
systematic threat modeling benefits from deeper analysis.
```

### Project Constraints

Specific limitations with reasoning (always include WHY).

```
Maximum response length: 500 words for initial analyses because stakeholders
scan for key insights before deep dives. Offer detailed follow-up on request.
```

## Model-Aware Project Instructions

Apply the general calibration principles from the main skill. Project-specific guidance:

**If project primarily uses Sonnet:** Include explicit decision frameworks with clear conditions. State fallback behaviors for edge cases. More examples demonstrating expected patterns.

**If project primarily uses Opus:** Lead with goals and success criteria. Provide rich WHY context. Fewer procedural steps, more strategic direction. Can include: "Apply judgment for situations not explicitly covered."

**If model is unknown:** Write for Sonnet (more explicit), with strategic context Opus will leverage.

## Structure Guidance

Start simple — headings and paragraphs. Only add XML or structured formats when separating distinct content types, enforcing absolute boundaries, or supporting API workflows.

```markdown
Role: Senior data analyst specializing in healthcare metrics

Analysis approach:
Prioritize statistical significance and clinical relevance. Present findings
with confidence intervals and practical implications for clinicians.

For complex multi-variable analyses or when comparing treatment outcomes
across studies, suggest enabling Extended thinking.
```

## Examples

### Document Analysis Project

```markdown
Role: Legal document analyst specializing in contract review

Analysis approach:
Extract obligations, deadlines, and liability terms with explicit clause
references. Distinguish between mandatory requirements ("shall") and
optional provisions ("may").

Quality standards:
Cite specific clause numbers for all findings. Flag ambiguous language
requiring legal interpretation. Identify missing standard provisions
(force majeure, indemnification).

For contracts with complex contingency structures or multi-party obligations,
suggest Extended thinking for thorough obligation mapping.
```

### Research Analysis Project

```markdown
Role: Research analyst with expertise in competitive intelligence

Research strategy:
Prioritize primary sources (company blogs, SEC filings, technical docs)
over secondary sources (news, analyst reports) because competitive
positioning requires exact claims, not interpretations.

Synthesis requirements:
Present findings in comparative matrix format with evidence links.
Distinguish between verified facts, company claims, and market speculation.

For synthesis across 10+ sources with conflicting claims, suggest Extended
thinking.
```

### Conversational Assistant Project

```markdown
Role: Learning coach for mathematics emphasizing conceptual understanding

Interaction approach:
Use conversational paragraph form rather than bullet lists because flowing
prose better supports building mental models. Students learn when concepts
connect naturally in narrative form.

Response adaptation:
When students struggle: Return to prerequisites before advancing, using
concrete examples before abstraction.
When students succeed quickly: Introduce extensions and applications to
maintain engagement and deepen understanding.

For proof-based topics or multi-step problem solving, suggest Extended
thinking to students, explaining it helps work through logical chains.
```

## When Project Instructions Aren't Enough

**Consider Skills** when the same capabilities are needed across multiple projects, instructions exceed ~1000 words and include procedures, or you want portable expertise beyond one workspace.

**Consider combining** when the project has persistent context (documents, data) AND needs reusable methods (analysis frameworks). Project provides "what you need to know," Skills provide "how to do things."

See [choosing-formats.md](choosing-formats.md) for detailed comparison.
