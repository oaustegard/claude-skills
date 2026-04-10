---
name: challenging
description: Adversarial review of Muninn's own outputs before delivery. Use when producing deliverables that benefit from hostile second-pass review — blog posts, technical recommendations, analysis briefs, code, or any artifact where accuracy and rigor matter more than speed. Triggers on "challenge this", "review before shipping", "adversarial pass", "stress test", or when the task profile warrants automatic review.
metadata:
  version: 0.2.0
---

# Challenging — Adversarial Review

Cross-model adversarial review for deliverables. Different model reviews with fresh context — no shared blind spots, no accumulated goodwill.

Inspired by VDD (dollspace.gay) and Grainulation's anti-rationalization patterns.

## Profiles

Pick the profile matching your artifact. **Read only the profile you need** — each is self-contained with its own persona, anti-rationalization table, evaluation criteria, and adversary system prompt.

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
    context='Blog post about RAG scaling laws for muninn.austegard.com'
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

## Adversary

Default: Gemini Pro (cross-model). Alternate: `adversary='claude'` (Opus sub-agent).
