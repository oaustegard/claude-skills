---
name: writing-instructions
description: "Write effective instructions for Claude: project instructions, standalone prompts, and skill content. Use when users need help writing prompts, setting up project instructions, choosing between instruction formats, or improving how they communicate with Claude. Covers writing principles, model-aware calibration, and format selection. For building and testing complete skills, use skill-creator instead."
---

# Writing Instructions for Claude

Principles and patterns for writing instructions that Claude follows reliably — whether as project instructions, standalone prompts, or skill content.

## Choosing the Right Format

Determine format before writing. The wrong container undermines good instructions.

**Project instructions** — persistent context for a workspace. Use when all conversations in a project need shared knowledge, team collaboration context, or initiative-specific behavior. Signals: "for this project," "all conversations about X," "team workspace."
Read [references/project-instructions.md](references/project-instructions.md) for detailed guidance.

**Standalone prompts** — ephemeral, conversational, immediate. Use for one-off requests, ad-hoc direction, or conversational refinement. Signals: "for this task," "right now," "just this once."
Read [references/standalone-prompts.md](references/standalone-prompts.md) for techniques.

**Skill content** — portable expertise that loads on-demand across contexts. Use when capability is needed across multiple projects, procedural knowledge applies broadly, and instructions should activate automatically on relevant triggers. Signals: "every time I," "whenever," "reusable," "teach Claude how to."
For building full skills (structure, testing, iteration, packaging), use the **skill-creator** skill.

**Combined approaches** work well: project instructions provide "what you need to know" (reference material, context) while skills provide "how to do things" (methods, procedures). Read [references/choosing-formats.md](references/choosing-formats.md) for detailed comparison and migration patterns.

## Core Writing Principles

These apply to ALL instruction formats. They are ordered by impact.

### 1. Imperative Construction

Frame as direct commands. Imperative language reduces ambiguity and signals that the instruction is not optional.

- ❌ "Consider creating X" → ✅ "Create X when conditions Y"
- ❌ "You might want to search" → ✅ "Search for"
- ❌ "Try to optimize" → ✅ "Optimize by"

### 2. Context and Motivation

Explain WHY requirements exist. Claude uses reasoning about purpose to make better decisions in unstated edge cases, and WHY context is particularly valuable for Opus's autonomous judgment.

- ❌ "Use formal tone"
- ✅ "Use formal tone because documentation targets enterprise clients expecting authoritative voice"

A requirement without context is a rule Claude follows mechanically. A requirement with context is a principle Claude can extend intelligently.

### 3. Positive Directive Framing

State WHAT to do, not what NOT to do. Negative instructions force Claude to infer the desired alternative — positive instructions state it directly.

- ❌ "Don't use bullet points" → ✅ "Write in flowing paragraph form"
- ❌ "Avoid technical jargon" → ✅ "Use accessible language for beginners"
- ❌ "Never output raw data" → ✅ "Present data with interpretation and context"

When a negative constraint is truly necessary, pair it with the positive alternative: "Present in prose paragraphs, not bullet lists, because flowing text is more conversational for learning contexts."

### 4. Strategic Over Procedural

Provide goals and decision frameworks rather than step-by-step procedures. If Claude can infer the procedure from the goal, specify only the goal.

- Specify: success criteria, boundaries, decision frameworks, quality standards
- Minimize: sequential steps, detailed execution, operations Claude can determine from goals

This principle scales with model capability — Opus needs less procedural detail than Haiku (see Model-Aware Calibration below).

### 5. Trust Base Behavior

Claude's system prompt already handles citation protocols, copyright, safety, general tool usage, artifact creation, conversational tone, and accuracy standards. Only specify project- or domain-specific deviations from these defaults.

Duplicating system prompt behavior wastes tokens and can create conflicting signals. Test whether Claude already does what you want before adding instructions for it.

## Model-Aware Calibration

Instructions may execute across Haiku, Sonnet, and Opus. Each model responds differently to instruction density and abstraction level.

**Haiku (1.3–1.5× detail):** Lead with explicit imperative commands and concrete decision trees. Haiku follows direct procedures reliably but struggles with abstract principles. Provide exact conditions, specific fallbacks, and complete examples for every expected scenario. Structure as: "When X, do Y. When Z, do W."

**Sonnet (1.0–1.2× detail):** Provide decision frameworks with explicit conditions alongside 2–3 concrete examples demonstrating desired patterns. Sonnet learns strongly from examples and handles moderate abstraction when anchored by demonstrations. Balance procedural clarity with strategic context.

