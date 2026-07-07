# Standalone Prompts Guide

Guidance for crafting effective standalone prompts - the one-off instructions you give Claude in conversation.

## What Are Standalone Prompts?

Prompts are natural language instructions you provide to Claude in the moment. They're:
- **Ephemeral** - Don't persist beyond the conversation
- **Conversational** - Can be refined through back-and-forth
- **Reactive** - Provide immediate context and direction
- **Ad-hoc** - For one-time requests without need for reuse

## Core Techniques

### 1. Be Explicit and Clear

Tell Claude exactly what you want without ambiguity:

**Vague:** "Create an analytics dashboard"

**Explicit:** "Create an analytics dashboard. Include as many relevant features and interactions as possible. Go beyond the basics to create a fully-featured implementation."

The explicit version signals comprehensive output and sets quality expectations.

**Best practices:**
- Lead with direct action verbs: "Write," "Analyze," "Generate," "Create"
- Skip preambles, get straight to the request
- State what you want output to include, not just what to work on
- Be specific about quality and depth expectations

### 2. Provide Context and Motivation

Explain WHY things matter:

**Less effective:** "NEVER use bullet points"

**More effective:** "I prefer responses in natural paragraph form rather than bullet points because I find flowing prose easier to read and more conversational. Bullet points feel too formal and list-like for my casual learning style."

Explaining reasoning helps Claude understand your goals and make better decisions about related choices.

**When to provide context:**
- Explaining purpose or audience for output
- Clarifying why constraints exist
- Describing how output will be used
- Indicating what problem you're solving

### 3. Be Specific

Structure instructions with explicit guidelines:

**Vague:** "Create a meal plan for a Mediterranean diet"

**Specific:** "Design a Mediterranean diet meal plan for pre-diabetic management. 1,800 calories daily, emphasis on low glycemic foods. List breakfast, lunch, dinner, and one snack with complete nutritional breakdowns."

**What makes a prompt specific:**
- Clear constraints (word count, format, timeline)
- Relevant context (audience, goal)
- Desired output structure (table, list, paragraph)
- Requirements or restrictions (dietary needs, budget, technical constraints)

### 4. Use Examples (When Helpful)

Examples demonstrate desired output format or style:

**Without example:** "Summarize this article"

**With example:**
```
Here's the summary style I want:

Article: [link to article about AI regulation]
Summary: EU passes comprehensive AI Act targeting high-risk systems. 
Key provisions include transparency requirements and human oversight 
mandates. Takes effect 2026.

Now summarize this article in the same style: [your article link]
```

**When to use examples:**
- Desired format is easier to show than describe
- You need specific tone or style
- Task involves subtle patterns or conventions
- Simple instructions haven't produced consistent results

**When to skip examples:**
- Instructions are clear without them
- Task is straightforward and well-understood
- You cannot create examples that perfectly align with all requirements

**CRITICAL for Claude 4.x:** Examples teach ALL patterns. If your example uses bullet points but you want prose, Claude will use bullets. Ensure every aspect of examples demonstrates desired behavior.

### 5. Give Permission to Express Uncertainty

Allow Claude to say "I don't know" rather than guess:

**Example:** "Analyze this financial data and identify trends. If the data is insufficient to draw conclusions, say so rather than speculating."

This reduces hallucinations and increases reliability.

## Complexity Scaling

Match prompt complexity to task needs:

**Simple task (1 tool call):** "Who won the NBA finals last year?"
→ Concise prompt, single fact

**Medium task (3-5 tool calls):** "Compare pricing and features of top 3 project management tools for remote teams"
→ Structured prompt with clear criteria

**Complex task (5-10+ tool calls):** "Research semiconductor export restrictions and analyze impact on our tech portfolio. Consider geopolitical factors, supply chain dependencies, and alternative suppliers."
→ Comprehensive prompt with context and multi-part analysis

**Model selection for prompts:**
- **Sonnet:** Best for routine, well-defined tasks. Add explicit structure, constraints, and examples for complex requests.
- **Opus:** Best for nuanced reasoning, creative work, or ambiguous tasks requiring judgment. Can work from goals with less procedural guidance. Worth the latency/cost tradeoff when task benefits from deeper reasoning.

## Advanced Techniques

### Prefill Claude's Response

Guide format by starting Claude's response:

**For JSON output:**
```
Extract the name and price from this product description into JSON.

Begin your response with: {
```

Claude will continue from the opening brace, outputting only valid JSON.

**For skipping preambles:**
```
Analyze this code for security issues. Begin directly with the first 
vulnerability you find:

1. Vulnerability:
```

### Chain of Thought (When Needed)

For complex reasoning, request step-by-step thinking:

**Basic:** "Think step-by-step before answering"

**Guided:** "First, identify key themes in the document. Then, analyze how these themes relate to the research question. Finally, synthesize your findings."

**Structured:** "Think through your analysis in <thinking> tags. Then provide your answer in <answer> tags."

**Note:** For Claude.ai users with Extended thinking available, enabling that feature is generally better than manual chain of thought prompting.

