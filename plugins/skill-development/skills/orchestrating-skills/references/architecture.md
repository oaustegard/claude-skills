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

**v0.1.0** used per-skill sentence count ceilings. This was dropped in v0.2.0
because:

1. The planner LLM ignored the ceilings in practice (0 self-answers on test doc)
2. Sentence counts are a poor proxy for task complexity — a 2-sentence causal
   chain is harder than a 5-sentence list of facts
3. The ceiling was a coarse Python parameter trying to encode what should be an
   agentic judgment call

**v0.2.0** gives the planner clear criteria instead:

> Use "self" when the answer is a direct lookup — a number, a name, a date,
> a definition — that requires no reasoning, analysis, or comparison. If you
> already know the answer from reading the context, include it inline.

This produces correct self-answering behavior: on a mixed task with 3 lookups
and 1 analytical comparison, the planner self-answered the 3 lookups and
delegated only the comparison.

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
| Self-answering | Confidence threshold | LLM judgment (lookup vs. analysis) |
| Parallelism | Framework-dependent | ThreadPoolExecutor + httpx (no SDK) |
| Extensibility | Requires retraining | Pass custom skill dict at runtime |

## Error Handling

- **Orchestrator produces invalid JSON**: `call_claude_json` strips markdown fences before parsing
- **Unknown skill in plan**: Falls back to generic "helpful assistant" system prompt
- **Subagent failure**: `httpx` raises on HTTP errors; `call_parallel` propagates exceptions
- **Empty context slice**: If section headers don't match, falls back to full context
