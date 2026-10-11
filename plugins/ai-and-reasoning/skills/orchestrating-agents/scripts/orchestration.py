"""Compatibility shim: orchestrating-agents was renamed to orchestrating-chat-agents (2026-10-11).

Loads the real module from the sibling skill and re-exports it, so code that put
/mnt/skills/user/orchestrating-agents/scripts on sys.path keeps working.
"""

import importlib.util as _u
import sys as _sys
from pathlib import Path as _P

_dir = _P(__file__).resolve().parent.parent.parent / "orchestrating-chat-agents" / "scripts"
if not (_dir / "orchestration.py").exists():
    raise ImportError(f"orchestrating-agents is deprecated and its successor is missing: {_dir}/orchestration.py. "
                      "Install the orchestrating-chat-agents skill.")
if str(_dir) not in _sys.path:
    _sys.path.insert(0, str(_dir))  # the real modules import each other by bare name
_spec = _u.spec_from_file_location("_occa_orchestration", _dir / "orchestration.py")
_mod = _u.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
