# challenging

Cross-context adversarial review for deliverables before shipping — blog posts, technical recommendations, analysis briefs, code, or any artifact where accuracy matters more than speed.

The value comes from **disciplined distance** from the draft. Three strategies for getting it:

- **Fresh context** (subagent or external API) — no shared blind spots with the conversation that produced the artifact, no accumulated goodwill. Catches structural flaws invisible from inside. Blind to local conventions not stated in the artifact.
- **Same-context persona switch** (self) — retains full subject-matter context from the conversation. Catches local-convention mismatches and factual errors the artifact glosses over. Vulnerable to same-session confabulations the caller already committed to.

Neither dominates. Run both when you can afford to; pick intentionally when you can't.

See [`SKILL.md`](SKILL.md) for the full protocol, profile table, system prompts, and the drill loop. See [`CHANGELOG.md`](CHANGELOG.md) for version history.

## Three paths

| Environment | Adversary | How it works | Cost |
|---|---|---|---|
| **Claude Code** (primary) | Native sub-Claude via the Task tool | `prepare()` → Task tool → `parse_response()`. Fresh context, same model. | Free |
| **claude.ai, Codex, headless** with API creds | Gemini 3.1 Pro or Anthropic API | `challenge(adversary='auto')` resolves gemini > claude. Cross-context; gemini is cross-model. | Incremental API call |
| **Any environment** | Caller assistant in adversary persona | `prepare_self()` → caller produces JSON in a dedicated response → `parse_response()`. Retains conversation context; explicit persona switch is the discipline. | Free |

`adversary='auto'` (the default for `challenge()`) ladders gemini → claude → self based on credentials. Claude Code callers stay on `prepare()` + Task tool explicitly — subagent is strictly better than self there, and auto-detecting Claude Code is brittle.

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

- **[generative-thinking](../generative-thinking)** — generates distance before evaluation. The self path's persona-switch move is kin to generative-thinking's inversion; both commit to a mode before producing output.
- **[convening-experts](../convening-experts)** — synthesizes multiple role-based viewpoints
- **[tiling-tree](../tiling-tree)** — exhaustive MECE partitioning of a solution space

This skill evaluates. It does not generate, synthesize, or partition.

## Dependencies

No skill dependencies. `requests` is loaded lazily — only the API path needs it.

Credentials are only required for the API path (see [`SKILL.md`](SKILL.md#credentials-api-path-only)).
