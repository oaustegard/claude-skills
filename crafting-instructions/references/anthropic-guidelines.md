# Latest Anthropic Prompt Engineering Guidelines

Official best practices from Anthropic's prompt engineering guide (November 2024) for Claude 4.x models.

## Core Principles

### 1. Be Explicit and Clear

Modern AI models respond exceptionally well to clear, explicit instructions. Don't assume the model will infer what you want—state it directly.

**The key principle:** Tell the model exactly what you want to see. If you want comprehensive output, ask for it. If you want specific features, list them.

**Example:**
```
Vague: "Create an analytics dashboard"

Explicit: "Create an analytics dashboard. Include as many relevant features 
and interactions as possible. Go beyond the basics to create a fully-featured 
implementation."
```

**Best practices:**
- Lead with direct action verbs: "Write," "Analyze," "Generate," "Create"
- Skip preambles and get straight to the request
- State what you want the output to include, not just what to work on
- Be specific about quality and depth expectations

### 2. Provide Context and Motivation

Explaining WHY something matters helps AI models better understand your goals and deliver more targeted responses.

**Example:**
```
Less effective: "NEVER use bullet points"

More effective: "I prefer responses in natural paragraph form rather than 
bullet points because I find flowing prose easier to read and more 
conversational. Bullet points feel too formal and list-like for my casual 
learning style."
```

The second version helps the model understand the reasoning, which allows it to make better decisions about related formatting choices.

**When to provide context:**
- Explaining the purpose or audience for the output
- Clarifying why certain constraints exist
- Describing how the output will be used
- Indicating what problem you're trying to solve

### 3. Be Specific

Specificity means structuring instructions with explicit guidelines and requirements.

**Example:**
```
Vague: "Create a meal plan for a Mediterranean diet"

Specific: "Design a Mediterranean diet meal plan for pre-diabetic management. 
1,800 calories daily, emphasis on low glycemic foods. List breakfast, lunch, 
dinner, and one snack with complete nutritional breakdowns."
```

**What makes a prompt specific:**
- Clear constraints (word count, format, timeline)
- Relevant context (who's the audience, what's the goal)
- Desired output structure (table, list, paragraph)
- Any requirements or restrictions (dietary needs, budget limits, technical constraints)

### 4. Use Examples Judiciously

Examples aren't always necessary, but they shine when explaining concepts or demonstrating specific formats.

**Important note for Claude 4.x:** These models pay very close attention to details in examples. Ensure your examples align with behaviors you want to encourage and minimize patterns you want to avoid.

**When to use examples:**
- The desired format is easier to show than describe
- You need a specific tone or style
- The task involves subtle patterns or conventions
- Simple instructions haven't produced consistent results

**When to keep them minimal:**
- Instructions are clear and complete without them
- You cannot construct example with perfect alignment
- Task is straightforward and well-understood

**Pro tip:** Start with one example (one-shot). Only add more (few-shot) if output still doesn't match needs.

### 5. Give Permission to Express Uncertainty

Give AI explicit permission to express uncertainty rather than guessing.

**Example:** "Analyze this financial data and identify trends. If the data is insufficient to draw conclusions, say so rather than speculating."

This simple addition makes responses more trustworthy by allowing the model to acknowledge limitations.

## Advanced Techniques

### Prefill the AI's Response

Prefilling lets you start the AI's response for it, guiding format, tone, or structure.

**When to use prefilling:**
- You need AI to output JSON, XML, or other structured formats
- You want to skip conversational preambles
- You need to maintain a specific voice or character
- You want to control how AI begins its response

**Example (API usage):**
```python
messages=[
    {"role": "user", "content": "Extract name and price as JSON."},
    {"role": "assistant", "content": "{"}
]
```

The AI will continue from the opening brace, outputting only valid JSON.

**In chat interfaces:** Be very explicit: "Output only valid JSON with no preamble. Begin your response with an opening brace."

### Chain of Thought Prompting

Chain of thought (CoT) involves requesting step-by-step reasoning before answering.

**Modern approach:** Claude offers Extended Thinking feature that automates structured reasoning. When available, Extended Thinking is generally preferable to manual CoT prompting.

**When to use manual CoT:**
- Extended Thinking isn't available
- You need transparent reasoning you can review
- Task requires multiple analytical steps
- You want to ensure AI considers specific factors

**Implementations:**

**Basic:** "Think step-by-step before you write the email."

**Guided:** "First, think through what messaging might appeal to this donor. Then, consider which aspects would resonate. Finally, write the personalized email."

**Structured:** "Think in <thinking> tags. Then write in <email> tags."

### Control Output Format

**Tell AI what TO do, not what NOT to do:**
```
Instead of: "Do not use markdown in your response"
Try: "Your response should be composed of smoothly flowing prose paragraphs"
```

**Match your prompt style to desired output:**
The formatting style used in your prompt may influence AI's response style.

**Be explicit about formatting preferences:**
```
When writing reports or analyses, write in clear, flowing prose using 
complete paragraphs. Use standard paragraph breaks for organization. 
Reserve markdown primarily for inline code, code blocks, and simple headings.

DO NOT use ordered lists or unordered lists unless presenting truly discrete 
items where a list format is the best option, or the user explicitly requests 
a list.
```

### Prompt Chaining

Chaining breaks complex tasks into smaller sequential steps with separate prompts.

**Example:**
1. First prompt: "Summarize this medical paper"
2. Second prompt: "Review the summary for accuracy and completeness"
3. Third prompt: "Improve the summary based on this feedback"

**When to use:**
- Complex request needs breaking into steps
- Need iterative refinement
- Multi-stage analysis
- Intermediate validation adds value

