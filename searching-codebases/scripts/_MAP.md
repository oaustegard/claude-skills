# scripts/
*Files: 3*

## Files

### code_rag.py
> Imports: `os, re, sys, json, time`...
- **main** (f) `()` :566

### flowing.py
> Imports: `sys, time, traceback, concurrent.futures, dataclasses`...
- **StepState** (C) :36
- **task** (f) `(
    fn: Optional[Callable] = None,
    *,
    depends_on: Optional[list[TaskDef]] = None,
    retry: int = 0,
    retry_backoff_base_ms: int = 1000,
    retry_max_backoff_ms: int = 30_000,
    timeout_s: Optional[float] = None,
    name: Optional[str] = None,
)` :76
- **Flow** (C) :193
  - **__init__** (m) `(self, *terminals: TaskDef, max_workers: int = 5, fail_fast: bool = True)` :194
  - **run** (m) `(self)` :202
  - **value** (m) `(self, td: TaskDef)` :282
  - **summary** (m) `(self)` :290

### pipeline.py
> Imports: `argparse, os, re, shutil, subprocess`...
- **PipelineConfig** (C) :99
  - **__init__** (m) `(self, args: argparse.Namespace)` :100
- **main** (f) `()` :373

