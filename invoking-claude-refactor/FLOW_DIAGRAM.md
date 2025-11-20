# Implementation Flow Diagram

## Critical Path Overview

```
START
  │
  ├─[1] SETUP & RENAME (5 min)
  │   ├─ Rename directory
  │   ├─ Update SKILL.md metadata
  │   └─ Verify environment
  │
  ├─[2] CORE STREAMING (20 min) ⭐ CRITICAL
  │   ├─ invoke_claude_streaming()
  │   ├─ _build_messages() helper
  │   ├─ invoke_parallel_streaming()
  │   └─ Test immediately ✓
  │
  ├─[3] INTERRUPT SUPPORT (15 min)
  │   ├─ InterruptToken class
  │   ├─ invoke_parallel_interruptible()
  │   └─ Test immediately ✓
  │
  ├─[4] DOCUMENTATION (15 min)
  │   ├─ Streaming examples
  │   ├─ Function reference
  │   └─ Agent SDK section
  │
  ├─[5] TEST SUITE (20 min)
  │   ├─ test_streaming.py
  │   ├─ test_interrupt.py
  │   └─ test_integration.py updates
  │
  └─[6] FINALIZE (10 min)
      ├─ MIGRATION.md
      ├─ Final verification
      └─ Package ✓
  │
END (85 min total)
```

## Dependencies Graph

```
Environment Setup
      │
      ├─────────────┐
      ▼             ▼
  Rename Skill   Verify anthropic
      │             │
      └──────┬──────┘
             ▼
    ┌─────────────────┐
    │ Update SKILL.md │
    └────────┬────────┘
             │
             ├──────────────────┐
             ▼                  ▼
    ┌─────────────────┐  ┌─────────────────┐
    │   Streaming     │  │  Documentation  │
    │ Implementation  │  │   (parallel)    │
    └────────┬────────┘  └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │   Test Stream   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │    Interrupt    │
    │ Implementation  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Test Interrupt  │
    └────────┬────────┘
             │
             ├──────────────────┐
             ▼                  ▼
    ┌─────────────────┐  ┌─────────────────┐
    │  Full Test      │  │   Migration     │
    │  Suite          │  │   Guide         │
    └────────┬────────┘  └─────────┬───────┘
             │                     │
             └──────────┬──────────┘
                        ▼
                  ┌──────────┐
                  │  DONE ✓  │
                  └──────────┘
```

## Parallel Execution Opportunities

```
┌──────────────────────────────────────────────────────────────┐
│                      PHASE 1-2                               │
│            (Sequential - Critical Path)                      │
│    Setup → Rename → Streaming Implementation → Test         │
└──────────────────┬───────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
  ┌──────────┐          ┌──────────┐
  │ PHASE 3  │          │ PHASE 4  │
  │Interrupt │          │   Docs   │
  │  Code    │          │  Write   │
  └────┬─────┘          └────┬─────┘
       │                     │
       └──────────┬──────────┘
                  │
                  ▼
        ┌─────────────────┐
        │    PHASE 5-6    │
        │   Test & Final  │
        └─────────────────┘
```

**Note:** Phases 3 and 4 can be done in parallel if working with multiple sessions.

## Function Dependency Tree

```
invoke_claude() [existing]
      │
      ├──────────────┐
      │              │
      ▼              ▼
_format_system_   _format_message_
with_cache()      with_cache()
      │              │
      └──────┬───────┘
             │
             ├─────────────────────┐
             │                     │
             ▼                     ▼
    invoke_claude_          _build_messages()
    streaming() [NEW]             [NEW]
             │                     │
             └──────┬──────────────┘
                    │
                    ▼
        invoke_parallel_streaming()
                  [NEW]
```

```
ThreadPoolExecutor [Python stdlib]
        │
        ├──────────────┐
        │              │
        ▼              ▼
invoke_parallel()  InterruptToken [NEW]
   [existing]          │
                       │
                       ▼
           invoke_parallel_interruptible()
                     [NEW]
```

## Testing Pyramid

```
                    ▲
                   ╱ ╲
                  ╱   ╲
                 ╱  E  ╲         E = End-to-End (Real workflows)
                ╱───────╲
               ╱         ╲
              ╱     I     ╲      I = Integration (Test suite)
             ╱─────────────╲
            ╱               ╲
           ╱        U        ╲   U = Unit (Individual functions)
          ╱───────────────────╲
         ╱                     ╲
        ╱          S            ╲ S = Syntax (Import checks)
       ╱─────────────────────────╲
      ╱                           ╲
     ▼                             ▼
   START                         DONE

Test Order: S → U → I → E
Time Split: 5min, 10min, 15min, 20min
```

