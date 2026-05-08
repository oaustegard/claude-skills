"""
Tests for muninn_utils.issue_close (issue #619).

Verifies:
  - happy path: close + memory + verify
  - validate=must_have_synthesis_text rejects empty/whitespace
  - close failure raises (main DAG); no memory write
  - memory failure does NOT raise; surfaces in detached_failures
  - pending_test=False skips verify_pending_test (when= gate)
  - pending_test=True with missing tag → verify_pending_test fails detached
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

THIS_DIR = Path(__file__).resolve().parent
PKG_DIR = THIS_DIR.parent
SKILLS_ROOT = PKG_DIR.parent

sys.path.insert(0, str(SKILLS_ROOT / "flowing" / "scripts"))
import flowing as _flowing
sys.modules.setdefault("flowing", _flowing)

import importlib.util
spec = importlib.util.spec_from_file_location(
    "issue_close_under_test", PKG_DIR / "issue_close.py"
)
ic = importlib.util.module_from_spec(spec)
sys.modules["issue_close_under_test"] = ic
spec.loader.exec_module(ic)


def _patch_externals(monkeypatch, *,
                     close_raises=False,
                     remember_raises=False,
                     mem_id="mem-abc-123",
                     recall_returns=None):
    """Patch GitHub + memory layers."""
    if close_raises:
        monkeypatch.setattr(ic, "_post_close_comment",
                            MagicMock(side_effect=RuntimeError("GH 422")))
    else:
        monkeypatch.setattr(ic, "_post_close_comment",
                            MagicMock(return_value={
                                "id": 999,
                                "html_url": "https://github.com/x/y/issues/1#issuecomment-999",
                            }))
    monkeypatch.setattr(ic, "_close_issue",
                        MagicMock(return_value={"state": "closed"}))

    remember_mock = MagicMock(return_value=mem_id)
    if remember_raises:
        remember_mock.side_effect = RuntimeError("turso 503")
    monkeypatch.setattr(ic, "_import_remember", lambda: remember_mock)

    if recall_returns is None:
        recall_returns = [{"id": mem_id}]
    recall_mock = MagicMock(return_value=recall_returns)
    monkeypatch.setattr(ic, "_import_recall", lambda: recall_mock)

    return remember_mock, recall_mock


def test_happy_path_no_pending_test(monkeypatch):
    remember_mock, recall_mock = _patch_externals(monkeypatch)

    result = ic.issue_close(
        number=42,
        synthesis="Learned that flowing graphs make gates structural.",
        repo="oaustegard/claude-skills",
        pending_test=False,
        extra_tags=["flowing"],
    )

    assert result["issue_url"] == "https://github.com/oaustegard/claude-skills/issues/42"
    assert result["comment_url"].endswith("#issuecomment-999")
    assert result["memory_id"] == "mem-abc-123"
    assert result["pending_test_applied"] is False
    assert result["detached_failures"] == []

    assert ic._post_close_comment.call_count == 1
    assert ic._close_issue.call_count == 1
    assert remember_mock.call_count == 1
    assert recall_mock.call_count == 0  # gated off

    # The memory write got base tags but NOT pending-test.
    args, kwargs = remember_mock.call_args
    tags = kwargs.get("tags") or args[2] if len(args) > 2 else kwargs.get("tags", [])
    assert "issue-42" in tags
    assert "claude-skills" in tags
    assert "flowing" in tags
    assert ic.PENDING_TEST_TAG not in tags


def test_pending_test_true_includes_tag_and_verifies(monkeypatch):
    remember_mock, recall_mock = _patch_externals(monkeypatch)

    result = ic.issue_close(
        number=43,
        synthesis="Pattern X validated under load.",
        repo="oaustegard/claude-skills",
        pending_test=True,
    )

    args, kwargs = remember_mock.call_args
    tags = kwargs.get("tags", [])
    assert ic.PENDING_TEST_TAG in tags

    assert result["pending_test_applied"] is True
    assert recall_mock.call_count == 1
    assert result["detached_failures"] == []


def test_validate_blocks_empty_synthesis(monkeypatch):
    remember_mock, recall_mock = _patch_externals(monkeypatch)

    try:
        ic.issue_close(
            number=44,
            synthesis="   \n\t",
            repo="oaustegard/claude-skills",
        )
    except RuntimeError as e:
        assert "synthesis" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError on empty synthesis")

    # No GitHub or memory work happened.
    assert ic._post_close_comment.call_count == 0
    assert ic._close_issue.call_count == 0
    assert remember_mock.call_count == 0


def test_close_failure_raises_no_memory_write(monkeypatch):
    remember_mock, recall_mock = _patch_externals(monkeypatch, close_raises=True)

    try:
        ic.issue_close(
            number=45,
            synthesis="real synthesis",
            repo="oaustegard/claude-skills",
        )
    except RuntimeError as e:
        assert "GH 422" in str(e)
    else:
        raise AssertionError("expected RuntimeError on close failure")

    # The PATCH-close was never reached either (post_close_comment failed first).
    assert ic._close_issue.call_count == 0
    # Memory write SKIPPED.
    assert remember_mock.call_count == 0


def test_memory_failure_is_detached_no_raise(monkeypatch):
    remember_mock, recall_mock = _patch_externals(monkeypatch, remember_raises=True)

    result = ic.issue_close(
        number=46,
        synthesis="real synthesis",
        repo="oaustegard/claude-skills",
    )

    # Close succeeded.
    assert result["issue_url"].endswith("/issues/46")
    # Memory failed but didn't propagate.
    assert result["memory_id"] is None
    failures = dict(result["detached_failures"])
    assert "store_synthesis_memory" in failures
    assert "503" in failures["store_synthesis_memory"]


def test_pending_test_tag_silently_dropped_surfaces_failure(monkeypatch):
    """If the tag is missing on recall, verify_pending_test should fail detached."""
    # Recall returns no rows matching mem_id → verify raises.
    remember_mock, recall_mock = _patch_externals(monkeypatch,
                                                  recall_returns=[{"id": "other"}])

    result = ic.issue_close(
        number=47,
        synthesis="real synthesis",
        repo="oaustegard/claude-skills",
        pending_test=True,
    )

    # Close + memory both ok.
    assert result["memory_id"] == "mem-abc-123"
    # Verify failed → not applied + surfaced in detached failures.
    assert result["pending_test_applied"] is False
    failures = dict(result["detached_failures"])
    assert "verify_pending_test" in failures


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
