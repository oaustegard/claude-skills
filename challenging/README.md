# challenging

Cross-context adversarial review for deliverables before shipping — blog posts, technical recommendations, analysis briefs, code, or any artifact where accuracy matters more than speed.

The value comes from **fresh context**: no shared blind spots with the conversation that produced the artifact, no accumulated goodwill. The adversary sees the draft cold and only the draft.

See [`SKILL.md`](SKILL.md) for the full protocol, profile table, system prompts, and the drill loop. See [`CHANGELOG.md`](CHANGELOG.md) for version history.

## Two paths

| Environment | Adversary | Why |
|---|---|---|
| **Claude Code** (primary) | Native sub-Claude via the Task tool | No key, no network dependency, fresh context |
| **claude.ai, Codex, headless** | Gemini 3.1 Pro (default) or Anthropic API | No subagents available; Gemini also gives genuine cross-model diversity |

## Five profiles

Each lives in its own `references/*.md` file — read only the one you need.

| Profile | Use for | Iteration |
|---|---|---|
| `prose` | Blog posts, essays, articles | parallel replay |
| `analysis` | Research briefs, comparisons, synthesis | parallel replay |
| `code` | Scripts, implementations, PRs | parallel replay |
| `recommendation` | Technical decisions, architecture choices | parallel replay |
| `drill` | 5 Whys on one finding from a review | sequential deepen |

Review profiles replay in parallel — each pass independent, novelty tracked so confabulated findings get filtered. Drill deepens sequentially — one why-level per pass, conditioned on the chain so far, until bedrock or max depth, then a synthesis pass extracts root causes. Patches fix the instance; drills fix the class.

## Verdicts

**SHIP** — clean, deliver. **REVISE** — real issues, sound core. **RETHINK** — structural problems, reconsider.

## Provenance

- **VDD persona & anti-rationalization patterns** — [dollspace.gay](https://dollspace.gay)
- **Grainulation's confabulation-resistance heuristics**
- **5 Whys (drill profile)** — adapted from Tim Kellogg's [open-strix writeup](https://timkellogg.me/blog/2026/04/14/forgetting)

## Complements

- **[generative-thinking](../generative-thinking)** — generates distance before evaluation
- **[convening-experts](../convening-experts)** — synthesizes multiple role-based viewpoints
- **[tiling-tree](../tiling-tree)** — exhaustive MECE partitioning of a solution space

This skill evaluates. It does not generate, synthesize, or partition.

## Dependencies

No skill dependencies. `requests` is loaded lazily — only the API path needs it.

Credentials are only required for the API path (see [`SKILL.md`](SKILL.md#credentials-api-path-only)).
