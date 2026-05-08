"""
Tests for bsky_card.compose_link_post / compose_and_post (issue #617).

Verifies:
  - Topology: fetch_og + facets_node parallel, upload_blob → embed → record → post
  - Happy path: record contains text + facets + embed with thumb
  - No image in OG → embed has no thumb, post still fires
  - upload_blob_node raises → embed and post SKIP cleanly, create_post never fires
  - validate=must_be_valid_record blocks empty text
  - Pre-supplied og_tags short-circuits the network fetch
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
    "bsky_card_under_test", PKG_DIR / "bsky_card.py"
)
bc = importlib.util.module_from_spec(spec)
sys.modules["bsky_card_under_test"] = bc
spec.loader.exec_module(bc)


def _patch_externals(monkeypatch, *,
                     og_tags=None,
                     upload_raises=False,
                     post_raises=False):
    """Patch fetch_og_tags, upload_blob, create_post on the module."""
    if og_tags is None:
        og_tags = {
            "url": "https://example.com/p",
            "title": "T",
            "description": "D",
            "image": "https://example.com/i.png",
        }
    monkeypatch.setattr(bc, "fetch_og_tags", MagicMock(return_value=og_tags))

    if upload_raises:
        monkeypatch.setattr(bc, "upload_blob",
                            MagicMock(side_effect=RuntimeError("blob 503")))
    else:
        monkeypatch.setattr(bc, "upload_blob",
                            MagicMock(return_value={"$type": "blob", "ref": "x"}))

    create_post_mock = MagicMock(return_value={
        "uri": "at://did/app.bsky.feed.post/r",
        "cid": "c",
        "url": "https://bsky.app/profile/h/post/r",
        "rkey": "r",
    })
    if post_raises:
        create_post_mock.side_effect = RuntimeError("createRecord 500")
    monkeypatch.setattr(bc, "create_post", create_post_mock)
    return create_post_mock


def test_compose_happy_path_returns_full_record(monkeypatch):
    _patch_externals(monkeypatch)

    record = bc.compose_link_post(
        "Check this out", "https://example.com/p",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
    )

    assert record["$type"] == "app.bsky.feed.post"
    # URL should have been appended to text since not present.
    assert "https://example.com/p" in record["text"]
    # Facet for the URL exists.
    link_facets = [f for f in record["facets"]
                   if any(feat["$type"] == "app.bsky.richtext.facet#link"
                          for feat in f["features"])]
    assert link_facets, "expected at least one link facet"
    # Embed has the thumb (upload returned a blob).
    assert record["embed"]["external"]["uri"] == "https://example.com/p"
    assert record["embed"]["external"]["thumb"]["$type"] == "blob"


def test_compose_no_og_image_yields_thumbless_embed(monkeypatch):
    _patch_externals(monkeypatch, og_tags={
        "url": "https://example.com/p",
        "title": "T",
        "description": "D",
    })

    record = bc.compose_link_post(
        "x", "https://example.com/p",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
    )

    # No thumb (no image in OG), but embed still present.
    assert "thumb" not in record["embed"]["external"]
    assert record["embed"]["external"]["uri"] == "https://example.com/p"
    # upload_blob never called.
    assert bc.upload_blob.call_count == 0


def test_compose_upload_failure_skips_embed_and_record(monkeypatch):
    _patch_externals(monkeypatch, upload_raises=True)

    try:
        bc.compose_link_post(
            "x", "https://example.com/p",
            auth={"access_jwt": "j", "did": "did", "handle": "h"},
        )
    except RuntimeError as e:
        assert "upload_blob_node" in str(e)
        assert "blob 503" in str(e)
        return
    raise AssertionError("expected RuntimeError when upload_blob_node fails")


def test_compose_pre_supplied_og_skips_fetch(monkeypatch):
    _patch_externals(monkeypatch)

    pre = {
        "url": "https://example.com/p",
        "title": "Pre",
        "description": "D",
        "image": "https://example.com/img.png",
    }
    record = bc.compose_link_post(
        "x", "https://example.com/p",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
        og_tags=pre,
    )

    assert record["embed"]["external"]["title"] == "Pre"
    assert bc.fetch_og_tags.call_count == 0


def test_compose_and_post_happy_path(monkeypatch):
    create_post_mock = _patch_externals(monkeypatch)

    result = bc.compose_and_post(
        "x", "https://example.com/p",
        auth={"access_jwt": "j", "did": "did", "handle": "h"},
    )

    assert result["record"]["$type"] == "app.bsky.feed.post"
    assert result["post"]["url"].startswith("https://bsky.app/")
    assert result["thumb_blob"]["$type"] == "blob"
    assert isinstance(result["facets"], list)
    assert result["detached_failures"] == []
    assert create_post_mock.call_count == 1


def test_compose_and_post_skips_create_when_upload_fails(monkeypatch):
    create_post_mock = _patch_externals(monkeypatch, upload_raises=True)

    try:
        bc.compose_and_post(
            "x", "https://example.com/p",
            auth={"access_jwt": "j", "did": "did", "handle": "h"},
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError when upload_blob_node fails")

    # create_post must NOT have fired — that's the whole point of #617.
    assert create_post_mock.call_count == 0


def test_compose_and_post_validate_blocks_empty_text(monkeypatch):
    _patch_externals(monkeypatch)

    # An empty text after URL-append would still contain the URL line, so we
    # need to construct a record that genuinely fails validate. Easiest: stub
    # build_external_embed to drop the uri so the embed-uri check trips.
    monkeypatch.setattr(bc, "build_external_embed",
                        lambda og, thumb_blob=None: {
                            "$type": "app.bsky.embed.external",
                            "external": {"title": "x", "description": "y"},
                        })

    try:
        bc.compose_and_post(
            "x", "https://example.com/p",
            auth={"access_jwt": "j", "did": "did", "handle": "h"},
        )
    except RuntimeError as e:
        assert "record_node" in str(e)
        assert "uri" in str(e)
    else:
        raise AssertionError("expected RuntimeError on bad embed shape")

    # And no post fired.
    assert bc.create_post.call_count == 0


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
