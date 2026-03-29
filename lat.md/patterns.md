# Patterns

Architectural patterns that recur across unrelated skills. These aren't formal dependencies — they're shared design decisions that emerged independently.

## Progressive Disclosure

**Skills using it:** building-github-index, creating-mcp-servers, crafting-instructions, mapping-codebases, generating-lattice

**The pattern:** Don't dump everything. Provide a structural overview first, then let the consumer drill into details on demand. building-github-index generates layered repo indexes for Claude project knowledge. creating-mcp-servers explicitly documents progressive disclosure for tool descriptions. mapping-codebases exports only the API surface (signatures, exports), deferring full source to selective reading.

**Why it recurs:** Token cost. Every skill that produces documentation for LLM consumption faces the same constraint — context windows are finite. Progressive disclosure is the universal response to this constraint.

## Knowledge Skills vs. Code Skills

Some skills contain only a SKILL.md with no scripts — the markdown *is* the implementation. 17 of 59 skills work this way.

**Examples:** asking-questions, charting, check-tools, cloning-project, creating-bookmarklets, down-skilling, fetching-blocked-urls, generating-patches, hello-demo, learning-goal, making-waffles, processing-images, processing-video, reviewing-ai-papers, sorting-groceries, updating-knowledge, versioning-skills

**The pattern:** Some skills contain only a SKILL.md that guides Claude's behavior — no Python scripts, no automation. They work because Claude already has the capabilities (ImageMagick, ffmpeg, git, web search); the skill provides decision frameworks, formatting rules, and workflow patterns.

**Design rationale:** This is the cheapest possible skill architecture. No installation, no dependencies, no maintenance. The SKILL.md *is* the implementation — it's a prompt injection that shapes Claude's existing behavior. The tradeoff: no enforcement. A knowledge skill can be ignored; a code skill with validation (like generating-lattice's `lat check`) cannot.

## Declarative Spec → Deterministic Render

**Skills using it:** charting-vega-lite, json-render-ui, generating-lattice (lat.md format)

**The pattern:** The LLM generates structured data (Vega-Lite JSON, UITree JSON, wiki-linked markdown). A deterministic runtime renders it. The LLM's job is conceptual — *what* to show — not mechanical — *how* to render it.

**Why it matters:** This pattern separates LLM creativity from deterministic correctness. The spec is validatable (schema checks, lat check). The render is reproducible. Compare to the charting skill, which generates imperative matplotlib code — harder to validate, easier to break.

## Container Awareness

**Skills addressing it:** configuring, accessing-github-repos, using-webctl, check-tools, coding-mojo, controlling-spotify

**The shared problem:** Claude.ai containers are ephemeral, network-restricted, and lack persistent state. Skills must handle: tool installation on every session, credential loading from env files, network egress through allowed domains, filesystem resets between conversations.

**The non-pattern:** Despite this shared concern, each skill solves it independently. configuring exists as a universal loader, but most skills that need environment setup don't reference it. This is the collection's most obvious missed abstraction.

## AST-First Analysis

**Skills using it:** mapping-codebases, exploring-codebases, searching-codebases

**The pattern:** Use tree-sitter AST parsing instead of regex or text matching for code understanding. Extract structure mechanically (zero LLM tokens), then apply intelligence selectively.

**Hub dependency:** All three depend on mapping-codebases, which owns the tree-sitter integration. The `_MAP.md` file format is the shared interchange.

## Deprecation by Absorption

**Instances:** sampling-bluesky-zeitgeist → browsing-bluesky, building-github-index → building-github-index-v2

**The pattern:** When a skill grows to subsume another, the original is marked deprecated but not removed. Both instances still exist in the collection. This is benign for now but creates confusion in skill routing — the deprecated skill's trigger words still match.

## Memory Integration

**Skills with memory integration:** orchestrating-skills, remembering (core), inspecting-skills, mapping-webapp (via api-credentials)

**The non-pattern:** Most skills are stateless. They don't read from or write to Muninn's memory system. This is mostly correct — standalone tools shouldn't need memory. But analysis skills (reviewing-ai-papers, updating-knowledge, convening-experts) could benefit from recalling prior research. The connection is handled by the conversation-level Muninn boot, not by the skills themselves. Memory integration is an *environmental* capability, not a skill-level one.
