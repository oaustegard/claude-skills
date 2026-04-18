---
name: challenging
description: Cross-context adversarial review for deliverables before shipping. Use when producing blog posts, technical recommendations, analysis briefs, code, or any artifact where accuracy matters more than speed. Triggers on "challenge this", "review before shipping", "adversarial pass", "stress test this".
metadata:
  version: 0.9.0
---

# Challenging — Adversarial Review

Adversarial review before shipping. Three paths, each with distinct trade-offs:

- **Subagent path** (Claude Code, primary). Native sub-Claude via the Task tool — zero API keys, fresh context window, same model. Best when available.
- **External API path** (claude.ai, Codex, headless). Gemini (cross-model + cross-context) or Anthropic API (cross-context). Costs an incremental API call but gives genuine outside perspective.
- **Self path** (any environment). The caller assistant inhabits the adversary persona in a dedicated response. Zero cost, retains full subject-matter context from the conversation. Weaker at catching same-session confabulations than fresh-context adversaries, stronger at catching local-convention and factual errors the artifact glosses over. Not a strict downgrade — a different failure-mode profile.

The `adversary='auto'` resolution (default) picks gemini → claude → self based on available credentials. Callers in Claude Code still use `prepare()` + Task tool explicitly (subagent is strictly better than self in that environment, and auto-detection of Claude Code is brittle).

