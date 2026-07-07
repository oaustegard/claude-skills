---
name: reasoning-semiformally
version: 0.3.0
description: Apply semi-formal certificate reasoning to code analysis — patch verification, fault localization, patch equivalence. Use when reviewing patches, hunting bugs across scopes, comparing fixes, or when code reasoning requires tracing execution across files/modules. Triggers on code review, bug localization, patch comparison, name shadowing, scope analysis, regression checking.
---

# Semi-Formal Code Reasoning

Structured certificate templates that force mandatory checkpoints before conclusions.

## Skip Conditions

Do NOT apply semi-formal reasoning when:
- The change is trivial: docs, formatting, version bumps, config changes
- The bug is locally obvious: typo, off-by-one in the same function, missing comma
- No execution paths cross scope boundaries
- The task is not code analysis (text editing, data extraction, summarization)

If any skip condition is met, proceed with standard reasoning.

## Model-Specific Instructions

**If you are Haiku-class (Haiku 4.5 or similar):**
Read `haiku.md` in this skill directory. It contains full procedural templates with worked examples.

**If you are Sonnet-class or above (Sonnet 4.6, Opus):**
Read `sonnet.md` in this skill directory. It contains compact verification checkpoints.

## Composing Tasks

For complex tasks, apply templates sequentially:
1. **Fault localization** to find the bug
2. **Patch verification** to validate a proposed fix
3. **Patch equivalence** to compare alternative fixes

Each output feeds the next as premises.
