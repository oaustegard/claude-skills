---
name: orchestrating-skills
description: >-
  Skill-aware orchestration with bash-mediated context routing. Decomposes complex
  tasks into skill-typed subtasks, extracts targeted context subsets without redundant
  reparsing, executes subagents in parallel with specialized instructions, and
  synthesizes results. Self-answers trivial subtasks inline. Use when tasks require
  multiple analytical perspectives (comparison + critique + synthesis), when context
  is large and subtasks only need portions, or when orchestrating-agents spawns too
  many redundant subagents.
metadata:
  version: 0.1.0
  depends_on:
    - orchestrating-agents
---

# Skill-Aware Orchestration

Orchestrate complex multi-step tasks through a four-phase pipeline that eliminates
redundant context processing and reflexive subagent spawning.

## When to Use

- Task requires **multiple analytical perspectives** (e.g., compare + critique + synthesize)
- Context is large and **subtasks only need portions** of it
- Simple subtasks should be **self-answered** without spawning subagents
- Current `orchestrating-agents` + `tiling-tree` pattern produces too many redundant calls

## When NOT to Use

- Single-skill tasks (just use the skill directly)
- Tasks requiring tool use or code execution (this is text-analysis orchestration)
- Real-time streaming requirements (this is batch-oriented)

## Quick Start

```python
import sys
sys.path.insert(0, "/mnt/skills/user/orchestrating-skills/scripts")
from orchestrate import orchestrate

result = orchestrate(
    context=open("report.md").read(),
    task="Compare the two proposed architectures, extract cost figures, and recommend one",
    verbose=True,
)
print(result["result"])
```

## Four-Phase Pipeline

### Phase 1: Planning (LLM)

The orchestrator reads the full context **once** and produces a JSON plan:

```json
{
  "subtasks": [
    {
      "task": "Compare architecture A vs B on scalability, cost, and complexity",
      "skill": "analytical_comparison",
      "context_pointers": {"sections": ["Architecture A", "Architecture B"]}
    },
    {
      "task": "Extract all cost figures and projections",
      "skill": "fact_extraction",
      "context_pointers": {"sections": ["Cost Analysis"]}
    },
    {
      "task": "What is the team's current headcount?",
      "skill": "self",
      "answer": "12 engineers (stated in paragraph 2)"
    }
  ]
}
```

Key behaviors:
- Assigns exactly one skill per subtask from the built-in library
- Uses `"self"` for trivial lookups (avoids spawning a subagent for simple questions)
- Context pointers use **section headers** (structural, edit-resilient) as primary method

### Phase 2: Assembly (Deterministic Code)

No LLM calls. The assembler:
1. Extracts context subsets using section headers or line ranges
2. Pairs each subset with the assigned skill's system prompt
3. Builds prompt dicts ready for `invoke_parallel`

### Phase 3: Execution (Parallel LLM)

Subagent prompts run in parallel via `orchestrating-agents.invoke_parallel`.
Each subagent receives **only its context slice** and **skill-specific instructions**.

### Phase 4: Synthesis (Deterministic Code + LLM)

1. Code collects results and interleaves self-answered results
2. A synthesizer LLM combines all results into a coherent response

## Built-in Skill Library

Eight task-oriented skills, each with specialized system prompt and output schema:

| Skill | Purpose | Self-answer ceiling |
|-------|---------|-------------------|
| `analytical_comparison` | Compare items along dimensions with trade-offs | 2 sentences |
| `fact_extraction` | Extract facts with source attribution | 3 sentences |
| `structured_synthesis` | Combine multiple sources into narrative | 1 sentence |
| `causal_reasoning` | Identify cause-effect chains | 1 sentence |
| `critique` | Evaluate arguments for soundness | 1 sentence |
| `classification` | Categorize items with rationale | 5 sentences |
| `summarization` | Produce concise summaries | 4 sentences |
| `gap_analysis` | Identify missing information | 2 sentences |

The self-answer ceiling determines when the orchestrator handles a subtask inline
rather than spawning a subagent.

## API Reference

### `orchestrate(context, task, **kwargs) -> dict`

Main entry point. Returns:

```python
{
    "result": "Final synthesized response",
    "plan": {...},           # Orchestrator's decomposition
    "subtask_count": 4,      # Total subtasks
    "self_answered": 1,      # Handled inline
    "delegated": 3,          # Sent to subagents
}
```

Parameters:
- `context` (str): Full context to process
- `task` (str): What to accomplish
- `model` (str): Claude model, default `claude-sonnet-4-6`
- `max_tokens` (int): Per-subagent token limit, default 4096
- `synthesis_max_tokens` (int): Synthesis token limit, default 8192
- `max_workers` (int): Parallel subagent limit, default 5
- `self_answer_ceiling` (int): Sentence threshold for self-answering, default 3
- `skills` (dict): Custom skill library (overrides built-in)
- `verbose` (bool): Print progress to stderr

### CLI

```bash
python orchestrate.py \
    --context-file report.md \
    --task "Analyze this report" \
    --verbose \
    --json
```

## Extending the Skill Library

Add custom skills by passing a dict to `orchestrate(skills=...)`:

```python
custom_skills = {
    "code_review": {
        "description": "Review code for bugs, style, and security",
        "system_prompt": "You are a code review specialist...",
        "output_hint": "issues_list with severity and fix suggestions",
        "self_answer_ceiling": 1,
    }
}

# Merge with built-in skills
from skill_library import SKILLS
all_skills = {**SKILLS, **custom_skills}

result = orchestrate(context=code, task="Review this PR", skills=all_skills)
```

## Architecture Details

See [references/architecture.md](references/architecture.md) for:
- Context pointer design decisions
- Self-answering heuristics
- Token efficiency analysis
- Comparison with SkillOrchestra (arXiv 2602.19672)