Inspired by VDD (dollspace.gay) and Grainulation's anti-rationalization patterns. The `drill` helper adopts the 5 Whys pattern from Tim Kellogg's [open-strix writeup](https://timkellogg.me/blog/2026/04/14/forgetting). The self-path persona-inhabitation move is kin to generative-thinking's inversion — commit to the mode before evaluating.

## Profiles

Pick the profile matching your artifact. **Read only the profile you need** — each is self-contained with persona, anti-rationalization table, evaluation criteria, and adversary system prompt.

| Profile | Use For | Iteration strategy | File |
|---------|---------|--------------------|------|
| `prose` | Blog posts, essays, articles | parallel replay | `references/prose.md` |
| `analysis` | Research briefs, comparisons, synthesis | parallel replay | `references/analysis.md` |
| `code` | Scripts, implementations, PRs | parallel replay | `references/code.md` |
| `recommendation` | Technical decisions, architecture choices | parallel replay | `references/recommendation.md` |
| `drill` | 5 Whys on one finding from a review | sequential deepen | `references/drill.md` |

One engine, one surface, two iteration strategies. Review profiles iterate in *parallel replay* — each pass independent, novelty tracked for confabulation. Drill iterates in *sequential deepen* — each pass takes the chain so far and produces one more why-level until bedrock or max depth, followed by a synthesis pass that extracts root causes.

## Usage — Claude Code (subagent path, primary)

Two-step protocol: a Python helper builds the prompt, you spawn a subagent via the Task tool, then a parser turns its response into structured findings.

```python
import sys
sys.path.insert(0, '/mnt/skills/user/challenging/scripts')
from challenger import prepare, parse_response

job = prepare(
    artifact=open('/home/claude/draft.md').read(),
    profile='prose',
    context='Blog post about RAG scaling laws',
)
```

Then invoke the Task tool — `subagent_type='general-purpose'`, `prompt=job['prompt']`, `description='Adversarial review (prose)'`. The subagent runs in a fresh context, applies the persona, and returns a JSON message. Pass that message text to the parser:

```python
result = parse_response(subagent_text)
print(result['verdict'])    # SHIP | REVISE | RETHINK
print(result['findings'])   # List of specific issues
print(result['strengths'])  # What to preserve
```

**Why subagents (not the API):** no key, no network dependency, fresh context, and the same Claude that's reviewing your work is reviewing it again with no prior bias — but in a clean window. For cross-model diversity (genuinely different blind spots), use Gemini below.

### Drill — 5 Whys on a systemic finding (subagent path)

Drill uses the same `prepare()` / Task / `parse_response()` protocol as review profiles, but you run the loop yourself — each pass takes the chain so far and produces exactly ONE new `{why, because}`. When the adversary sets `bedrock=true` (or you hit max depth), run a final synthesis pass.

```python
from challenger import prepare, parse_response

suspect = next(f for f in result['findings'] if f['severity'] in ('high', 'critical'))
artifact = open('/home/claude/draft.md').read()
ctx = 'Blog post about RAG scaling laws'

chain = []
for depth in range(1, 6):
    job = prepare(artifact, 'drill', context=ctx, finding=suspect, chain=chain)
    # Task tool: subagent_type='general-purpose', prompt=job['prompt']
    step = parse_response(subagent_text)   # {why, because, bedrock, reasoning}
    chain.append({'why': step['why'], 'because': step['because']})
    if step.get('bedrock'):
        break

# Final synthesis pass over the completed chain
job = prepare(artifact, 'drill', context=ctx, finding=suspect, chain=chain, synthesize=True)
# Task tool again, then:
diagnosis = parse_response(subagent_text)
print(diagnosis['chain'])        # [{why, because}, ...]
print(diagnosis['root_causes'])  # usually 3-4 distinct systemic issues
print(diagnosis['direction'])    # compass heading for the process fix
```

`finding` accepts either a dict from `parse_response()` or a free-text description. Patches fix the instance; drills fix the class. Why sequential, not parallel? A single-shot drill lets the model shortcut the whole tree and produces renames instead of explanations; one level per pass forces each "because" to earn its depth. See `references/drill.md` for when to drill and the anti-patterns to reject.

## Usage — claude.ai, Codex, headless scripts (API path)

Where subagents aren't available, call an external model directly.

```python
from challenger import challenge

result = challenge(
    artifact=open('draft.md').read(),
    profile='prose',
    context='Blog post about RAG scaling laws',
    adversary='gemini',     # default — cross-model diversity
)
```

`adversary` accepts:
- **`auto`** (default) — resolves to gemini > claude > self based on available credentials. Logs the choice.
- **`gemini`** — Gemini 3.1 Pro. Cross-model + cross-context. Requires Gemini credentials.
- **`claude`** — Anthropic API. Cross-context, same model family. **Do not use this in Claude Code** — use the subagent path instead.
- **`self`** — NOT runnable via `challenge()` (raises with a pointer to `prepare_self()`). Self-challenge requires the caller assistant to produce the adversary response, which a synchronous function cannot do.

Drill uses the same `challenge()` call with `profile='drill'`. `challenge()` runs the whole sequential-deepen loop internally and returns the synthesized diagnosis:

```python
diagnosis = challenge(
    artifact,
    profile='drill',
    context=ctx,
    finding=suspect,          # required for drill
    max_iterations=5,         # optional — defaults to 5 for drill, 3 for review
)
print(diagnosis['chain'], diagnosis['root_causes'], diagnosis['direction'])
```

### Blocking mode (API path, review profiles only)

```python
result = challenge(artifact, profile='analysis', mode='blocking', max_iterations=3)
```

Loops the adversary until: (a) no actionable findings, (b) novelty rate > 75% (adversary inventing problems — artifact is clean), or (c) max iterations. `mode` is ignored when `profile='drill'` — drill always iterates until bedrock or max depth. Subagent-path callers can replicate blocking mode by looping `prepare()` / Task / `parse_response()` themselves and tracking findings across iterations.

## Usage — self path (same-context adversary)

When neither subagents nor external API credentials are available — or when subject-matter context from the current conversation is load-bearing for the review — use `prepare_self()`. The caller assistant inhabits the adversary persona in a dedicated response.

```python
from challenger import prepare_self, parse_response

job = prepare_self(
    artifact=open('draft.md').read(),
    profile='analysis',
    context='Cross-domain claim that depends on codebase-specific IEEE-754 conventions',
)
# job is {'system': <adversary system prompt>, 'user': <artifact + context>, ...}
```

The caller then:
1. Reads `job['system']` — the prompt opens with `SELF-INVOCATION MODE` instructing a full persona switch. Commit to it.
2. In a dedicated response, produces JSON matching the schema described in the system prompt.
3. Passes that JSON string to `parse_response()`.

```python
# After generating the adversary JSON in a dedicated response:
result = parse_response(adversary_json_text)
print(result['verdict'], result['findings'])
```

**When self beats external:** the artifact depends on conventions visible only from inside the conversation (codebase invariants, prior decisions, domain terminology established earlier). External adversaries with generic priors issue confident-but-wrong findings in these cases; self retains the context.

**When external beats self:** the artifact contains confabulations or blind spots the caller already committed to. Fresh context catches these; self inherits them.

**When possible, run both.** They have orthogonal failure modes.

Drill via self path uses the same loop as the subagent drill: iterate `prepare_self(profile='drill', finding=..., chain=...)` — produce one `{why, because}` per dedicated response — append to chain — until bedrock or max depth — then a final synthesize pass.

## Verdicts

- **SHIP**: Clean. Deliver.
- **REVISE**: Real issues, sound core. Fix and deliver.
- **RETHINK**: Structural problems. Reconsider approach.

## Severity Levels

- **critical/high/medium/low**: Standard severity — actionable findings that block in blocking mode.
- **unverifiable**: Adversary flagged something it doesn't recognize (API, pattern, model name) but can't confirm is wrong. Surfaced for awareness but does not block SHIP. Use `context` to ground the adversary on APIs/patterns it may not know.

## Credentials (API path only)

The subagent path needs no credentials. The API path loads from environment or project files:

- **Gemini via Cloudflare Gateway** (preferred): `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`, `CF_API_TOKEN` from env or `proxy.env`
- **Gemini direct**: `GOOGLE_API_KEY` from env
- **Claude API** (claude.ai fallback only): `ANTHROPIC_API_KEY` or `API_KEY` from env or `claude.env`

No external skill dependencies. `requests` is loaded lazily — only the API path requires it.
