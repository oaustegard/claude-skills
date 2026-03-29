# Standalone Tools

Twenty-five skills have no inter-skill dependencies and nothing depends on them. This isn't a deficiency — many are well-scoped single-purpose tools. The isolation is architectural: each solves one problem completely.

## GitHub Operations (standalone subset)

**accessing-github-repos** — REST API fallback when git clone fails in containers. Overlaps with invoking-github and githubbing but at a lower level (raw curl vs. client library vs. CLI).

**building-github-index** (and v2) — Generates progressive disclosure indexes for repos as Claude project knowledge. Two versions exist simultaneously — a consolidation opportunity.

**generating-patches** — Creates git patch files from modifications. The inverse of the GitHub write path.

**Observation:** GitHub operations are split across 5+ skills (accessing, githubbing, invoking, building-index, generating-patches) with no unifying abstraction. Each was built to solve a specific friction point in container environments.

## Web & Frontend

**creating-bookmarklets** — Browser-executable JavaScript with strict formatting. Niche but well-defined.

**creating-mcp-servers** — FastMCP v2 server creation. Heavy reference material (6 reference files). Could be a dependency for skills that want to expose themselves as MCP endpoints, but currently standalone.

**developing-preact** — Full Preact development skill. Closest to an "application framework" in the collection.

**fetching-blocked-urls** — Jina AI fallback for when web_fetch fails. Simple HTTP retry pattern.

**hello-demo** — Demo/test artifact. Meta-skill.

**json-render-ui** — Constrained JSON → Preact UI renderer. An interesting pattern: LLM generates structured data, deterministic runtime renders it. Shares philosophy with charting-vega-lite (declarative spec → visual output) but they don't reference each other.

**using-webctl** — Browser automation via webctl/Playwright. Used by mapping-webapp but not formally depended upon (mapping-webapp has its own capture scripts).

## Analysis & Research

**convening-experts** — Expert panel simulation for problem-solving. References consulting frameworks (MECE, DMAIC, RAPID) but doesn't use orchestrating-agents for actual parallelism. Could benefit from the connection.

**down-skilling** — Distills Opus-level reasoning into Haiku-optimized instructions. The only skill explicitly about cross-model optimization.

**reviewing-ai-papers** — AI/ML content analysis through enterprise engineering lens. Standalone methodology, no code dependencies.

**updating-knowledge** — Systematic web research methodology. Requires web_search tool but no skill dependencies.

## Domain-Specific

**coding-mojo** — Mojo language development in containers. Self-contained with installation, compilation, execution.

**controlling-spotify** — Spotify MCP server integration. Includes MCP server installation scripts — architecturally interesting because it's the only skill that *installs* an MCP server rather than *creating* one.

**learning-goal** — MCII-based goal-setting exercise. Pure methodology, no code.

**llm-as-computer** — Transformer stack machine executor. The most theoretically exotic skill. Completely isolated — it's a demonstration, not a building block.

**making-waffles** — WAFFLES declarations for social posts. Niche content tool.

**sorting-groceries** — Grocery list optimization from aisle photos. The most domain-specific skill in the collection.

## Media

**processing-images** — ImageMagick toolkit awareness. No code — it's a knowledge skill that guides Claude's use of system tools. Conceptually adjacent to seeing-images and image-to-svg but doesn't reference them.

**processing-video** — FFmpeg operations. Same pattern as processing-images: system tool guidance, no custom code.

## Meta / Behavioral

**asking-questions** — Guidance on when to ask clarifying questions. Pure methodology.

**cloning-project** — Project export/backup. Meta-skill about the Claude project system itself.

**loading-skills** — Fetches and cats every SKILL.md from the repo. Bootstrap mechanism.
