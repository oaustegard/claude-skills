"""
Tests for blog_publish.publish_and_announce flowing graph (issue #616).

Verifies:
  - main DAG order: publish_page → wait_for_deploy → update_feed
  - detached chain auto-discovery: announce_bsky → link_engagement_node
  - retry_until=lambda r: r["deployed"] consumes budget when deploy is slow
  - when= gate skips update_feed when feed_path is None
  - validate= rejects bsky_text > BSKY_LIMIT before any post fires
  - bsky failure populates detached_failures, doesn't raise

Network calls are monkeypatched. No real GitHub or Bluesky access required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

THIS_DIR = Path(__file__).resolve().parent
PKG_DIR = THIS_DIR.parent
SKILLS_ROOT = PKG_DIR.parent

# bsky_card and bsky_limit are needed by blog_publish at import time. Stub /
# load them BEFORE adding PKG_DIR to sys.path so we don't accidentally pick up
# the materialized siblings under /root/muninn_utils.
import types

bsky_card_stub = types.ModuleType("bsky_card")
# Collapsed compose_link_post returns {record, post, og_tags, thumb_blob,
# facets, detached_failures} — see #617.
bsky_card_stub.compose_link_post = MagicMock()
sys.modules["bsky_card"] = bsky_card_stub

# bsky_limit: prefer the real materialized one (correct grapheme counting),
# fall back to a tiny len-based stub.
try:
    import importlib.util
    materialized = Path("/root/muninn_utils/bsky_limit.py")
    if materialized.exists():
        spec = importlib.util.spec_from_file_location("bsky_limit", materialized)
        bsky_limit_mod = importlib.util.module_from_spec(spec)
        sys.modules["bsky_limit"] = bsky_limit_mod
        spec.loader.exec_module(bsky_limit_mod)
        bsky_limit = bsky_limit_mod
    else:
        raise FileNotFoundError
except Exception:
    bsky_limit = types.ModuleType("bsky_limit")
    bsky_limit.BSKY_LIMIT = 300
    bsky_limit.fits = lambda t, limit=300: len(t) <= limit
    sys.modules["bsky_limit"] = bsky_limit

# Wire flowing from the skill bytes (canonical source).
sys.path.insert(0, str(SKILLS_ROOT / "flowing" / "scripts"))
import flowing as _flowing
sys.modules.setdefault("flowing", _flowing)

# Now load OUR blog_publish (not the materialized one) by file path so there
# is zero ambiguity about which copy is under test.
import importlib.util
spec = importlib.util.spec_from_file_location(
    "blog_publish_under_test", PKG_DIR / "blog_publish.py"
)
bp = importlib.util.module_from_spec(spec)
sys.modules["blog_publish_under_test"] = bp
spec.loader.exec_module(bp)


def _reset(monkeypatch):
    """Patch every external call inside blog_publish to a controllable mock."""
    monkeypatch.setattr(bp, "publish_page", MagicMock(return_value="abcdef1234"))
    monkeypatch.setattr(bp, "update_feed", MagicMock(return_value="feed5678"))
    monkeypatch.setattr(bp, "link_engagement", MagicMock(return_value="link9999"))
    monkeypatch.setattr(bp, "_probe_url", MagicMock(return_value=True))

    bsky_card_stub.compose_link_post.reset_mock()
    bsky_card_stub.compose_link_post.side_effect = None
    bsky_card_stub.compose_link_post.return_value = {
        "record": {"$type": "app.bsky.feed.post"},
        "post": {
            "uri": "at://did:plc:x/app.bsky.feed.post/abc",
            "cid": "cid1",
            "url": "https://bsky.app/profile/h/post/abc",
            "rkey": "abc",
        },
        "og_tags": {"url": "u"},
        "thumb_blob": None,
        "facets": [],
        "detached_failures": [],
    }
    return bsky_card_stub


def test_happy_path_main_chain_and_detached(monkeypatch):
    """All five steps run, in order; detached chain produces post + link."""
    bc = _reset(monkeypatch)

    result = bp.publish_and_announce(
        path="blog/x.html",
        content="<html/>",
        bsky_text="A post",
        auth={"access_jwt": "j", "did": "did:plc:x", "handle": "h"},
        feed_entry={"title": "X", "summary": "..."},
    )

    assert result["page_url"] == f"{bp._MUNINN_BASE}/blog/x.html"
    assert result["commit_sha"] == "abcdef1234"
    assert result["feed_sha"] == "feed5678"
    assert result["deployed"] is True
    assert result["bsky_post"]["url"].startswith("https://bsky.app/")
    assert result["update_sha"] == "link9999"
    assert result["detached_failures"] == []

    # Main-chain functions each called exactly once.
    assert bp.publish_page.call_count == 1
    assert bp.update_feed.call_count == 1
    assert bp.link_engagement.call_count == 1
    assert bc.compose_link_post.call_count == 1


def test_when_skips_feed_update_without_feed_path(monkeypatch):
    """feed_path=None → update_feed_node skipped; detached chain still runs."""
    bc = _reset(monkeypatch)

    result = bp.publish_and_announce(
        path="blog/y.html",
        content="<html/>",
        bsky_text="B",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        repo="oaustegard/oaustegard.github.io",
        site_base="https://austegard.com",
        feed_path=None,
        feed_entry=None,
    )

    assert bp.update_feed.call_count == 0
    assert result["feed_sha"] is None
    # Page commit and bsky chain still ran.
    assert bp.publish_page.call_count == 1
    assert bc.compose_link_post.call_count == 1
    assert result["update_sha"] == "link9999"


def test_validate_blocks_oversize_bsky_text(monkeypatch):
    """bsky_text > BSKY_LIMIT → announce_bsky FAILS with no createRecord call."""
    bc = _reset(monkeypatch)

    huge = "x" * (bsky_limit.BSKY_LIMIT + 1)
    result = bp.publish_and_announce(
        path="blog/z.html",
        content="<html/>",
        bsky_text=huge,
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "Z", "summary": "..."},
    )

    # Main chain still completed.
    assert result["commit_sha"] == "abcdef1234"
    assert result["feed_sha"] == "feed5678"
    # bsky never composed/posted.
    assert bc.compose_link_post.call_count == 0
    assert result["bsky_post"] is None
    # link_engagement skipped (its dep failed).
    assert bp.link_engagement.call_count == 0
    # Surface in detached_failures.
    failures = dict(result["detached_failures"])
    assert "announce_bsky" in failures
    assert "graphemes" in failures["announce_bsky"].lower() or \
           str(bsky_limit.BSKY_LIMIT) in failures["announce_bsky"]


def test_retry_until_consumes_budget_when_deploy_slow(monkeypatch):
    """First N probes return False; succeeds on attempt N+1 within retry budget."""
    bc = _reset(monkeypatch)

    # Speed up the test: monkey-patch retry config to 0ms backoff.
    monkeypatch.setattr(bp, "_DEPLOY_POLL_MS", 0)
    monkeypatch.setattr(bp, "_DEPLOY_RETRIES", 4)

    # Returns False, False, True (succeeds on third attempt).
    seq = iter([False, False, True])
    bp._probe_url = MagicMock(side_effect=lambda *a, **k: next(seq))
    monkeypatch.setattr(bp, "_probe_url", bp._probe_url)

    result = bp.publish_and_announce(
        path="blog/r.html",
        content="<html/>",
        bsky_text="R",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "R", "summary": "..."},
    )

    assert result["deployed"] is True
    # Probe called at least 3 times (the first two returned False).
    assert bp._probe_url.call_count == 3
    # Downstream still happened.
    assert bp.update_feed.call_count == 1
    assert bc.compose_link_post.call_count == 1


def test_retry_until_exhausts_budget(monkeypatch):
    """Deploy never lands → wait_for_deploy_node FAILS, downstream all skipped."""
    bc = _reset(monkeypatch)

    monkeypatch.setattr(bp, "_DEPLOY_POLL_MS", 0)
    monkeypatch.setattr(bp, "_DEPLOY_RETRIES", 2)
    monkeypatch.setattr(bp, "_probe_url", MagicMock(return_value=False))

    result = bp.publish_and_announce(
        path="blog/never.html",
        content="<html/>",
        bsky_text="N",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "N", "summary": "..."},
    )

    # Page committed, but everything downstream skipped.
    assert result["commit_sha"] == "abcdef1234"
    assert result["deployed"] is False
    assert result["feed_sha"] is None
    assert result["bsky_post"] is None
    assert result["update_sha"] is None
    assert bp.update_feed.call_count == 0
    assert bc.compose_link_post.call_count == 0


def test_skip_deploy_wait_short_circuits_probe(monkeypatch):
    """skip_deploy_wait=True → _probe_url never called."""
    bc = _reset(monkeypatch)
    monkeypatch.setattr(bp, "_probe_url", MagicMock(return_value=False))

    result = bp.publish_and_announce(
        path="blog/skip.html",
        content="<html/>",
        bsky_text="S",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "S", "summary": "..."},
        skip_deploy_wait=True,
    )

    assert result["deployed"] is True
    assert bp._probe_url.call_count == 0
    assert bp.update_feed.call_count == 1
    assert bc.compose_link_post.call_count == 1


def test_bsky_failure_does_not_block_main_return(monkeypatch):
    """compose_link_post raises → bsky_post is None, detached_failures populated, but feed/page ok."""
    bc = _reset(monkeypatch)
    bc.compose_link_post.side_effect = RuntimeError("AT Proto 503")

    result = bp.publish_and_announce(
        path="blog/det.html",
        content="<html/>",
        bsky_text="D",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        feed_entry={"title": "D", "summary": "..."},
    )

    assert result["commit_sha"] == "abcdef1234"
    assert result["feed_sha"] == "feed5678"
    assert result["bsky_post"] is None
    assert result["update_sha"] is None
    failures = dict(result["detached_failures"])
    assert "announce_bsky" in failures
    assert "503" in failures["announce_bsky"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
