"""
Tests for opening-prs.opening_prs.open_pr.

Verifies:
  - happy path: branch + push + PR + mergeable polling all run in order
  - validate=must_not_be_base_branch blocks branch_name='main' (no API calls)
  - validate also rejects other protected names ('master', 'production', etc.)
  - validate rejects branch_name == base when base is custom (e.g. 'develop')
  - retry_until consumes budget when mergeable_state is initially 'unknown'
  - retry_until exhaustion: mergeable_state stays 'unknown' but PR still created
  - PR creation failure raises (main DAG) and skips wait_mergeable
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

THIS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = THIS_DIR.parent / "scripts"
SKILL_ROOT = THIS_DIR.parent
SKILLS_PARENT = SKILL_ROOT.parent  # repo root

# Wire flowing
sys.path.insert(0, str(SKILLS_PARENT / "flowing" / "scripts"))
import flowing as _flowing  # noqa: F401
sys.modules.setdefault("flowing", _flowing)

# Load opening_prs by file path
import importlib.util
spec = importlib.util.spec_from_file_location(
    "opening_prs_under_test", SCRIPTS_DIR / "opening_prs.py"
)
op = importlib.util.module_from_spec(spec)
sys.modules["opening_prs_under_test"] = op
spec.loader.exec_module(op)


def _patch_externals(monkeypatch, *,
                     pr_create_raises=False,
                     mergeable_sequence=None,
                     base_sha="basesha",
                     branch_create_raises=False,
                     put_file_raises=False):
    monkeypatch.setattr(op, "_get_branch_head", MagicMock(return_value=base_sha))

    cb_mock = MagicMock(return_value={"object": {"sha": "newbranch1"}})
    if branch_create_raises:
        cb_mock.side_effect = RuntimeError("422 ref already exists")
    monkeypatch.setattr(op, "_create_branch", cb_mock)

    pf_mock = MagicMock(return_value={"commit": {"sha": "filecommit1"}})
    if put_file_raises:
        pf_mock.side_effect = RuntimeError("contents API 500")
    monkeypatch.setattr(op, "_put_file", pf_mock)

    cpr_mock = MagicMock(return_value={
        "number": 99,
        "html_url": "https://github.com/o/r/pull/99",
        "state": "open",
    })
    if pr_create_raises:
        cpr_mock.side_effect = RuntimeError("422 PR exists")
    monkeypatch.setattr(op, "_create_pull_request", cpr_mock)

    if mergeable_sequence is None:
        mergeable_sequence = [{"mergeable_state": "clean", "mergeable": True}]
    seq = iter(mergeable_sequence)
    monkeypatch.setattr(op, "_get_pull_request",
                        MagicMock(side_effect=lambda *a, **k: next(seq)))

    return cb_mock, pf_mock, cpr_mock


def _ensure_token(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "test-token")


def test_happy_path(monkeypatch):
    _ensure_token(monkeypatch)
    cb, pf, cpr = _patch_externals(monkeypatch)

    result = op.open_pr(
        repo="o/r", branch_name="claude/feature-x",
        title="Feature X", body="Why & what.",
        files=[("a.py", "print(1)"), ("b.py", "print(2)")],
    )

    assert result["pr_url"] == "https://github.com/o/r/pull/99"
    assert result["pr_number"] == 99
    assert result["mergeable_state"] == "clean"
    assert result["files_pushed"] == ["a.py", "b.py"]
    assert cb.call_count == 1
    assert pf.call_count == 2
    assert cpr.call_count == 1


def test_validate_blocks_main(monkeypatch):
    _ensure_token(monkeypatch)
    cb, pf, cpr = _patch_externals(monkeypatch)
    try:
        op.open_pr(repo="o/r", branch_name="main",
                   title="t", body="b", files=[("a", "x")])
    except RuntimeError as e:
        assert "branch_name == base" in str(e) or "NEVER push" in str(e) or "Branch off" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
    assert cb.call_count == 0
    assert cpr.call_count == 0


def test_validate_blocks_other_protected(monkeypatch):
    _ensure_token(monkeypatch)
    cb, pf, cpr = _patch_externals(monkeypatch)
    for name in ("master", "production", "prod", "trunk", "MAIN", "Master"):
        try:
            op.open_pr(repo="o/r", branch_name=name,
                       title="t", body="b", files=[("a", "x")])
        except RuntimeError:
            continue
        raise AssertionError(f"expected RuntimeError for {name!r}")
    assert cb.call_count == 0


def test_validate_blocks_branch_equal_to_custom_base(monkeypatch):
    _ensure_token(monkeypatch)
    cb, pf, cpr = _patch_externals(monkeypatch)
    try:
        op.open_pr(repo="o/r", branch_name="develop",
                   title="t", body="b", files=[("a", "x")], base="develop")
    except RuntimeError as e:
        assert "branch_name == base" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
    assert cb.call_count == 0


def test_retry_until_polls_until_settled(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch, mergeable_sequence=[
        {"mergeable_state": "unknown"},
        {"mergeable_state": "unknown"},
        {"mergeable_state": "clean"},
    ])
    result = op.open_pr(
        repo="o/r", branch_name="claude/x", title="t", body="b",
        files=[("a", "x")], mergeable_poll_retries=4,
        mergeable_poll_base_ms=0, mergeable_poll_max_ms=0,
    )
    assert result["mergeable_state"] == "clean"
    assert op._get_pull_request.call_count == 3


def test_retry_until_exhaustion_preserves_state(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch, mergeable_sequence=[
        {"mergeable_state": "unknown"}] * 10)
    result = op.open_pr(
        repo="o/r", branch_name="claude/x", title="t", body="b",
        files=[("a", "x")], mergeable_poll_retries=2,
        mergeable_poll_base_ms=0, mergeable_poll_max_ms=0,
    )
    assert result["pr_url"].endswith("/99")
    assert result["mergeable_state"] == "unknown"


def test_unstable_settles_immediately(monkeypatch):
    _ensure_token(monkeypatch)
    _patch_externals(monkeypatch, mergeable_sequence=[
        {"mergeable_state": "unstable"}])
    result = op.open_pr(
        repo="o/r", branch_name="claude/x", title="t", body="b",
        files=[("a", "x")], mergeable_poll_retries=4,
        mergeable_poll_base_ms=0,
    )
    assert result["mergeable_state"] == "unstable"
    assert op._get_pull_request.call_count == 1


def test_pr_create_failure_raises(monkeypatch):
    _ensure_token(monkeypatch)
    cb, pf, cpr = _patch_externals(monkeypatch, pr_create_raises=True)
    try:
        op.open_pr(repo="o/r", branch_name="claude/x",
                   title="t", body="b", files=[("a", "x")])
    except RuntimeError as e:
        assert "PR exists" in str(e) or "create_pr" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError")
    assert cb.call_count == 1
    assert pf.call_count == 1
    assert op._get_pull_request.call_count == 0


def test_missing_token_raises_before_api(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    cb, pf, cpr = _patch_externals(monkeypatch)
    # Replace _get_branch_head with the real one so the token check fires;
    # patches above stub network functions but the actual auth check is in _gh_api.
    # We bypass: just call _gh_api directly.
    try:
        op._gh_api("GET", "/repos/x/y")
    except RuntimeError as e:
        assert "GH_TOKEN" in str(e)
    else:
        raise AssertionError("expected RuntimeError on missing token")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