**Opus (0.6–0.8× detail):** Emphasize strategic goals, reasoning context, and principles over procedures. Opus uses rich WHY context for autonomous judgment in edge cases. One clear example often suffices. Overly procedural instructions constrain Opus unnecessarily. Frame as: "Goal is X because Y. Apply judgment for unstated cases."

**The density multiplier** is relative to what you'd tell a competent colleague for the same task.

**Practical layering pattern:** Structure instructions so imperative commands come first (Haiku gets what it needs immediately), followed by decision frameworks and examples (Sonnet's sweet spot), with strategic reasoning and WHY context woven throughout (Opus leverages this for edge cases). A single instruction set serves all three models when layered well.

**When uncertain about target model:** Optimize for Sonnet. Sonnet-optimized instructions work adequately on both Haiku (slightly verbose but functional) and Opus (slightly over-specified but not harmful).

## Example Quality Awareness

Examples are the most powerful and most dangerous instruction tool. Claude 4.x learns ALL patterns from examples — format, verbosity, structure, tone, terminology — including patterns you didn't intend to teach.

**Rules for examples:**
- Audit every detail: if the example uses bullets but you want prose, Claude defaults to bullets
- Ensure ALL aspects of every example demonstrate desired behavior
- Better to omit examples entirely than include ones with mixed signals
- One well-crafted example outperforms three sloppy ones

**Model-specific impact:**
- Sonnet: Examples are highly influential — include 2–3 that perfectly demonstrate desired patterns
- Opus: Examples help but Opus weights explicit principles more heavily — one clear example suffices, omit entirely if examples can't perfectly align with all requirements
- Haiku: Examples are critical — provide complete input/output pairs covering each expected scenario

## Structural Simplicity

Default to clear organization using headings, whitespace, and natural paragraph flow. Explicit language stating relationships is usually sufficient.

Use structured markup (XML tags, JSON schemas) only when separating distinct content types in complex scenarios, when absolute certainty about content boundaries is required, or for API-driven workflows needing structured parsing.

**Decision rule:** Can this be organized with headings? → Do that first. Only reach for XML/JSON when headings genuinely fail to create clarity.

## Extended Thinking Guidance

Extended thinking is a UI toggle, not controllable via prompt phrasing. In instructions:

- Make the assistant aware it exists as a feature
- Provide domain-specific indicators for when to suggest it
- ❌ Do NOT include "trigger phrases" like "think carefully" — they don't activate extended thinking

Pattern: "For tasks involving [specific complexity], suggest enabling Extended thinking, briefly explaining why it would help for THIS task."

## Complexity Scaling

Match instruction complexity to task needs. Before adding complexity, ask: could a simpler formulation work equally well?

**Simple task** → Clear, concise prompt with explicit output expectations
**Medium task** → Structured guidance with decision frameworks and 1–2 examples
**Complex task** → Comprehensive instructions with model-aware layering + suggest extended thinking

The best instructions use the minimum complexity that produces reliable results.

## Common Mistakes

**System prompt duplication** — "Use web_search for current info, cite sources." This wastes tokens and adds no value. Omit unless the project has specific deviations from default behavior.

**Negative framing without alternatives** — "Don't use lists, never be verbose." State the positive: "Present in natural prose paragraphs."

**Fake thinking triggers** — "Use 'think carefully' for deep thinking." Phrases don't control extended thinking. Suggest the UI toggle for specific complexity types.

**Procedural micromanagement** — "Step 1: Analyze. Step 2: Search. Step 3: Synthesize." Instead: "Research goal: X. Quality standard: Y. Present findings as Z."

**Contextless requirements** — "Always use formal tone." Add WHY: "Use formal tone for audit reports because regulators expect authoritative voice."

**Imperfect examples** — Example uses bullets when you want prose. Either create perfect examples or omit them entirely.

## Quality Checklist

Before delivering any instruction set:

**Does it say what to do?** Imperative commands, positive framing, clear success criteria.

**Does it say why?** Context and motivation for non-obvious requirements, enabling intelligent edge-case handling.

**Is it calibrated?** Appropriate detail density for the target model, with layered structure if model is unknown.

**Is it minimal?** No system prompt duplication, no unnecessary complexity, no procedural steps Claude can infer from goals.

**Are examples safe?** Every aspect of every example demonstrates desired behavior, or examples are omitted.

## Format-Specific References

- [references/project-instructions.md](references/project-instructions.md) — Writing project instructions: role definition, quality standards, decision frameworks, domain tool patterns
- [references/standalone-prompts.md](references/standalone-prompts.md) — Crafting effective prompts: specificity, context, examples, complexity scaling
- [references/choosing-formats.md](references/choosing-formats.md) — When to use skills vs projects vs prompts, combined approaches, migration patterns
