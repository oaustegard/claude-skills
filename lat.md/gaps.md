# Gaps

Missing connections, redundancies, and consolidation opportunities visible from the lattice view.

## Redundancies

Three areas where skills overlap or coexist with deprecated versions.

**GitHub operations:** Five skills (accessing-github-repos, githubbing, invoking-github, building-github-index, generating-patches) with overlapping scope. A unified GitHub layer with progressive disclosure would reduce routing confusion.

**building-github-index vs. building-github-index-v2:** Both exist, same name in frontmatter. One should supersede the other.

**sampling-bluesky-zeitgeist:** Deprecated but still present. Trigger words overlap with browsing-bluesky.

## Missing Connections

**convening-experts → orchestrating-agents:** Expert panels could use parallel API calls for independent expert perspectives. Currently convening-experts is pure methodology — the LLM simulates all experts sequentially.

**processing-images/processing-video → seeing-images:** These knowledge skills guide image/video operations but don't reference the augmented vision tools that could improve their outputs.

**json-render-ui ↔ charting-vega-lite:** Both implement the "declarative spec → deterministic render" pattern but don't reference each other. A user asking for "an interactive dashboard" should know both options exist.

**exploring-data → charting-vega-lite:** EDA produces statistics and distributions; charting-vega-lite renders them. The pipeline is obvious but implicit.

**updating-knowledge / reviewing-ai-papers → remembering:** Research skills that don't persist their findings. The conversation-level Muninn integration handles this, but skill-level memory hooks could make research accumulation automatic.

## Structural Gaps

Four cross-cutting concerns that no skill currently owns.

**No unified routing layer.** Skill selection is purely trigger-word matching in descriptions. With 59 skills, false positives and missed triggers are inevitable. orchestrating-skills addresses this but isn't integrated into boot.

**No shared test framework.** Each skill with code tests independently (or doesn't). versioning-skills tracks file changes but doesn't validate behavior.

**No dependency resolution.** Skills declare dependencies in prose ("Requires **mapping-codebases** skill") but nothing enforces installation order or compatibility.

**Container setup duplication.** Many skills independently handle pip install, tool verification, and environment setup. configuring exists as a shared layer but adoption is inconsistent.

## Consolidation Candidates

Five merge/delete opportunities that would reduce routing confusion without losing capability.

1. **GitHub ops** → unified skill with progressive disclosure levels
2. **charting + charting-vega-lite** → single skill with static/interactive routing
3. **sampling-bluesky-zeitgeist** → delete (already deprecated)
4. **building-github-index v1** → delete or merge into v2
5. **processing-images + processing-video** → unified "media-processing" knowledge skill (they share the same pattern: system tool guidance, no custom code)
