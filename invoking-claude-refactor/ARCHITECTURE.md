# Architecture: Multi-Agent Coordination Patterns

## Overview

The enhanced skill supports three primary patterns, each with distinct use cases and characteristics.

## Pattern 1: Parallel API Analysis (Core Skill)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Main Claude Instance                        │
│                  (Your conversation context)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Multi-Agent Skill     │
                │  invoke_parallel()     │
                └────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Claude API     │ │  Claude API     │ │  Claude API     │
│  (Security)     │ │  (Performance)  │ │  (Quality)      │
│  Stateless      │ │  Stateless      │ │  Stateless      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Synthesized     │
                    │ Analysis        │
                    └─────────────────┘
```

**Characteristics:**
- ✓ Fast (concurrent API calls)
- ✓ Scalable (5-10 parallel agents)
- ✓ Cost-effective (with prompt caching)
- ✗ No tool access
- ✗ Stateless (no file operations)

**Best for:**
- Multi-perspective analysis
- Code reviews
- Document summarization
- Research synthesis

## Pattern 2: Streaming Parallel Analysis (New Enhancement)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Main Claude Instance                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────────┐
                │  Multi-Agent Skill         │
                │  invoke_parallel_streaming()│
                └────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Claude API     │ │  Claude API     │ │  Claude API     │
│  Stream         │ │  Stream         │ │  Stream         │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
    ╔════▼════╗         ╔════▼════╗         ╔════▼════╗
    ║callback1║         ║callback2║         ║callback3║
    ╚════╤════╝         ╚════╤════╝         ╚════╤════╝
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Real-time       │
                    │ Progress        │
                    └─────────────────┘
```

**Characteristics:**
- ✓ Real-time visibility
- ✓ Early error detection
- ✓ Better UX for long analyses
- ✓ Per-agent progress tracking
- ✗ Still no tool access

**Best for:**
- Long-running analyses
- Production monitoring
- Interactive workflows
- Multi-hour batch processing

## Pattern 3: Hybrid API + Agent SDK (Reference Architecture)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Main Claude Instance                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────────┐
                │  Multi-Agent Skill         │
                │  Orchestrator Logic        │
                └────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
            ▼ (ANALYSIS)                     ▼ (IMPLEMENTATION)
  ┌──────────────────┐              ┌──────────────────────┐
  │ invoke_parallel()│              │  Agent SDK Client    │
  └─────────┬────────┘              │  (External Tool)     │
            │                       └──────────┬───────────┘
    ┌───────┼───────┐                         │
    ▼       ▼       ▼                         ▼
  [API]   [API]   [API]              ┌──────────────────┐
    │       │       │                 │  WebSocket       │
    └───────┼───────┘                 │  Connection      │
            │                         └────────┬─────────┘
            ▼                                  │
    ┌─────────────────┐                       ▼
    │ Analysis Report │              ┌──────────────────────┐
    │ (Read-only)     │              │  E2B Sandbox         │
    └─────────┬───────┘              │  Agent SDK Instance  │
            │                        └──────────┬───────────┘
            │                                   │
            │                          ┌────────┴─────────┐
            │                          │                  │
            │                          ▼                  ▼
            │                    ┌──────────┐      ┌──────────┐
            │                    │  Tools   │      │  Tools   │
            │                    │  - bash  │      │  - files │
            │                    │  - git   │      │  - python│
            │                    └──────────┘      └──────────┘
            │                          │                  │
            │                          └────────┬─────────┘
            │                                   │
            │                                   ▼
            │                          ┌──────────────────┐
            │                          │ Implementation   │
            │                          │ (Files changed)  │
            └──────────────────────────┴──────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Complete Result │
                    └─────────────────┘
```

**Characteristics:**
- ✓ Best of both worlds
- ✓ Fast analysis (parallel API)
- ✓ Tool access for implementation
- ✗ Complex setup (requires external infrastructure)
- ✗ Higher operational cost

**Best for:**
- Complex multi-stage workflows
- Analysis → Implementation pipelines
- Large codebase operations
- Production system modifications

## Pattern Comparison Matrix

| Feature | Parallel API | Streaming | Hybrid + SDK |
|---------|-------------|-----------|--------------|
| **Concurrency** | ✓✓✓ High | ✓✓✓ High | ✓✓ Medium |
| **Speed** | ✓✓✓ Fast | ✓✓✓ Fast | ✓✓ Moderate |
| **Progress** | ✗ None | ✓✓✓ Real-time | ✓✓ Via callbacks |
| **Tool Access** | ✗ None | ✗ None | ✓✓✓ Full |
| **File Ops** | ✗ No | ✗ No | ✓✓✓ Yes |
| **Setup** | ✓✓✓ Simple | ✓✓✓ Simple | ✗ Complex |
| **Cost** | ✓✓ Low | ✓✓ Low | ✗ Higher |
| **State** | Stateless | Stateless | ✓ Persistent |

## Data Flow: Caching Strategy

### Without Caching (Expensive)
```
Agent 1: [Context 10K tokens] + [Task A] = 10,100 tokens × $0.003 = $0.0303
Agent 2: [Context 10K tokens] + [Task B] = 10,100 tokens × $0.003 = $0.0303
Agent 3: [Context 10K tokens] + [Task C] = 10,100 tokens × $0.003 = $0.0303
─────────────────────────────────────────────────────────────────────
Total: 30,300 tokens × $0.003 = $0.0909
```

### With Caching (Efficient)
```
Agent 1: [Context 10K tokens]* + [Task A] = 10,100 tokens
         Cache write: 10K × $0.003 = $0.030
         Regular: 100 × $0.003 = $0.0003
         Subtotal: $0.0303