**Trade-offs:** Increases latency but dramatically improves accuracy for complex tasks.

## Techniques for Specific Contexts

### XML Tags for Structure

**Modern status:** Less necessary with Claude 4.x but still useful in specific situations.

**When XML tags help:**
- Extremely complex prompts mixing multiple content types
- Need absolute certainty about content boundaries
- Working with older model versions
- API-driven workflows requiring structured parsing

**Modern alternative:** Clear headings, whitespace, and explicit language work just as well with less overhead.

### Role Prompting

**Modern status:** Sophisticated models often don't need heavy-handed role prompting.

**When role prompting helps:**
- Need consistent tone across many outputs
- Building application requiring specific persona
- Want domain expertise framing for complex topics

**Important caveat:** Don't over-constrain the role. "You are a helpful assistant" often better than "You are a world-renowned expert who only speaks in technical jargon."

**Modern alternative:** "Analyze this investment portfolio, focusing on risk tolerance and long-term growth potential" rather than assigning elaborate role.

## Choosing the Right Techniques

**Start here:**
1. Is your request clear and explicit? If no, work on clarity first
2. Is the task simple? Use core techniques only
3. Does task require specific formatting? Use examples or prefilling
4. Is task complex? Consider breaking it down (chaining)
5. Does it need reasoning? Use Extended Thinking or chain of thought

**Technique selection:**

| Task Type | Best Techniques |
|-----------|----------------|
| Simple factual | Be clear, be specific |
| Format-specific | Examples, prefilling |
| Complex analysis | Chain of thought, Extended Thinking |
| Multi-step | Prompt chaining |
| Iterative | Chaining with refinement |

## Troubleshooting Common Issues

**Response is too generic** → Add specificity, examples, or explicit requests for comprehensive output

**Response is off-topic** → Be more explicit about actual goal, provide context

**Format is inconsistent** → Add examples (few-shot) or use prefilling

**Task too complex, unreliable results** → Break into multiple prompts (chaining)

**AI includes unnecessary preambles** → Use prefilling or explicitly request: "Skip preamble, answer directly"

**AI makes up information** → Explicitly give permission to say "I don't know"

**AI suggests changes when you wanted implementation** → Be explicit: "Change this function" not "Can you suggest changes?"

## Common Mistakes to Avoid

**Don't over-engineer:** Longer, more complex prompts are NOT always better

**Don't ignore basics:** Advanced techniques won't help if core prompt is unclear

**Don't assume AI reads minds:** Be specific about what you want

**Don't use every technique at once:** Select techniques that address your specific challenge

**Don't forget to iterate:** First prompt rarely works perfectly

**Don't rely on outdated techniques:** XML tags and heavy role prompting less necessary with modern models

## Working with Long Content

### Context Awareness Improvements

Claude 4.x models have significantly improved context awareness capabilities that help address historical "lost-in-the-middle" issues.

**Why task-splitting still helps:** Even with improvements, breaking large tasks into smaller, discrete chunks remains valuable—not because of context limitations, but because it helps model focus on doing best work within specific requirements and scope.

**Strategy:** 
- Structure information clearly with critical details at beginning or end
- Consider breaking complex tasks into focused subtasks
- Each subtask should have clear boundaries and specific goals

## Claude 4.x Specific Considerations

### Example Quality Awareness

**CRITICAL:** Claude 4.x models are highly attentive to example details—they learn ALL patterns in examples, including ones you may not intend to teach.

**Risks:**
- Example uses bullets → Model defaults to bullets even if you want prose
- Example is verbose → Model becomes verbose
- Example uses casual tone → Model adopts casual tone
- Example shows specific structure → Model replicates structure

**Safe example construction:**
1. Audit EVERY detail for unintended patterns
2. Ensure ALL aspects demonstrate desired behavior
3. If any aspect conflicts, revise or remove example
4. Better to omit than include examples with mixed signals

### Structural Simplicity

**Modern Claude excels with minimal structure.** Default to simple, clear organization:
- Clear headings and whitespace
- Explicit language stating relationships
- Natural paragraph flow

Only add elaborate structure (XML, nested tags) when genuine complexity demands it.

### Extended Thinking

**Critical understanding:** Extended Thinking is controlled by UI toggle in Claude.ai, not by prompt phrases.

**Don't do this:** "Use 'think carefully' for moderate thinking"

**Do this:** "For architectural decisions with multiple tradeoffs, inform users that enabling Extended Thinking in the chat interface may improve analysis quality."

## Evaluation Tips

**Quick evaluation:**
- Does output match specific requirements?
- Did you get result in one attempt or need multiple iterations?
- Is format consistent across multiple attempts?
- Are you avoiding common mistakes listed above?

## Resources

- [Prompt engineering documentation](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview)
- [Interactive tutorial](https://github.com/anthropics/prompt-eng-interactive-tutorial)
- [Prompt engineering course](https://anthropic.skilljar.com/claude-with-the-anthropic-api)
- [Context engineering guide](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## Summary: Key Takeaways

1. **Be explicit and clear** - State exactly what you want
2. **Provide context and motivation** - Explain why requirements exist
3. **Be specific** - Include constraints, context, structure, requirements
4. **Use examples carefully** - Claude 4.x learns all patterns, including unintended ones
5. **Give permission for uncertainty** - Allow "I don't know" responses
6. **Prefill when needed** - Control format and skip preambles
7. **Chain complex tasks** - Break down for better accuracy
8. **Control format positively** - State what TO do, not what NOT to do
9. **Trust base capabilities** - Modern models need less elaborate prompting
10. **Iterate and refine** - First attempt rarely perfect, test and improve

The best prompt isn't the longest or most complex. It's the one that achieves your goals reliably with the minimum necessary structure.
