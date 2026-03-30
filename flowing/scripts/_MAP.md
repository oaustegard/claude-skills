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
)` :90
- **Flow** (C) :210
  - **__init__** (m) `(self, *terminals: TaskDef, max_workers: int = 5, fail_fast: bool = True)` :211
  - **_collect_tasks** (m) `(self)` :220
  - **_build_layers** (m) `(self, tasks: set[TaskDef])` :234
  - **_execute** (m) `(self, layers: list[list[TaskDef]], skip_succeeded: bool = False)` :262
  - **_execute_detached** (m) `(self, detached_tasks: set[TaskDef])` :306
  - **run** (m) `(self)` :349
  - **resume** (m) `(self)` :379
  - **override** (m) `(self, td: TaskDef, value: Any)` :413
  - **value** (m) `(self, td: TaskDef)` :421
  - **summary** (m) `(self)` :429
  - **_all_task_defs** (m) `(self)` :443

