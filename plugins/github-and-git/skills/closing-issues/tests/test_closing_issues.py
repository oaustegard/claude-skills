"""
Tests for closing-issues.closing_issues.close_issue.

Verifies:
  - happy path (no callback): close + comment, no callback fires
  - happy path (with callback): close + comment + callback runs detached
  - validate=must_have_synthesis_text rejects empty/whitespace
  - close failure raises (main DAG); no callback fires
  - callback failure does NOT raise; surfaces in detached_failures
  - missing GH_TOKEN raises before any API call
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

THIS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = THIS_DIR.parent / "scripts"
SKILL_ROOT = THIS_DIR.parent
SKILLS_PARENT = SKILL_ROOT.parent

sys.path.insert(0, str(SKILLS_PARENT / "flowing" / "scripts"))
import flowing as _flowing  # noqa: F401
sys.modules.setdefault("flowing", _flowing)

import importlib.util
spec = importlib.util.spec_from_file_location(
    "closing_issues_under_test", SCRIPTS_DIR / "closing_issues.py"
)
ci = importlib.util.module_from_spec(spec)
sys.modules["closing_issues_under_test"] = ci
spec.loader.exec_module(ci)


def _patch_externals(monkeypatch, *, close_raises=False):
    if close_raises:
        monkeypatch.setattr(ci, "_post_close_comment",
                            MagicMock(side_effect=RuntimeError("GH 422")))
    else:
        monkeypatch.setattr(ci, "_post_close_comment",
                            MagicMock(return_value={
                                "id": 999,
                                "html_url": "https://github.com/o/r/issues/1#issuecomment-999",
                            }))
    monkeypatch.setattr(ci, "_close_issue",
                        MagicMock(return_value={"state": "closed"}))


def _ensure_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "test-token")


def test_happy_path_no_callback(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch)

    result = ci.close_issue(
        repo="o/r", number=42,
        synthesis="Pattern X works because of Y. Constraint: Z.",
    )

    assert result["issue_url"] == "https://github.com/o/r/issues/42"
    assert result["comment_url"].endswith("#issuecomment-999")
    assert result["callback_result"] is None
    assert result["detached_failures"] == []
    assert ci._post_close_comment.call_count == 1
    assert ci._close_issue.call_count == 1


def test_happy_path_with_callback(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch)

    callback = MagicMock(return_value={"stored": True, "id": "mem-1"})
    result = ci.close_issue(
        repo="o/r", number=43,
        synthesis="Learned about flowing graphs.",
        post_close_callback=callback,
    )

    assert result["callback_result"] == {"stored": True, "id": "mem-1"}
    assert callback.call_count == 1
    # Callback receives the four kwargs.
    cb_kwargs = callback.call_args.kwargs
    assert cb_kwargs["synthesis"] == "Learned about flowing graphs."
    assert cb_kwargs["issue_url"].endswith("/issues/43")
    assert cb_kwargs["repo"] == "o/r"
    assert cb_kwargs["number"] == 43


def test_validate_blocks_empty_synthesis(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch)
    callback = MagicMock()

    try:
        ci.close_issue(
            repo="o/r", number=44, synthesis="   \n\t",
            post_close_callback=callback,
        )
    except RuntimeError as e:
        assert "synthesis" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError on empty synthesis")

    # No GitHub API calls and no callback.
    assert ci._post_close_comment.call_count == 0
    assert ci._close_issue.call_count == 0
    assert callback.call_count == 0


def test_close_failure_raises_no_callback(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch, close_raises=True)
    callback = MagicMock()

    try:
        ci.close_issue(
            repo="o/r", number=45, synthesis="real synthesis",
            post_close_callback=callback,
        )
    except RuntimeError as e:
        assert "GH 422" in str(e)
    else:
        raise AssertionError("expected RuntimeError on close failure")

    assert callback.call_count == 0


def test_callback_failure_is_detached_no_raise(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch)
    callback = MagicMock(side_effect=RuntimeError("memory store down"))

    result = ci.close_issue(
        repo="o/r", number=46, synthesis="real synthesis",
        post_close_callback=callback,
    )

    # Close still succeeded.
    assert result["issue_url"].endswith("/issues/46")
    # Callback failed but didn't propagate.
    assert result["callback_result"] is None
    failures = dict(result["detached_failures"])
    assert "post_close_callback" in failures
    assert "memory store down" in failures["post_close_callback"]


def test_missing_token_raises_before_api(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    try:
        ci._gh_api("GET", "/repos/x/y")
    except RuntimeError as e:
        assert "GH_TOKEN" in str(e)
    else:
        raise AssertionError("expected RuntimeError on missing token")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
