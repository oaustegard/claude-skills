"""Template registry. Each module in this package registers one or more named
templates via the @register decorator. build.py looks them up here.
"""

from __future__ import annotations

from collections.abc import Callable

REGISTRY: dict[str, dict] = {}


def register(name: str, *, summary: str, spec_keys: dict[str, str]) -> Callable:
    """Decorate a builder function ``f(spec: dict) -> str`` (returns the body
    HTML; composer.page() wraps it).

    summary: one-line description shown by ``build.py list``.
    spec_keys: ``{key: description}`` shown by ``build.py describe``.
    """
    def deco(fn):
        REGISTRY[name] = {"build": fn, "summary": summary, "spec_keys": spec_keys}
        return fn
    return deco


# Importing the modules below triggers the @register side-effects.
from . import (
    deck,  # noqa: F401
    design,  # noqa: F401
    diagram,  # noqa: F401
    editor,  # noqa: F401
    exploration,  # noqa: F401
    freeform,  # noqa: F401
    prototype,  # noqa: F401
    report,  # noqa: F401
    research,  # noqa: F401
    review,  # noqa: F401
)
