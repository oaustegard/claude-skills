"""Tests for the binding-resolved (python-lsp) tier of searching-codebases.

Round-trips against a small multi-file fixture driving a real
``pyright-langserver``, and exercises the mandatory soft-fallback contract.

Run: python -m pytest searching-codebases/tests/test_lsp_refs.py -v
Or:  python searching-codebases/tests/test_lsp_refs.py   (standalone)

The semantic tests require pyright (and system node); they are skipped if the
bootstrap can't make pyright available. The fallback tests have no such
dependency — they assert the degradation path.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lsp_refs  # noqa: E402
from lsp_refs import (  # noqa: E402
    LspUnavailable,
    definition_sites,
    lsp_query,
    occurrence_sites,
)

FIXTURE = str(Path(__file__).parent / "fixture")


def _pyright_available() -> bool:
    try:
        lsp = lsp_refs._import_lsp_client()
        lsp.ensure_pyright(install=True)
        return True
    except Exception:
        return False


pyright = pytest.mark.skipif(not _pyright_available(),
                             reason="pyright/node unavailable")


def _pyright_proc_count() -> int:
    out = subprocess.run(["pgrep", "-f", "pyright-langserver"],
                         capture_output=True, text=True).stdout
    return len([ln for ln in out.splitlines() if ln.strip()])


# ── symbol → position resolution (no server) ─────────────────────────────────

def test_definition_sites_finds_both_helpers():
    sites = definition_sites(FIXTURE, "helper")
    by_file = {s.file: s for s in sites}
    assert "pkg/models.py" in by_file and "pkg/other.py" in by_file
    # Column lands on the symbol token, not the `def` keyword (1-based).
    assert by_file["pkg/models.py"].col == 5  # "def helper" -> h at col 5
    assert by_file["pkg/models.py"].line == 9


def test_occurrence_sites_are_a_superset():
    occ = occurrence_sites(FIXTURE, "helper")
    files = {s.file for s in occ}
    # Text matching catches all three files (including the unrelated other.py).
    assert {"pkg/models.py", "pkg/other.py", "pkg/service.py"} <= files


# ── binding-resolved queries (the win over regex) ────────────────────────────

@pyright
def test_references_exclude_unrelated_same_named_symbol():
    result = lsp_query(FIXTURE, "helper", op="references")
    groups = {g["anchor"].file: g for g in result["results"]}
    # The models.py binding's references include its def and the use in
    # service.py, but EXCLUDE the unrelated helper in other.py.
    models = {Path(loc.path).name for loc in groups["pkg/models.py"]["locations"]}
    models_files = {str(Path(loc.path).relative_to(Path(FIXTURE)))
                    for loc in groups["pkg/models.py"]["locations"]}
    assert "pkg/models.py" in models_files
    assert "pkg/service.py" in models_files
    assert "pkg/other.py" not in models_files, (
        "binding-resolved references must exclude the same-named unrelated symbol"
    )
    assert "models.py" in models  # sanity on the name extraction


@pyright
def test_definition_follows_import_across_files():
    result = lsp_query(FIXTURE, "User", op="definition")
    locs = result["results"][0]["locations"]
    files = {str(Path(loc.path).relative_to(Path(FIXTURE))) for loc in locs}
    # Anchored at every occurrence (incl. the import + use in service.py),
    # definition resolves across the import to the class in models.py.
    assert "pkg/models.py" in files


@pyright
def test_hover_returns_inferred_signature():
    result = lsp_query(FIXTURE, "helper", op="hover")
    hovers = " ".join(g["hover"] or "" for g in result["results"])
    assert "helper" in hovers and "int" in hovers


@pyright
def test_indexing_wait_makes_queries_deterministic():
    # Without wait_for_index this would flake to empty. Repeat must be stable.
    for _ in range(2):
        result = lsp_query(FIXTURE, "User", op="references")
        total = sum(len(g["locations"]) for g in result["results"])
        assert total >= 3


@pyright
def test_no_orphaned_subprocess():
    before = _pyright_proc_count()
    lsp_query(FIXTURE, "User", op="references")
    # Context manager in lsp_query must reap the server.
    assert _pyright_proc_count() == before, "pyright-langserver leaked"


# ── soft-fallback contract (no pyright dependency) ───────────────────────────

def test_missing_symbol_raises_lsp_unavailable():
    with pytest.raises(LspUnavailable):
        lsp_query(FIXTURE, "NoSuchSymbolAnywhere", op="references")


def test_bootstrap_failure_raises_lsp_unavailable(monkeypatch):
    # Simulate node/pyright absence: ensure_pyright fails loud, the tier must
    # degrade (raise LspUnavailable) rather than hang.
    lsp = lsp_refs._import_lsp_client()

    def boom(*a, **k):
        raise lsp.BootstrapError("pyright requires system 'node' but none found")

    monkeypatch.setattr(lsp, "ensure_pyright", boom)
    with pytest.raises(LspUnavailable) as exc:
        lsp_query(FIXTURE, "helper", op="references")
    assert "node" in str(exc.value).lower()


# ── standalone runner ────────────────────────────────────────────────────────

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
