---
name: challenging
description: Adversarial review of Muninn's own outputs before delivery. Use when producing deliverables that benefit from hostile second-pass review — blog posts, technical recommendations, analysis briefs, code, or any artifact where accuracy and rigor matter more than speed. Triggers on "challenge this", "review before shipping", "adversarial pass", "stress test", or when the task profile warrants automatic review.
metadata:
  version: 0.1.0
---

# Challenging — Adversarial Review

Cross-model adversarial review for Muninn's deliverables. Inspired by dollspace.gay's VDD methodology and Grainulation's anti-rationalization patterns.

## Core Principle

Use a **different model** to review. Self-review shares blind spots. Cross-model review introduces genuine cognitive diversity.

- **Builder**: Claude (Muninn, the current conversation)
- **Adversary**: Gemini 3 Pro (default) or Claude Opus via sub-agent (alternate)
- **Fresh context every pass**: The adversary never accumulates goodwill

## When to Use

**Always use for:**
- Blog posts before publishing
- Technical recommendations that drive decisions
- Analysis briefs synthesizing multiple sources

**Consider for:**
- Code that will ship to production repos
- Skill definitions before packaging
- Any deliverable where Oskar said "make sure this is right"

**Skip for:**
- Quick answers, conversational responses
- Exploratory drafts explicitly marked as rough
- Tasks where speed dominates accuracy

## Quick Start

```python
import sys
sys.path.insert(0, '/mnt/skills/user/challenging/scripts')
from challenger import challenge

# Returns verdict dict with findings and recommendation
result = challenge(
    artifact=open('/home/claude/draft.md').read(),
    profile='prose',           # prose | analysis | code | recommendation
    context='Blog post about RAG scaling laws for muninn.austegard.com'
)
print(result['verdict'])       # SHIP | REVISE | RETHINK
print(result['findings'])      # List of specific issues
print(result['strengths'])     # What to preserve
```

## Profiles

Each profile carries task-specific anti-rationalization rules and evaluation criteria. Load profile details from `references/profiles.md`.

| Profile | Use For | Adversary Focus |
|---------|---------|-----------------|
| `prose` | Blog posts, essays, articles | Claims without evidence, buried lede, false balance, explaining the subtext |
| `analysis` | Research briefs, comparisons, synthesis | Cherry-picking, missing perspectives, confidence inflation, circular sourcing |
| `code` | Scripts, implementations, PRs | Logic errors, edge cases, security, error handling theater |
| `recommendation` | Technical decisions, architecture choices | Unstated assumptions, missing alternatives, reversibility blindness |

## Verdict Protocol

Every challenge produces exactly one verdict:

| Verdict | Meaning | Action |
|---------|---------|--------|
| `SHIP` | No genuine issues found. Adversary may have nitpicked. | Deliver as-is. |
| `REVISE` | Real issues found but core is sound. | Apply targeted fixes, then deliver. |
| `RETHINK` | Structural problems. Fixing details won't help. | Reconsider approach before continuing. |

## Multi-Pass Mode

For high-stakes deliverables, run iterative passes:

```python
result = challenge(
    artifact=content,
    profile='analysis',
    context='Decision brief for infrastructure migration',
    mode='blocking',        # 'advisory' (default, single pass) or 'blocking' (loop)
    max_iterations=3
)
```

**Blocking mode** loops until:
1. **Clean pass**: No genuine findings → SHIP
2. **Confabulation threshold**: Adversary's false-positive rate exceeds 75% → the adversary is inventing problems, the artifact is clean
3. **Max iterations reached**: Stop and report best state

This exit strategy comes from VDD: when a hyper-critical reviewer is forced to fabricate problems, the work is done.

## Integration with Existing Workflows

**Story Forge**: Story Forge already has Opus editorial + Gemini fresh-eyes. Challenging doesn't replace that — it covers the non-fiction deliverables that Story Forge doesn't touch.

**Blog publishing**: Run `challenge(profile='prose')` before `blog_publish()`.

**PR workflow**: Run `challenge(profile='code')` before creating the PR.
