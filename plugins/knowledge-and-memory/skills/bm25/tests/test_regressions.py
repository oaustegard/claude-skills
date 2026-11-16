"""Deterministic regressions for the two findings; no model, no generator."""
import importlib.util, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import pytest

SKILL = Path(os.environ.get("BM25_PY", Path(__file__).resolve().parents[1] / "scripts" / "bm25.py"))
spec = importlib.util.spec_from_file_location("bm25cli", SKILL)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "CACHE_ROOT", tmp_path / "cache")
    root = tmp_path / "corpus"; root.mkdir()
    return root

def build(root):
    return m.get_or_build_index(root, [], [], 2_000_000, use_cache=True)[0]

def test_cache_serves_edited_file_stale(corpus):
    (corpus / "a.txt").write_text("alpha")
    (corpus / "b.txt").write_text("beta")
    build(corpus)
    (corpus / "a.txt").write_text("gamma")
    idx = build(corpus)
    assert dict(zip(idx.paths, idx.docs))["a.txt"] == "gamma"

def test_cache_serves_deleted_file(corpus):
    (corpus / "a.txt").write_text("alpha")
    (corpus / "b.txt").write_text("beta")
    build(corpus)
    (corpus / "a.txt").unlink()
    assert build(corpus).paths == ["b.txt"]

def test_cache_misses_new_file(corpus):
    (corpus / "a.txt").write_text("alpha")
    build(corpus)
    (corpus / "b.txt").write_text("beta")
    assert sorted(build(corpus).paths) == ["a.txt", "b.txt"]

@pytest.mark.parametrize("files", [{}, {"README": "x y z"}])
def test_cli_no_indexable_terms_exits_cleanly(tmp_path, files):
    for n, t in files.items():
        (tmp_path / n).write_text(t)
    r = subprocess.run([sys.executable, str(SKILL), str(tmp_path), "alpha", "--no-cache"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr[-300:]
    hits = [l for l in r.stdout.splitlines() if l.strip()[:2].rstrip(".").isdigit()]
    assert len(hits) == len(files), r.stdout          # one zero-score hit per file
    assert all(" 0.00 " in l for l in hits), r.stdout
