# Architecture: Skill-Aware Orchestration

## Problem Statement

The existing `orchestrating-agents` + `tiling-tree` pattern exhibits two inefficiencies
identified in SkillOrchestra (arXiv 2602.19672):

1. **Reflexive spawning**: Every leaf task spawns a subagent regardless of difficulty.
   The orchestrator never self-answers, even for trivial lookups.

2. **Context re-processing**: Each subagent independently reparses the full context,
   wasting tokens on redundant work. For N subagents with context C, total context
   processing is O(N*C) instead of O(C + N*c_i) where c_i << C.

## Design Decisions

### Context Pointers: Section Headers as Primary

Three options were considered:

| Method | Pros | Cons |
|--------|------|------|
| Section headers | Structural, edit-resilient, human-readable | Requires markdown headers |
| Line ranges | Works on any text, precise | Brittle to edits, opaque |
| Hybrid | Best of both | More complex pointer format |

**Decision**: Section headers as primary, line ranges as fallback.

Rationale: Most context in Claude workflows is markdown or markdown-like. Section
headers are resilient to line insertions/deletions and readable in the orchestrator
plan JSON. Line ranges serve as escape hatch for headerless content.

Implementation in `assembler.py`:
- `extract_sections()` matches headers case-insensitively, captures content through
  next equal-or-higher-level header
- `extract_lines()` uses 1-indexed inclusive ranges
- `extract_context_subset()` tries sections first, then line ranges, falls back to
  full context

### Self-Answering Heuristics

The orchestrator uses a **sentence ceiling** per skill to decide whether to self-answer:

```
If estimated_answer_length < skill.self_answer_ceiling sentences:
    Use skill="self" and provide inline answer
Else:
    Delegate to subagent
```

Ceilings vary by skill complexity:
- `classification` (5): Simple categorization often needs one word
- `summarization` (4): Brief summaries can be inline
- `fact_extraction` (3): Single-fact lookups are trivial
- `analytical_comparison` (2): Even short comparisons benefit from structure
- `critique`, `causal_reasoning`, `structured_synthesis` (1): Almost always needs depth

The orchestrator LLM makes this judgment during planning. The ceiling is guidance,
not a hard rule — the LLM can override based on context complexity.

### Skill Granularity: Broad Taxonomy

**Decision**: 8 broad skills covering analytical primitives.

Rationale: The orchestrator LLM has limited attention budget for skill selection.
A library of 6-8 well-defined skills is matchable in a single pass. Fine-grained
libraries (50+ skills) require multi-hop retrieval that defeats the "touch context
once" principle.

The 8 skills cover the analytical primitives that compose into complex tasks:

```
fact_extraction    → What does the context say?
summarization      → What's the gist?
classification     → What category does this fall into?
analytical_comparison → How do X and Y compare?
causal_reasoning   → Why did X happen? What follows from Y?
critique           → Is this argument sound?
gap_analysis       → What's missing?
structured_synthesis → How do these pieces fit together?
```

Custom skills can be added via the `skills` parameter without modifying the library.

### Token Efficiency Analysis

For a task with context C (tokens) decomposed into N subtasks:

**Without orchestration** (naive parallel):
```
Total context tokens = N * C  (each subagent gets full context)
```

**With skill-aware orchestration**:
```
Phase 1: C (orchestrator reads once)
Phase 2: 0 (deterministic code)
Phase 3: Σ c_i where c_i = context slice for subtask i
Phase 4: Σ r_i (response collection) + synthesis prompt

Total ≈ C + Σ c_i + Σ r_i
```

If context slices average 30% of full context:
- Naive: 5 * 10K = 50K context tokens
- Orchestrated: 10K + 5 * 3K = 25K context tokens (50% reduction)

Self-answering further reduces by eliminating subagent calls entirely for
trivial subtasks.

## Pipeline Flow

```
┌─────────────────────────────────────────────┐
│ Phase 1: Orchestrator (LLM)                 │
│                                             │
│ Input: Full context + task                  │
│ Output: JSON plan with skill assignments    │
│                                             │
│ - Reads context ONCE                        │
│ - Decomposes into 1-6 subtasks             │
│ - Assigns skills from library               │
│ - Self-answers trivial subtasks inline      │
│ - Specifies context pointers per subtask    │
└──────────────────┬──────────────────────────┘
                   │ JSON plan
                   ▼
┌─────────────────────────────────────────────┐
│ Phase 2: Assembler (Deterministic Code)     │
│                                             │
│ For each delegated subtask:                 │
│ 1. Extract context subset via pointers      │
│ 2. Look up skill system prompt              │
│ 3. Build prompt dict for invoke_parallel    │
│                                             │
│ NO LLM CALLS                               │
└──────────────────┬──────────────────────────┘
                   │ Prompt dicts
                   ▼
┌─────────────────────────────────────────────┐
│ Phase 3: Subagents (Parallel LLM)           │
│                                             │
│ invoke_parallel() with:                     │
│ - Targeted context slices (not full)        │
│ - Skill-specific system prompts             │
│ - Low temperature (0.3) for consistency     │
└──────────────────┬──────────────────────────┘
                   │ Responses
                   ▼
┌─────────────────────────────────────────────┐
│ Phase 4: Collection + Synthesis             │
│                                             │
│ Code: Interleave self-answers + responses   │
│ LLM:  Synthesize into coherent final answer │
└─────────────────────────────────────────────┘
```

## Comparison with SkillOrchestra

This implementation adapts the SkillOrchestra approach (arXiv 2602.19672) to Claude's
skill system with key differences:

| Aspect | SkillOrchestra | This Skill |
|--------|---------------|------------|
| Skill source | Learned from training data | Explicit skill library with system prompts |
| Context routing | Embedding-based retrieval | Structural extraction (headers/lines) |
| Self-answering | Confidence threshold | Sentence ceiling per skill type |
| Parallelism | Framework-dependent | ThreadPoolExecutor via orchestrating-agents |
| Extensibility | Requires retraining | Pass custom skill dict at runtime |

## Error Handling

- **Orchestrator produces invalid JSON**: `invoke_claude_json` retries with fence-stripping
- **Unknown skill in plan**: Falls back to generic "helpful assistant" system prompt
- **Subagent failure**: `invoke_parallel` raises `ClaudeInvocationError`; caller can
  retry or degrade gracefully
- **Empty context slice**: If section headers don't match, falls back to full context
  (logged as warning in verbose mode)
