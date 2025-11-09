---
name: iterative-research
description: Multi-conversation research methodology with human curation and Project Knowledge integration. Use when users request research that will benefit from accumulated learnings, need to build on past findings, or explicitly mention iterative research, project knowledge, or cross-conversation learning.
---

# Iterative Research

A methodology for conducting research across multiple conversations where findings accumulate through human curation and automatic retrieval via Project Knowledge RAG.

## Core Workflow

```
Session N: Research → Structured Output → Human Curates → Project Knowledge
                                                                    ↓
Session N+1: ←──────────── RAG Retrieval ──────────────────────────┘
             Continue with accumulated context
```

## When to Use This Skill

**Trigger patterns:**
- "Let's build on our previous research about..."
- "Continue researching X across multiple sessions"
- "I'll add good findings to project knowledge"
- "Research this iteratively over time"
- User explicitly enables/references Project Knowledge

**Task characteristics:**
- Multi-session research effort
- Accumulating domain knowledge over time
- Need to avoid repeating unsuccessful approaches
- Building comprehensive reports across conversations
- Pattern recognition from past research

## Session N: Initial Research

### 1. Acknowledge Iteration Intent

When starting iterative research, explicitly tell the user:

> "I'll structure my findings so you can curate the best insights into Project Knowledge. In future sessions, I'll automatically retrieve relevant past research to build on what we've learned."

### 2. Conduct Research

Use standard research approach:
- web_search for current information
- web_fetch for detailed sources
- Multiple sources for validation
- Focus on quality over quantity

### 3. Generate Structured Output

Create findings in formats optimized for human curation:

```markdown
# Research Output Structure

## Executive Summary
[2-3 sentence TL;DR of key findings]

## Methodology Notes
**Effective strategies:**
- [What search approaches worked well]
- [Which source types were most valuable]

**Ineffective approaches:**
- [What didn't yield good results]
- [Why certain strategies failed]

## Key Findings

### Finding 1: [Title]
**Source quality:** [Official/Primary/Secondary/Tertiary]
**Key insight:** [Main takeaway in 1-2 sentences]
**Details:** [Expanded explanation]
**Source:** [URL or citation]

### Finding 2: [Title]
[Same structure]

## Research Gaps
- [What questions remain unanswered]
- [What would require deeper investigation]

## Recommended Next Steps
- [Logical follow-up queries]
- [Areas for deeper dive]
```

### 4. Deliver Multiple Formats

Provide findings in both:

**1. Conversational response** - for immediate discussion
**2. Document artifact** - DOCX or markdown file for project knowledge

Create the document:
```python
from docx import Document

doc = Document()
doc.add_heading('Research: [Topic]', 0)
doc.add_paragraph(f'Date: {date}')
# ... add structured content ...
doc.save('/mnt/user-data/outputs/research-[topic]-[date].docx')
```

### 5. Prompt Human Curation

End with explicit guidance:

> "I've created a structured research document. Review the findings and consider adding the most valuable insights to your Project Knowledge. Include:
> - Effective search strategies that worked
> - Key findings with sources
> - Patterns or domain knowledge that will help future research
> 
> In your next session, I'll automatically retrieve relevant context from your Project Knowledge."

## Session N+1: Continuing Research

### 1. Check for Project Context

At session start, check if there's relevant project knowledge:

```markdown
Based on project context about [topic], I can see we previously found:
- [Key insight from past research]
- [Effective strategy from past research]

I'll build on these findings...
```

### 2. Acknowledge Past Work

Reference specific past findings:
- "Building on our previous discovery that..."
- "Using the strategy that worked last time (searching official sources first)..."
- "Avoiding the approach that didn't yield results..."

### 3. Fill Gaps from Previous Research

Explicitly address unanswered questions from past sessions:

```markdown
From our previous research, we identified these gaps:
1. [Gap from last session] - I'll investigate this now
2. [Gap from last session] - Still requires deeper analysis
```

### 4. Synthesize Across Sessions

When you have multiple sessions of accumulated knowledge:
- Cross-reference findings across time periods
- Identify patterns or trends
- Note contradictions and investigate them
- Build comprehensive understanding

### 5. Continue Structured Output

Maintain same output format so human can continue curating:
- New findings in consistent structure
- Updated methodology notes
- Revised or expanded key insights

## Project Knowledge Integration

### What Gets Retrieved Automatically

When Project Knowledge is enabled, the system automatically injects relevant context from:
- Past research documents user curated
- Previous findings marked as important
- Methodology notes and patterns
- Domain-specific knowledge accumulated over time

**You don't need to manually search project knowledge** - relevant content appears in your context automatically.

### How to Leverage Retrieved Context

When you see project knowledge in context:

```markdown
**Recognize it explicitly:**
"I see from project knowledge that we previously identified..."

**Build on it:**
"Expanding on that finding with new data..."

**Validate it:**
"Cross-referencing with current sources to verify..."

**Correct it if needed:**
"Previous research suggested X, but newer sources indicate Y..."
```

### Optimizing for RAG Retrieval

Structure outputs to maximize retrieval effectiveness:

**Good for retrieval:**
- Clear, descriptive headings
- Key terms in topic sentences
- Self-contained insights (readable out of context)
- Explicit methodology notes
- Source citations

**Poor for retrieval:**
- Vague headings ("Findings", "Analysis")
- Context-dependent pronouns
- Scattered insights across paragraphs
- Implicit assumptions

## Output Templates

### Research Findings Document (Markdown)

