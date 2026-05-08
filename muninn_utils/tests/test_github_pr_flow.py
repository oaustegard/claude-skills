"""
Tests for muninn_utils.github_pr_flow.open_pr (issue #620).

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
    "github_pr_flow_under_test", PKG_DIR / "github_pr_flow.py"
)
gpf = importlib.util.module_from_spec(spec)
sys.modules["github_pr_flow_under_test"] = gpf
spec.loader.exec_module(gpf)


def _patch_externals(monkeypatch, *,
                     pr_create_raises=False,
                     mergeable_sequence=None,
                     base_sha="basesha",
                     branch_create_raises=False,
                     put_file_raises=False):
    """Patch every network call in github_pr_flow."""
    monkeypatch.setattr(gpf, "_get_branch_head", MagicMock(return_value=base_sha))

    cb_mock = MagicMock(return_value={"object": {"sha": "newbranch1"}})
    if branch_create_raises:
        cb_mock.side_effect = RuntimeError("422 ref already exists")
    monkeypatch.setattr(gpf, "_create_branch", cb_mock)

    pf_mock = MagicMock(return_value={"commit": {"sha": "filecommit1"}})
    if put_file_raises:
        pf_mock.side_effect = RuntimeError("contents API 500")
    monkeypatch.setattr(gpf, "_put_file", pf_mock)

    cpr_mock = MagicMock(return_value={
        "number": 99,
        "html_url": "https://github.com/o/r/pull/99",
        "state": "open",
    })
    if pr_create_raises:
        cpr_mock.side_effect = RuntimeError("422 PR exists")
    monkeypatch.setattr(gpf, "_create_pull_request", cpr_mock)

    if mergeable_sequence is None:
        mergeable_sequence = [{"mergeable_state": "clean", "mergeable": True}]
    seq = iter(mergeable_sequence)
    monkeypatch.setattr(gpf, "_get_pull_request",
                        MagicMock(side_effect=lambda *a, **k: next(seq)))

    return cb_mock, pf_mock, cpr_mock


def test_happy_path_creates_branch_pushes_files_opens_pr(monkeypatch):
    cb, pf, cpr = _patch_externals(monkeypatch)

    result = gpf.open_pr(
        repo="o/r",
        branch_name="claude/feature-x",
        title="Feature X",
        body="Why & what.",
        files=[("a.py", "print(1)"), ("b.py", "print(2)")],
    )

    assert result["pr_url"] == "https://github.com/o/r/pull/99"
    assert result["pr_number"] == 99
    assert result["branch"] == "claude/feature-x"
    assert result["base"] == "main"
    assert result["head_sha"] == "basesha"
    assert result["mergeable_state"] == "clean"
    assert result["files_pushed"] == ["a.py", "b.py"]
    assert result["detached_failures"] == []

    assert cb.call_count == 1
    assert pf.call_count == 2
    assert cpr.call_count == 1


def test_validate_blocks_branch_name_main(monkeypatch):
    cb, pf, cpr = _patch_externals(monkeypatch)

    try:
        gpf.open_pr(
            repo="o/r", branch_name="main",
            title="t", body="b",
            files=[("a.py", "x")],
        )
    except RuntimeError as e:
        assert "branch_name == base" in str(e) or "NEVER push directly" in str(e)
    else:
        raise AssertionError("expected RuntimeError on branch_name='main'")

    # Zero API calls fired.
    assert cb.call_count == 0
    assert pf.call_count == 0
    assert cpr.call_count == 0
    assert gpf._get_branch_head.call_count == 0


def test_validate_blocks_other_protected_names(monkeypatch):
    """master, production, prod, trunk are also blocked."""
    cb, pf, cpr = _patch_externals(monkeypatch)

    for protected in ("master", "production", "prod", "trunk", "MAIN", "Master"):
        try:
            gpf.open_pr(
                repo="o/r", branch_name=protected,
                title="t", body="b",
                files=[("a.py", "x")],
            )
        except RuntimeError as e:
            msg = str(e).lower()
            assert "protected" in msg or "branch_name == base" in msg, \
                f"unexpected error for {protected!r}: {e}"
        else:
            raise AssertionError(f"expected RuntimeError on branch_name={protected!r}")

    assert cb.call_count == 0


def test_validate_blocks_branch_equal_to_custom_base(monkeypatch):
    """base='develop' + branch='develop' → blocked."""
    cb, pf, cpr = _patch_externals(monkeypatch)

    try:
        gpf.open_pr(
            repo="o/r", branch_name="develop",
            title="t", body="b",
            files=[("a.py", "x")],
            base="develop",
        )
    except RuntimeError as e:
        assert "branch_name == base" in str(e)
    else:
        raise AssertionError("expected RuntimeError on branch == base")

    assert cb.call_count == 0


def test_retry_until_polls_until_settled(monkeypatch):
    """First two polls return 'unknown', then 'clean'."""
    cb, pf, cpr = _patch_externals(monkeypatch, mergeable_sequence=[
        {"mergeable_state": "unknown", "mergeable": None},
        {"mergeable_state": "unknown", "mergeable": None},
        {"mergeable_state": "clean", "mergeable": True},
    ])

    result = gpf.open_pr(
        repo="o/r", branch_name="claude/x",
        title="t", body="b",
        files=[("a.py", "x")],
        mergeable_poll_retries=4,
        mergeable_poll_base_ms=0,
        mergeable_poll_max_ms=0,
    )

    assert result["mergeable_state"] == "clean"
    assert gpf._get_pull_request.call_count == 3


def test_retry_until_exhausts_budget_returns_last_state(monkeypatch):
    """mergeable_state stays 'unknown' → wait_mergeable FAILS but PR is still presented."""
    cb, pf, cpr = _patch_externals(monkeypatch, mergeable_sequence=[
        {"mergeable_state": "unknown", "mergeable": None},
    ] * 10)

    result = gpf.open_pr(
        repo="o/r", branch_name="claude/x",
        title="t", body="b",
        files=[("a.py", "x")],
        mergeable_poll_retries=2,
        mergeable_poll_base_ms=0,
        mergeable_poll_max_ms=0,
    )

    # PR was created and URL surfaced.
    assert result["pr_url"] == "https://github.com/o/r/pull/99"
    # mergeable polling exhausted; last state preserved.
    assert result["mergeable_state"] == "unknown"


def test_unstable_mergeable_state_settles_immediately(monkeypatch):
    """unstable (CI failing) is a settled state — don't keep polling."""
    cb, pf, cpr = _patch_externals(monkeypatch, mergeable_sequence=[
        {"mergeable_state": "unstable", "mergeable": True},
    ])

    result = gpf.open_pr(
        repo="o/r", branch_name="claude/x",
        title="t", body="b",
        files=[("a.py", "x")],
        mergeable_poll_retries=4,
        mergeable_poll_base_ms=0,
    )

    assert result["mergeable_state"] == "unstable"
    assert gpf._get_pull_request.call_count == 1


def test_pr_create_failure_raises_skips_mergeable_poll(monkeypatch):
    cb, pf, cpr = _patch_externals(monkeypatch, pr_create_raises=True)

    try:
        gpf.open_pr(
            repo="o/r", branch_name="claude/x",
            title="t", body="b",
            files=[("a.py", "x")],
        )
    except RuntimeError as e:
        assert "PR exists" in str(e) or "create_pr" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError on PR creation failure")

    # Branch and files still pushed, but no mergeable poll.
    assert cb.call_count == 1
    assert pf.call_count == 1
    assert gpf._get_pull_request.call_count == 0


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
