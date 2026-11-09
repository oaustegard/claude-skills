"""Scores a program's place_points(): smallest pairwise distance / best known."""
import importlib.util
import itertools
import math
import os

BEST = (math.sqrt(6) - math.sqrt(2)) / 2


def evaluate(program_path):
    try:
        spec = importlib.util.spec_from_file_location("prog", program_path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        pts = [tuple(map(float, p)) for p in m.place_points()]
        if len(pts) != 8:
            return {"combined_score": 0.0, "error": f"expected 8 points, got {len(pts)}"}
        if any(not (-1e-9 <= c <= 1 + 1e-9) for p in pts for c in p):
            return {"combined_score": 0.0, "error": "a point lies outside the unit square"}
        d = min(math.dist(a, b) for a, b in itertools.combinations(pts, 2))
        out = {"combined_score": d / BEST, "min_distance": d}
        if os.environ.get("EVOLVE_SANDBOX_MARK"):
            out["sandbox_mark"] = os.environ["EVOLVE_SANDBOX_MARK"]
        return out
    except Exception as e:  # noqa: BLE001 - any program failure is a score of 0 with its message
        return {"combined_score": 0.0, "error": f"{type(e).__name__}: {e}"}
