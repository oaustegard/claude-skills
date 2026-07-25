"""Template registry. Each module in this package registers one or more named
templates via the @register decorator. build.py looks them up here.
"""

from __future__ import annotations

from typing import Callable

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
from . import exploration   # noqa: E402,F401
from . import review        # noqa: E402,F401
from . import design        # noqa: E402,F401
from . import prototype     # noqa: E402,F401
from . import diagram       # noqa: E402,F401
from . import deck          # noqa: E402,F401
from . import research      # noqa: E402,F401
from . import report        # noqa: E402,F401
from . import editor        # noqa: E402,F401
from . import freeform      # noqa: E402,F401