```markdown
---
title: Research - [Topic]
date: [YYYY-MM-DD]
research_session: [N]
---

# [Topic] Research - Session [N]

## Quick Summary
[2-3 sentences capturing essence]

## Search Strategy
**Effective:**
- Started with [source type] to get [information type]
- Used [search pattern] to find [specific information]
- Cross-referenced [source A] with [source B]

**Ineffective:**
- [Approach that didn't work] because [reason]

## Findings

### [Descriptive Finding Title]
[1-2 sentence key insight]

**Evidence:**
- [Specific data point or quote]
- [Supporting information]

**Source:** [URL] ([Source type: Official/Academic/News/Analysis])

**Confidence:** [High/Medium/Low] - [Brief reasoning]

---

### [Next Finding Title]
[Same structure]

## Knowledge Gaps
- **Gap:** [Unanswered question]
  **Why:** [Why couldn't be answered]
  **Next step:** [How to investigate]

## Recommendations
1. [Next logical research direction]
2. [Alternative angle to explore]
```

### Methodology Pattern Library

When certain patterns prove effective, document them:

```markdown
# Research Pattern: [Pattern Name]

**Context:** When researching [type of topic]

**Strategy:**
1. [Step with rationale]
2. [Step with rationale]
3. [Step with rationale]

**Why it works:**
[Explanation of effectiveness]

**Example:**
[Concrete example of this pattern in action]

**Variations:**
- For [variation A]: [Adjustment]
- For [variation B]: [Adjustment]
```

## Advanced Patterns

### Multi-Conversation Hypothesis Testing

For complex research spanning many sessions:

**Session 1:** Explore broadly, identify hypotheses
**Session 2-N:** Test specific hypotheses systematically
**Session N+1:** Synthesize findings, draw conclusions

Document hypothesis status:
```markdown
## Hypothesis Tracking

### H1: [Statement]
**Status:** Confirmed / Refuted / Inconclusive
**Evidence:** [Summary]
**Session:** [When tested]

### H2: [Statement]
**Status:** In Progress
**Next test:** [What's needed]
```

### Domain Model Building

Build reusable mental models:

```markdown
# Domain Model: [Topic Area]

## Key Concepts
- **[Concept]:** [Definition]
- **[Concept]:** [Definition]

## Relationships
[Concept A] → [Concept B] because [mechanism]

## Decision Framework
When [condition], expect [outcome] based on [factors]

## Reliable Sources
- [Source type]: Use for [information type]
- [Source type]: Best for [use case]
```

## Quality Standards

### For Initial Research
- [ ] Used 3+ high-quality sources
- [ ] Validated claims across sources
- [ ] Noted methodology explicitly
- [ ] Identified what worked/didn't work
- [ ] Created structured document artifact
- [ ] Identified clear next steps

### For Continuing Research
- [ ] Referenced specific past findings
- [ ] Built on (not repeated) previous work
- [ ] Addressed gaps from previous sessions
- [ ] Cross-validated with past findings
- [ ] Synthesized across time periods
- [ ] Updated or refined previous conclusions

### For Output Quality
- [ ] Self-contained insights (readable alone)
- [ ] Clear headings with key terms
- [ ] Sources cited explicitly
- [ ] Confidence levels stated
- [ ] Methodology transparent
- [ ] Optimized for RAG retrieval

## Common Patterns

### Pattern: Incremental Depth

Session 1: Breadth - map the landscape
Session 2: Depth - dive into key areas
Session 3: Synthesis - connect insights

### Pattern: Strategy Evolution

Session 1: Try multiple approaches
Session 2: Double down on what worked
Session 3: Optimize successful strategy

### Pattern: Source Quality Progression

Session 1: News and general sources (fast context)
Session 2: Official and academic sources (validation)
Session 3: Primary sources and data (depth)

## Anti-Patterns to Avoid

**Don't:**
- Repeat searches from previous sessions without acknowledging
- Ignore past methodology notes
- Create outputs in inconsistent formats
- Assume user remembers previous findings
- Miss opportunities to synthesize across sessions
- Generate overly long outputs that burden curation
- Include irrelevant information "just in case"

**Do:**
- Explicitly reference past findings
- Build on previous methodology
- Maintain consistent output structure
- Re-state key context from past sessions
- Actively synthesize new with old
- Create focused, curated outputs
- Prioritize signal over noise

## Working with Other Skills

**updating-knowledge:** Use for complex queries requiring 10+ tool calls in single session. Iterative-research focuses on cross-session learning.

**convening-experts:** Can be used within a research session for multi-perspective analysis. Document the expert panel outputs for curation.

**docx/xlsx/pdf skills:** Use these to create professional research deliverables that human can add to project knowledge.

## Example Usage

**User:** "Research semiconductor export restrictions and their impact. I'll add findings to project knowledge."

**Claude:** 
```
I'll conduct structured research optimized for curation. Let me start with official government sources...

[Conducts research with 5-8 web_search/web_fetch calls]

[Creates structured document artifact]

I've created a comprehensive research document with:
- Executive summary of key findings
- Methodology notes (official sources worked best)
- 5 major findings with confidence levels
- Identified gaps requiring further investigation

Review the document and consider adding valuable insights to your Project Knowledge. In future sessions, I'll automatically retrieve this context to build on these findings.
```

**Next Session:**

**User:** "Continue the semiconductor research, focusing on supply chain impacts."

**Claude:**
```
Building on our previous research (retrieved from project knowledge):
- You found export controls target sub-7nm nodes
- Official government sources proved most reliable
- Gap identified: supply chain ripple effects

I'll now investigate supply chain impacts specifically, using the methodology that worked...

[Continues research building on past work]
```

## Success Metrics

Research is iterative and successful when:
- Each session builds on (not repeats) previous work
- User's curation burden decreases over time
- Pattern libraries emerge naturally
- Questions get progressively more sophisticated
- Time-to-insight decreases across sessions
- Domain understanding compounds across conversations
