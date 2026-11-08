"""Install the numeric dependencies on first use: plain pip, then --user, then --break-system-packages.

A routine's container is not composed by the claude-workspace boot, so nothing can be assumed installed.
"""
from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys

NEEDED = {"numpy": "numpy", "onnxruntime": "onnxruntime", "tokenizers": "tokenizers", "sklearn": "scikit-learn"}


def ensure():
    missing = [pkg for mod, pkg in NEEDED.items() if importlib.util.find_spec(mod) is None]
    if not missing:
        return []
    base = [sys.executable, "-m", "pip", "install", "-q", *missing]
    for extra in ([], ["--user"], ["--break-system-packages"]):
        if subprocess.run(base + extra, capture_output=True, text=True, check=False).returncode == 0:
            importlib.invalidate_caches()
            return missing
    raise RuntimeError(f"could not pip-install {missing}")