### Control Output Format

**Frame positively:** Tell Claude what TO do, not what NOT to do

❌ "Do not use markdown"
✅ "Write in plain paragraph form with natural text flow"

**Match your prompt style:** Your prompt's formatting may influence Claude's response style. If you want minimal markdown, use minimal markdown in your prompt.

**Be explicit about preferences:**
```
When writing explanations, use clear flowing prose with complete paragraphs. 
Reserve markdown primarily for inline code, code blocks, and simple headings.

Present information naturally in sentences rather than using bullet lists 
unless you're presenting truly discrete items where a list format is the 
best option.
```

## Example Patterns

### Research Request
```
Research recent developments in quantum computing error correction. 
Focus on:
- Breakthrough announcements from major labs (Google, IBM, academic institutions)
- New error correction codes or architectures
- Practical implications for near-term quantum advantage

Present findings chronologically with source links. If research is limited 
or conflicting, acknowledge gaps rather than speculating.
```

### Code Review Request
```
Review this Python function for:
1. Security vulnerabilities (SQL injection, XSS, input validation)
2. Performance issues (O(n²) operations, redundant computations)
3. Code quality (readability, error handling, edge cases)

For each issue found:
- Severity level (Critical/High/Medium/Low)
- Specific line numbers
- Explanation of the problem
- Recommended fix with code example

If no issues in a category, explicitly state "No [category] issues found."
```

### Creative Writing Request
```
Write a 500-word short story about an AI that discovers it's living in a 
simulation. Use second-person perspective ("You wake up..."). Create a 
twist ending that reframes the entire narrative.

Tone: Philosophical but accessible, thought-provoking without being preachy.

If the premise feels too common to create something original, suggest 
alternative angles before writing.
```

### Analysis Request
```
Analyze this customer feedback data (attached CSV) and identify:

1. Top 3 pain points (by frequency and severity)
2. Feature requests mentioned more than 5 times
3. Sentiment trend over time (positive/negative/neutral)

Present findings in a brief executive summary (200 words) followed by 
detailed breakdown with specific examples and quote excerpts.

If data quality issues prevent confident analysis, specify what's missing 
or ambiguous.
```

## Common Mistakes to Avoid

### ❌ Assuming Claude Reads Minds
"Make it better" → Better how? What specifically needs improvement?

### ❌ Leaving Things Ambiguous
"Create a report" → What kind? For whom? What should it include?

### ❌ Over-Engineering Simple Requests
"What's the capital of France?" → Just ask directly, don't add complexity

### ❌ Using Examples That Contradict Instructions
Instruction: "No bullet points"
Example: [shows bullet points]
→ Claude will use bullets (examples teach all patterns)

### ❌ Forgetting to Scale to Complexity
Simple question with 10 paragraphs of instructions → Unnecessary overhead
Complex task with vague one-liner → Won't get quality results

## When to Convert Prompts to Other Formats

### Convert to Skill when:
You find yourself using the same prompt repeatedly:
- "Review this code following our security standards"
- "Format this analysis as executive summary + findings + recommendations"
- "Extract keywords from this document using YAKE algorithm"

### Convert to Project Instructions when:
Prompt applies to ALL conversations in a workspace:
- "For this product launch project, analyze everything through competitive lens"
- "All financial analysis should emphasize risk-adjusted returns"
- "In this learning project, use Socratic method rather than direct answers"

### Keep as Prompt when:
- One-off request with unique context
- Conversational refinement ("make that more formal")
- Ad-hoc instructions specific to this moment
- Experimenting with different approaches

## Troubleshooting

**Problem:** Response is too generic
**Solution:** Add specificity, examples, or explicit requests for comprehensive output

**Problem:** Response misses the point
**Solution:** Provide more context about your actual goal and why you're asking

**Problem:** Format is inconsistent
**Solution:** Add examples (with perfect alignment to requirements) or use prefilling

**Problem:** Task is too complex, results unreliable
**Solution:** Break into multiple prompts (chaining) or enable Extended thinking

**Problem:** Claude includes unnecessary preambles
**Solution:** Use prefilling or explicitly request: "Skip the preamble and answer directly"

**Problem:** Claude makes up information
**Solution:** Give explicit permission to say "I don't know" when uncertain

**Problem:** Claude suggests changes when you wanted implementation
**Solution:** Use imperative language: "Change this function" not "Can you suggest changes?"

## Quality Checklist

Before sending your prompt:

- [ ] Is my request clear and explicit?
- [ ] Have I provided relevant context?
- [ ] Are my requirements specific enough?
- [ ] If using examples, do they perfectly demonstrate desired behavior?
- [ ] Have I given permission to express uncertainty?
- [ ] Does prompt complexity match task complexity?
- [ ] Am I using positive directives (what to do) over negatives (what not to do)?

## Additional Resources

- Anthropic prompt engineering documentation: https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview
- Interactive tutorial: https://github.com/anthropics/prompt-eng-interactive-tutorial
- Prompt library: https://docs.claude.com/en/prompt-library/library
