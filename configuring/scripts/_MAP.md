# scripts/
*Files: 2*

## Files

### __init__.py
- *No top-level symbols*

### getting_env.py
> Imports: `os, json, pathlib, typing`
- **detect_environment** (f) `()` :46
- **load_all** (f) `(force_reload: bool = False)` :410
- **get_env** (f) `(
    key: str,
    default: Optional[str] = None,
    *,
    required: bool = False,
    validator: Optional[Callable[[str], bool]] = None,
)` :472
- **load_env** (f) `(path: str | Path)` :518
- **mask_secret** (f) `(value: str, show_chars: int = 4)` :552
- **get_loaded_sources** (f) `()` :572
- **debug_info** (f) `()` :577

