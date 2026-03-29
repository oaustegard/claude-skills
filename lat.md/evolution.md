# Evolution

How the collection grew. The skills weren't designed as a system — they accumulated as solutions to specific problems.

## Growth Phases

Six phases of accumulation, from infrastructure to meta-skills. The order reveals what problems were felt first.

**Phase 1: Core infrastructure.** remembering, configuring, api-credentials, loading-skills. These solved the fundamental problem: Claude has no persistent state. remembering became the architectural center of the Muninn project. configuring handled the "which environment am I in?" question.

**Phase 2: GitHub integration.** accessing-github-repos, githubbing, invoking-github, building-github-index. Each solved a different friction point with GitHub in containers. git clone doesn't work → REST API fallback. Need to create issues → CLI wrapper. Need to commit from chat → client library. Need repo as project knowledge → index generator. The accumulation is visible in hindsight: five skills doing overlapping things because each was built when a specific need arose.

**Phase 3: Code understanding.** mapping-codebases, exploring-codebases, searching-codebases. The cleanest cluster — deliberate architecture. mapping-codebases was designed as a foundation layer, and the others were built on its output format. generating-lattice is the newest addition, extending the chain to cross-referenced documentation.

**Phase 4: Domain tools.** image-to-svg, charting, browsing-bluesky, processing-images/video, etc. Each serving a specific use case. The visual pipeline (image-to-svg → svg-portrait-mode) is the most sophisticated, with genuine multi-stage processing and C compilation.

**Phase 5: Meta-skills.** creating-skill, crafting-instructions, inspecting-skills, versioning-skills, down-skilling. Skills about skills. This is where the collection became self-aware — tools for building and managing the toolbox itself.

**Phase 6: Orchestration.** orchestrating-agents, orchestrating-skills, flowing, tiling-tree. Parallel execution, workflow DAGs, problem decomposition. These emerged from the realization that many tasks have a shape that's expensive to execute serially.

## Organic vs. Deliberate

**Deliberate clusters** (designed with dependencies in mind): Code Intelligence, Visual Pipeline, Skill Lifecycle. These have clean dependency chains and clear architectural rationale.

**Organic accumulation** (each skill independent, overlap emerged): GitHub Operations, Container Awareness patterns. These solve real problems but share no architecture.

**Single-purpose tools** (no design intent beyond "I needed this once"): sorting-groceries, hello-demo, making-waffles. Perfectly fine as standalone tools — not everything needs to be part of a system.

---
