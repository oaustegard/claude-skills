# scripts/
*Files: 1*

## Files

### flowing.py
> Imports: `sys, time, traceback, concurrent.futures, dataclasses`...
- **StepState** (C) :48
- **task** (f) `(
    fn: Optional[Callable] = None,
    *,
    depends_on: Optional[list[TaskDef]] = None,
    retry: int = 0,
    retry_backoff_base_ms: int = 1000,
    retry_max_backoff_ms: int = 30_000,
    timeout_s: Optional[float] = None,
    name: Optional[str] = None,
    detached: bool = False,
)` :89
- **Flow** (C) :208
  - **__init__** (m) `(self, *terminals: TaskDef, max_workers: int = 5, fail_fast: bool = True)` :209
  - **_collect_tasks** (m) `(self)` :218
  - **_build_layers** (m) `(self, tasks: set[TaskDef])` :232
  - **_execute** (m) `(self, layers: list[list[TaskDef]], skip_succeeded: bool = False)` :260
  - **_execute_detached** (m) `(self, detached_tasks: set[TaskDef])` :304
  - **run** (m) `(self)` :347
  - **resume** (m) `(self)` :377
  - **override** (m) `(self, td: TaskDef, value: Any)` :411
  - **value** (m) `(self, td: TaskDef)` :419
  - **summary** (m) `(self)` :427
  - **_all_task_defs** (m) `(self)` :441

