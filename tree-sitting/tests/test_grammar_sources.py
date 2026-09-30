"""Grammar loading off Linux x86_64: fallbacks, the missing-grammar hint, and
cache invalidation when a grammar becomes available.

Run: python -m pytest tests/test_grammar_sources.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import engine
from engine import CodeCache


@pytest.fixture
def no_grammars(tmp_path, monkeypatch):
    """Every grammar source empty — what a Mac sees before installing wheels."""
    empty = tmp_path / 'empty'
    empty.mkdir()
    monkeypatch.setattr(engine, '_PARSERS_DIR', empty)
    monkeypatch.setenv('TREESIT_PARSERS_DIR', str(empty))
    monkeypatch.setattr(engine, '_load_wheel', lambda lang: None)
    _reset_memos(monkeypatch)
    return empty


def _reset_memos(monkeypatch):
    for name in ('_parsers', '_languages', '_grammar_sources'):
        monkeypatch.setattr(engine, name, {})


def _repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'a.py').write_text('def f():\n    return 1\n')
    (repo / 'data.json').write_text('{}\n')
    return repo


def test_missing_core_grammar_warns(tmp_path, monkeypatch, no_grammars):
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(tmp_path / 'cache'))
    stats = CodeCache().scan(str(_repo(tmp_path)))
    assert stats['files'] == 0
    hint = stats['grammar_hint']
    assert 'python' in hint and 'pip install tree-sitter tree-sitter-python' in hint
    # .json has no bundled grammar and isn't a core language: no nagging.
    assert 'json' not in hint


def test_cache_invalidates_when_grammar_appears(tmp_path, monkeypatch, no_grammars):
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(tmp_path / 'cache'))
    repo = _repo(tmp_path)
    empty = CodeCache().scan(str(repo))
    assert empty['files'] == 0

    # A grammar becomes available (wheel installed); the cached empty scan
    # must not be served.
    monkeypatch.undo()
    monkeypatch.setenv('TREESIT_CACHE_DIR', str(tmp_path / 'cache'))
    stats = CodeCache().scan(str(repo))
    assert stats['loaded_from_cache'] is False
    assert stats['files'] == 1 and stats['grammar_hint'] is None


def test_wheel_fallback_without_bundled(tmp_path, monkeypatch):
    pytest.importorskip('tree_sitter_python')
    monkeypatch.setattr(engine, '_PARSERS_DIR', tmp_path)
    monkeypatch.setenv('TREESIT_PARSERS_DIR', str(tmp_path))
    _reset_memos(monkeypatch)
    assert engine._get_parser('python') is not None
    assert engine.grammar_source('python') == 'wheel'
