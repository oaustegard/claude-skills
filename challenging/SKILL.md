---
name: challenging
description: Cross-context adversarial review for deliverables before shipping. Use when producing blog posts, technical recommendations, analysis briefs, code, or any artifact where accuracy matters more than speed. Triggers on "challenge this", "review before shipping", "adversarial pass", "stress test this".
metadata:
  version: 0.8.0
---

# Challenging — Adversarial Review

Adversarial review by an adversary with **fresh context** — no shared blind spots, no accumulated goodwill from your conversation.

In Claude Code (the primary path), the adversary is a native sub-Claude spawned via the Task tool: zero API keys, fresh context window, full Claude reasoning. The Gemini API path remains as an option for cross-model diversity, and the Claude API path exists only for claude.ai (which can't spawn subagents).

Inspired by VDD (dollspace.gay) and Grainulation's anti-rationalization patterns. The `drill` helper adopts the 5 Whys pattern from Tim Kellogg's [open-strix writeup](https://timkellogg.me/blog/2026/04/14/forgetting).

## Profiles

Pick the profile matching your artifact. **Read only the profile you need** — each is self-contained with persona, anti-rationalization table, evaluation criteria, and adversary system prompt.

| Profile | Use For | File |
|---------|---------|------|
| `prose` | Blog posts, essays, articles | `references/prose.md` |
| `analysis` | Research briefs, comparisons, synthesis | `references/analysis.md` |
| `code` | Scripts, implementations, PRs | `references/code.md` |
| `recommendation` | Technical decisions, architecture choices | `references/recommendation.md` |

`drill` is not a profile — it's a follow-up pass on a specific finding. See `references/drill.md`.

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

```python
from challenger import prepare_drill, parse_drill_response

suspect = next(f for f in result['findings'] if f['severity'] in ('high', 'critical'))

job = prepare_drill(
    artifact=open('/home/claude/draft.md').read(),
    finding=suspect,
    context='Blog post about RAG scaling laws',
)
# Invoke Task tool with prompt=job['prompt'], then:
diagnosis = parse_drill_response(subagent_text)
print(diagnosis['chain'])        # [{why, because}, ...] up to 5 levels
print(diagnosis['root_causes'])  # usually 3-4 distinct systemic issues
print(diagnosis['direction'])    # compass heading for the process fix
```

`finding` accepts either a dict from `parse_response()` or a free-text description. Patches fix the instance; drills fix the class. See `references/drill.md` for when to drill.

## Usage — claude.ai, Codex, headless scripts (API path)

Where subagents aren't available, call an external model directly.

```python
from challenger import challenge, drill

result = challenge(
    artifact=open('draft.md').read(),
    profile='prose',
    context='Blog post about RAG scaling laws',
    adversary='gemini',     # default — cross-model diversity
)
```

`adversary` accepts:
- **`gemini`** (default) — Gemini 3.1 Pro. Genuine cross-model review.
- **`claude`** — Anthropic API. Use only on claude.ai (which can't spawn subagents). **Do not use this in Claude Code** — use the subagent path instead.

`drill()` mirrors `challenge()` and accepts the same `adversary` argument.

### Blocking mode (API path only)

```python
result = challenge(artifact, profile='analysis', mode='blocking', max_iterations=3)
```

Loops the adversary until: (a) no actionable findings, (b) novelty rate > 75% (adversary inventing problems — artifact is clean), or (c) max iterations. Subagent-path callers can replicate this by looping `prepare()` / Task / `parse_response()` themselves and tracking findings across iterations.

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
