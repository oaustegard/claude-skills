---
name: challenging
description: Cross-model adversarial review for deliverables before shipping. Use when producing blog posts, technical recommendations, analysis briefs, code, or any artifact where accuracy matters more than speed. Triggers on "challenge this", "review before shipping", "adversarial pass", "stress test this".
metadata:
  version: 0.6.0
---

# Challenging — Adversarial Review

Cross-model adversarial review. A different model reviews your output with fresh context — no shared blind spots, no accumulated goodwill.

Inspired by VDD (dollspace.gay) and Grainulation's anti-rationalization patterns.

## Profiles

Pick the profile matching your artifact. **Read only the profile you need** — each is self-contained with persona, anti-rationalization table, evaluation criteria, and adversary system prompt.

| Profile | Use For | File |
|---------|---------|------|
| `prose` | Blog posts, essays, articles | `references/prose.md` |
| `analysis` | Research briefs, comparisons, synthesis | `references/analysis.md` |
| `code` | Scripts, implementations, PRs | `references/code.md` |
| `recommendation` | Technical decisions, architecture choices | `references/recommendation.md` |

## Usage

```python
import sys
sys.path.insert(0, '/mnt/skills/user/challenging/scripts')
from challenger import challenge

result = challenge(
    artifact=open('/home/claude/draft.md').read(),
    profile='prose',
    context='Blog post about RAG scaling laws'
)
print(result['verdict'])    # SHIP | REVISE | RETHINK
print(result['findings'])   # List of specific issues
print(result['strengths'])  # What to preserve
```

## Modes

- **advisory** (default): Single adversary pass. Fast.
- **blocking**: Loop until clean or confabulation threshold. For high-stakes artifacts.

```python
result = challenge(artifact, profile='analysis', mode='blocking', max_iterations=3)
```

Blocking exits when: (a) no genuine findings, (b) adversary FP rate > 75% (inventing problems — artifact is clean), or (c) max iterations.

## Verdicts

- **SHIP**: Clean. Deliver.
- **REVISE**: Real issues, sound core. Fix and deliver.
- **RETHINK**: Structural problems. Reconsider approach.

## Severity Levels

- **critical/high/medium/low**: Standard severity — actionable findings that block in blocking mode.
- **unverifiable**: Adversary flagged something it doesn't recognize (API, pattern, model name) but can't confirm is wrong. Surfaced for awareness but does not block SHIP. Use `context` to ground the adversary on APIs/patterns it may not know.

## Adversary Selection

Default: Gemini 3.1 Pro (cross-model diversity). Alternate: `adversary='claude'` (Opus sub-agent).

## Credentials

The script loads credentials automatically from environment or project files:

- **Gemini via Cloudflare Gateway** (preferred): `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`, `CF_API_TOKEN` from env or `proxy.env`
- **Gemini direct**: `GOOGLE_API_KEY` from env
- **Claude sub-agent**: `ANTHROPIC_API_KEY` or `API_KEY` from env or `claude.env`

No external skill dependencies. Uses `requests` (standard in most environments) for API calls.
