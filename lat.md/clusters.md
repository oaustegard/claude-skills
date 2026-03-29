# Clusters

Six connected clusters emerge from the dependency graph. Each has a hub skill that others depend on. The clusters are themselves mostly independent — skills bridge between them only through infrastructure layers ([[clusters#Infrastructure Layer]]).

## Code Intelligence

Hub: **mapping-codebases**. The most-depended-upon skill (4 dependents). AST-based structural extraction creates `_MAP.md` files that feed downstream consumers.

**The chain:** mapping-codebases (structure) → exploring-codebases (search within) → searching-codebases (regex + n-gram index) → generating-lattice (cross-referenced knowledge graph)

**Also connected:** mapping-webapp extends the pattern to behavioral documentation, adding browser automation for visual verification. It's the only skill in this cluster that reaches outside to [[clusters#Infrastructure Layer]] (api-credentials).

**Design rationale:** Every skill in this cluster exists because reading full source files is token-expensive. mapping-codebases solves this by extracting the API surface via tree-sitter — zero LLM tokens. Each downstream skill builds a different query/documentation layer on top of the same structural foundation. The progression is: structure → search → understanding → documentation.

**Tension:** mapping-webapp tried to extend this to web app *behavior* but drifted toward screenshot-centric approaches. generating-lattice's concept-grouped top-down approach may be the better pattern for that problem space.

## Visual Pipeline

Hub: **image-to-svg**. A deep pipeline with the collection's most complex dependency chain.

**The chain:** seeing-images (augmented vision analysis) → image-to-svg (raster to vector conversion, uses flowing for DAG orchestration) → svg-portrait-mode (foveated 4-zone selective detail, uses all three)

**Key dependency:** flowing provides the DAG workflow runner. This is the only cluster where flowing is used as infrastructure — elsewhere it's invoked directly as a standalone workflow tool.

**Design rationale:** The visual pipeline exists because Claude's native vision is insufficient for precise vectorization. seeing-images provides ground truth (colors, boundaries, shapes), image-to-svg does the conversion with a multi-stage pipeline, and svg-portrait-mode adds artistic intelligence (foreground/background discrimination, detail allocation). The flowing dependency isn't arbitrary — the SVG conversion genuinely has a DAG shape (parallel stroke extraction → merge → optimize).

**Notable:** This cluster contains the only C code in the collection (nn_assign.c in image-to-svg) — nearest-neighbor color assignment compiled for performance.

## Bluesky Ecosystem

Hub: **browsing-bluesky**. Social media analysis and interaction cluster.

**The chain:** extracting-keywords (YAKE algorithm) → categorizing-bsky-accounts (topic classification) → browsing-bluesky (comprehensive API/firehose access)

**Deprecated:** sampling-bluesky-zeitgeist is marked deprecated in favor of browsing-bluesky, which absorbed its firehose sampling capability.

**Design rationale:** The cluster grew bottom-up: keyword extraction was generic, then applied to Bluesky account analysis, then browsing-bluesky unified the API surface. The zeitgeist sampling was an early experiment that got folded in. extracting-keywords remains the only skill here with utility outside Bluesky.

## LLM Orchestration

Hub: **orchestrating-agents**. Parallel API calls, delegation, multi-agent patterns.

**The chain:** orchestrating-agents (core orchestration engine) → tiling-tree (MECE exhaustive exploration) and orchestrating-skills (skill-aware context routing, also depends on remembering)

**Design rationale:** Two different extension philosophies on the same base. tiling-tree is domain-agnostic — it uses orchestrating-agents purely as a parallelism engine for recursive problem decomposition. orchestrating-skills is Muninn-specific — it adds skill awareness and memory integration, making it the bridge between orchestration and the memory system.

**Infrastructure link:** api-credentials provides credential management for the orchestration engine's API calls. configuring sits one layer below api-credentials.

## Skill Lifecycle

Not a dependency chain but a conceptual cluster: the skills that manage other skills.

**Creation:** creating-skill (structure/templates, depends on crafting-instructions and versioning-skills)
**Installation:** installing-skills, loading-skills (different mechanisms: file copy vs. context loading)
**Inspection:** inspecting-skills (cross-skill import indexing)
**Versioning:** versioning-skills (rollback/comparison, required for all skill development)
**Instructions:** crafting-instructions (project instructions, prompts, skill triggers)

**Meta-observation:** This cluster is self-referential — creating-skill references versioning-skills, which is itself a skill created via creating-skill. The bootstrap problem is solved by crafting-instructions existing independently of the skill framework.

## Data & Visualization

Two skills with mutual awareness: **charting** (Python/matplotlib/seaborn) and **charting-vega-lite** (browser-rendered interactive). Each mentions the other as an alternative for different use cases.

**Also connected:** exploring-data (EDA via ydata-profiling) and forecasting-reverso (time series prediction) are conceptually adjacent but have no formal dependencies — they produce data that the charting skills could visualize, but the connection is implicit.

**Design rationale:** The charting split reflects a real architectural decision: static publication-quality plots (charting) vs. interactive browser-rendered visualizations (charting-vega-lite). Neither subsumes the other. The lack of formal integration with exploring-data is arguably a gap — an EDA pipeline that auto-selects chart types would be natural.

## Infrastructure Layer

Not a cluster but the connective tissue: **configuring** → **api-credentials** → (invoking-gemini, invoking-github, orchestrating-agents, mapping-webapp).

**Design rationale:** configuring is the universal environment loader (Claude.ai, Claude Code, Codex, Jules). api-credentials sits above it, providing typed access to specific providers. This two-layer design means skills don't need to know which environment they're running in — they just ask for credentials.

**Also infrastructure but isolated:** check-tools (environment validation) has no dependents despite being useful to many skills. githubbing depends on configuring but nothing depends on githubbing.
