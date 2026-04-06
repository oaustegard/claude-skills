# Standalone Prompts Guide

Crafting effective one-off prompts — the natural language instructions you give Claude in conversation.

## When to Use Prompts

Prompts are ephemeral, conversational, and ad-hoc. Use them for one-off requests, conversational refinement, and experiments. If you find yourself reusing the same prompt repeatedly, consider converting to a Skill or Project instruction (see [choosing-formats.md](choosing-formats.md)).

## Core Techniques

All writing principles from the main skill apply here. These additional techniques are prompt-specific.

### Be Explicit About Output

Tell Claude what the output should include, not just what to work on.

**Vague:** "Create an analytics dashboard"
**Explicit:** "Create an analytics dashboard. Include as many relevant features and interactions as possible. Go beyond the basics to create a fully-featured implementation."

Lead with action verbs. Skip preambles. State quality and depth expectations.

### Be Specific With Constraints

Structure instructions with explicit guidelines when the default would be too broad.

**Vague:** "Create a meal plan for a Mediterranean diet"
**Specific:** "Design a Mediterranean diet meal plan for pre-diabetic management. 1,800 calories daily, emphasis on low glycemic foods. List breakfast, lunch, dinner, and one snack with complete nutritional breakdowns."

What makes a prompt specific: clear constraints (word count, format, timeline), relevant context (audience, goal), desired output structure, and requirements or restrictions.

### Use Examples Carefully

Examples demonstrate desired format or style — but remember that Claude 4.x learns ALL patterns from examples, including unintended ones.

**When to use:** Desired format is easier to show than describe, you need specific tone or style, task involves subtle conventions, or simpler instructions haven't worked.

**When to skip:** Instructions are clear without them, task is straightforward, or you cannot create examples that perfectly align with ALL requirements.

### Give Permission for Uncertainty

Allow Claude to say "I don't know" rather than speculate.

"Analyze this financial data and identify trends. If the data is insufficient to draw conclusions, say so rather than speculating."

This reduces hallucinations and increases reliability.

### Prefill the Response

Guide format by starting Claude's response pattern.

For JSON: "Extract the name and price into JSON. Begin your response with: {"
For skipping preambles: "Analyze this code for security issues. Begin directly with the first vulnerability:"

### Control Format Positively

Frame formatting preferences as what TO do. Your prompt's own formatting may influence Claude's response style — if you want minimal markdown, use minimal markdown in your prompt.

```
When writing explanations, use clear flowing prose with complete paragraphs.
Reserve markdown for inline code, code blocks, and simple headings.
Present information in sentences rather than bullet lists unless presenting
truly discrete items.
```

## Complexity Scaling

Match prompt investment to task difficulty.

**Simple (1 tool call):** "Who won the NBA finals last year?" — Concise, single fact.

**Medium (3–5 tool calls):** "Compare pricing and features of top 3 project management tools for remote teams" — Structured with clear criteria.

**Complex (5–10+ tool calls):** "Research semiconductor export restrictions and analyze impact on our tech portfolio. Consider geopolitical factors, supply chain dependencies, and alternative suppliers." — Comprehensive context with multi-part analysis.

**Model selection for prompts:**
- Sonnet: Best for routine, well-defined tasks. Add structure and examples for complex requests.
- Opus: Best for nuanced reasoning, creative work, or ambiguous tasks requiring judgment. Can work from goals with less procedural guidance.

## Example Patterns

### Research Request
```
Research recent developments in quantum computing error correction.
Focus on breakthrough announcements from major labs, new error correction
architectures, and practical implications for near-term quantum advantage.

Present findings chronologically with source links. If research is limited
or conflicting, acknowledge gaps rather than speculating.
```

### Analysis Request
```
Analyze this customer feedback data (attached CSV) and identify:
top 3 pain points by frequency and severity, feature requests mentioned
more than 5 times, and sentiment trend over time.

Present as brief executive summary (200 words) followed by detailed
breakdown with specific examples. If data quality prevents confident
analysis, specify what's missing.
```

### Creative Writing Request
```
Write a 500-word short story about an AI discovering it's in a simulation.
Second-person perspective. Twist ending that reframes the narrative.

Tone: Philosophical but accessible. If the premise feels too common,
suggest alternative angles before writing.
```

## Troubleshooting

**Response too generic:** Add specificity, examples, or explicit depth expectations.
**Misses the point:** Provide more context about your actual goal and why you're asking.
**Inconsistent format:** Add perfect examples or use prefilling.
**Task too complex:** Break into multiple prompts or enable Extended thinking.
**Unnecessary preambles:** Use prefilling or "Skip the preamble and answer directly."
**Makes things up:** Give permission to say "I don't know."
**Suggests instead of implementing:** Use imperative language — "Change this" not "Can you suggest changes?"

## When to Convert

**→ Skill:** You use the same prompt repeatedly (code review standards, analysis frameworks, document templates).
**→ Project instructions:** The prompt applies to ALL conversations in a workspace (domain-specific approach, team standards).
**→ Keep as prompt:** One-off request, unique context, experimenting, conversational refinement.