## Code Addition Locations

```
scripts/claude_client.py
│
├─ Line 1-35: Imports [existing]
│
├─ Line 36-42: ClaudeInvocationError [existing]
│
├─ Line 43-150: Helper functions [existing]
│
├─ Line 151-200: invoke_claude() [existing]
│
├─ 🆕 NEW SECTION A (~line 201)
│  ├─ invoke_claude_streaming()     [50 lines]
│  ├─ _build_messages()             [10 lines]
│  └─ invoke_parallel_streaming()   [60 lines]
│
├─ Line 201-300: invoke_parallel() [existing]
│
├─ 🆕 NEW SECTION B (~line 301)
│  ├─ InterruptToken class          [15 lines]
│  └─ invoke_parallel_interruptible() [50 lines]
│
├─ Line 301-400: ConversationThread [existing]
│
└─ Line 401-519: Helper methods [existing]
```

## Risk Mitigation Flow

```
┌─────────────────┐
│ Implement Code  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ╔════════════╗
│ Syntax Check?   ├────→║    FAIL    ║
└────────┬────────┘     ╚════╤═══════╝
         │                   │
         ▼ PASS              ▼
┌─────────────────┐     Fix syntax errors
│ Import Test?    ├────→Review code
└────────┬────────┘     Re-test
         │                   │
         ▼ PASS              │
┌─────────────────┐     ╔════╧═══════╗
│ Unit Test?      ├────→║   RETRY    ║
└────────┬────────┘     ╚════╤═══════╝
         │                   │
         ▼ PASS              │
┌─────────────────┐          │
│ Integration?    ├──────────┘
└────────┬────────┘
         │
         ▼ PASS
┌─────────────────┐
│   SUCCESS ✓     │
└─────────────────┘
```

## Time Allocation

```
PHASE 1: Setup & Rename           █░░░░ (5 min)
PHASE 2: Streaming                 ████░ (20 min) ⭐
PHASE 3: Interrupt                 ███░░ (15 min)
PHASE 4: Documentation             ███░░ (15 min)
PHASE 5: Testing                   ████░ (20 min)
PHASE 6: Finalization             ██░░░ (10 min)
                                   ─────────────
Total:                             85 minutes

Critical Path: Phases 1→2→3→5→6   (70 min)
Parallel Option: Phase 4          (15 min saved if parallel)
Minimum Viable: Phases 1→2        (25 min, streaming only)
```

## Decision Points

```
                START
                  │
                  ▼
        ┌──────────────────┐
        │ Full Enhancement │
        │  or Minimal?     │
        └─────────┬────────┘
                  │
       ┌──────────┴──────────┐
       │                     │
       ▼                     ▼
   [FULL]                [MINIMAL]
       │                     │
       ├─ Streaming          ├─ Streaming only
       ├─ Interrupt          └─ Skip rest
       ├─ Documentation          (25 min)
       └─ Full tests
          (85 min)
```

## Checkpoint Validation

```
After Phase 2:
  python3 -c "from scripts.claude_client import invoke_claude_streaming; print('✓')"

After Phase 3:
  python3 -c "from scripts.claude_client import InterruptToken; print('✓')"

After Phase 5:
  python3 scripts/test_streaming.py && echo "✓"

After Phase 6:
  ls -la MIGRATION.md && echo "✓"
```

## Emergency Rollback Points

```
Checkpoint 1: After rename
  └─ Rollback: Rename directory back

Checkpoint 2: After streaming
  └─ Rollback: git checkout scripts/claude_client.py

Checkpoint 3: After interrupt
  └─ Rollback: git checkout scripts/claude_client.py

Checkpoint 4: Complete
  └─ Rollback: Restore from backup
```

## Success Indicators

```
✓ All imports work               [MUST HAVE]
✓ Existing tests pass             [MUST HAVE]
✓ New tests pass                  [MUST HAVE]
✓ Streaming returns correct data  [MUST HAVE]
✓ Callbacks receive chunks        [SHOULD HAVE]
✓ Interrupt stops execution       [SHOULD HAVE]
✓ Documentation clear             [SHOULD HAVE]
✓ Examples run                    [NICE TO HAVE]
```

---

**Quick Start:** Begin at Phase 1 in EXECUTION_PLAN.md. Use this diagram to track progress and understand dependencies.