Agent 2: [Context 10K tokens]✓ + [Task B] = 10,100 tokens
         Cache read: 10K × $0.0003 = $0.003
         Regular: 100 × $0.003 = $0.0003
         Subtotal: $0.0033

Agent 3: [Context 10K tokens]✓ + [Task C] = 10,100 tokens
         Cache read: 10K × $0.0003 = $0.003
         Regular: 100 × $0.003 = $0.0003
         Subtotal: $0.0033
─────────────────────────────────────────────────────────────────────
Total: $0.0369 (59% savings!)

* First agent creates cache
✓ Subsequent agents reuse cache
```

## Streaming Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Client Request                               │
│                invoke_parallel_streaming()                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌────────┐          ┌────────┐          ┌────────┐
    │Thread 1│          │Thread 2│          │Thread 3│
    └───┬────┘          └───┬────┘          └───┬────┘
        │                   │                   │
        ▼                   ▼                   ▼
    ┌────────┐          ┌────────┐          ┌────────┐
    │  API   │          │  API   │          │  API   │
    │ Stream │          │ Stream │          │ Stream │
    └───┬────┘          └───┬────┘          └───┬────┘
        │ chunk             │ chunk             │ chunk
        ▼                   ▼                   ▼
    ┌────────┐          ┌────────┐          ┌────────┐
    │callback│          │callback│          │callback│
    │   1    │          │   2    │          │   3    │
    └───┬────┘          └───┬────┘          └───┬────┘
        │                   │                   │
        ├─accumulate────────┼─accumulate────────┼─accumulate
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                    ┌─────────────────┐
                    │  Final Results  │
                    │  [resp1, resp2, │
                    │   resp3]        │
                    └─────────────────┘
```

## Interrupt Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Client Request                               │
│              invoke_parallel_interruptible()                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ InterruptToken  │
                    │  (shared flag)  │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌────────┐          ┌────────┐          ┌────────┐
    │Thread 1│          │Thread 2│          │Thread 3│
    │ check? │          │ check? │          │ check? │
    └───┬────┘          └───┬────┘          └───┬────┘
        │ not set           │ not set           │ not set
        ▼                   ▼                   ▼
    [Start]             [Start]             [Start]
        │                   │                   │
        │                   │                   │
    ┌───▼────────────────────────────────────────┐
    │         INTERRUPT EVENT                    │
    │       token.interrupt() called             │
    └───┬────────────────────────────────────────┘
        │
        ├───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
    ✓ complete          ● in-flight        ✗ not started
    return result       finish, return     return None
                        result
```

## Decision Tree

```
                    ┌─────────────────┐
                    │  Need to invoke │
                    │  Claude?        │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼ Need tools?                 ▼ Analysis only?
        ┌──────────┐                  ┌──────────┐
        │   YES    │                  │    NO    │
        └────┬─────┘                  └────┬─────┘
             │                              │
             ▼                              │
    ┌─────────────────┐                   │
    │ Use Agent SDK   │                   │
    │ (External)      │                   │
    │ - WebSocket     │                   │
    │ - E2B sandbox   │                   │
    └─────────────────┘                   │
                                          │
                                          ▼
                            ┌──────────────────────────┐
                            │ Need progress visibility?│
                            └──────────┬───────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │                             │
                        ▼ YES                         ▼ NO
              ┌──────────────────┐         ┌──────────────────┐
              │ invoke_parallel_ │         │ invoke_parallel()│
              │ streaming()      │         └──────────────────┘
              └──────────────────┘                   │
                        │                            │
                        │                            │
              ┌─────────▼────────────────────────────▼─────┐
              │ Need to cancel long operations?            │
              └─────────┬──────────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          │                           │
          ▼ YES                       ▼ NO
┌──────────────────────┐    ┌──────────────────────┐
│ invoke_parallel_     │    │ Use standard        │
│ interruptible()      │    │ functions           │
└──────────────────────┘    └──────────────────────┘
```

## Summary

The enhanced skill provides a progression of capabilities:

1. **Basic**: Parallel API calls (fast, simple)
2. **Enhanced**: Streaming + interrupt (production-ready)
3. **Advanced**: Hybrid with Agent SDK (tool-enabled)

Each pattern serves distinct use cases. Start with basic parallel, add streaming for visibility, and consider Agent SDK only when tools are essential.
