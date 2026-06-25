#!/usr/bin/env python3
"""Parity pin: the bundled search.js and search.py must return identical results.

Both searchers are thin readers of the same neutral JSON index built by the
JS packer. This test builds a small bundle with build_lexkb.js, then runs both
searchers over several query shapes (plain, multi-expand, metadata filter, RM3)
and asserts identical (id, score) lists. Run from the skill directory:

    python3 test_parity.py

Exit 0 on full parity, 1 otherwise. Requires `node` and `python3` on PATH.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE / "scripts"

CORPUS = {
    "factions.txt": "Liberty is to faction what air is to fire. The latent causes of "
                    "faction are sown in the nature of man; controlling factions and "
                    "their majority or minority interests is the work of government.\n",
    "powers.txt": "The accumulation of all powers, legislative, executive, and judiciary, "
                  "in the same hands is the very definition of tyranny. Separation of "
                  "powers with checks and balances guards liberty.\n",
    "property.txt": "From the protection of different and unequal faculties of acquiring "
                    "property, the possession of different degrees and kinds of property "
                    "and economic inequality immediately results.\n",
}

QUERIES = [
    ["--query", "controlling factions", "--core", "factions", "--expand", "faction"],
    ["--query", "separation of powers", "--core", "powers", "--expand", "checks", "--expand", "balances"],
    ["--core", "property", "--expand", "wealth inequality", "--filter", "source_path~property"],
    ["--query", "liberty and faction", "--rm3", "--rm3-docs", "3"],
]


def run(cmd: list[str]) -> list[tuple]:
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"{cmd[:2]} failed: {out.stderr[:300]}")
    hits = json.loads(out.stdout)["hits"]
    return [(h["id"], h["score"]) for h in hits]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "corpus"
        corpus.mkdir()
        for name, text in CORPUS.items():
            (corpus / name).write_text(text, encoding="utf-8")
        bundle = Path(tmp) / "kb"
        subprocess.run(
            ["node", str(SCRIPTS / "build_lexkb.js"), str(corpus),
             "--ext", "txt", "--out", str(bundle), "--target-chars", "0"],
            check=True, capture_output=True, text=True,
        )

        all_ok = True
        for q in QUERIES:
            js = run(["node", str(bundle / "search.js"), "--index", str(bundle), *q, "--k", "5"])
            py = run(["python3", str(bundle / "search.py"), "--index", str(bundle), *q, "--k", "5"])
            ok = js == py
            all_ok &= ok
            print(("OK   " if ok else "DIFF ") + " ".join(q))
            if not ok:
                print("  js:", js)
                print("  py:", py)

    print("\nPARITY:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
