"""Offline tests for which credential pair browsing-bluesky authenticates with.

`requests.post` is stubbed, so nothing reaches bsky.social. What is under
test is the selection: which pair is preferred, what happens when only one is
present, and whether a caller can find out which one answered.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Loaded by file path rather than by name. `scripts/__init__.py` here opens
# with `from .bsky import ...`, and putting that directory on sys.path makes
# pytest's default prepend import mode walk up to the skill directory and try
# to import `browsing-bluesky/__init__.py` as a bare top-level `__init__` —
# which fails, since a hyphenated directory is not an importable package.
_SPEC = importlib.util.spec_from_file_location(
    "bsky_under_test", Path(__file__).resolve().parents[1] / "scripts" / "bsky.py")
bsky = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bsky)
IDENTITIES, IDENTITY_ORDER = bsky.IDENTITIES, bsky.IDENTITY_ORDER

PAIRS = ["MUNINN_BSKY_HANDLE", "MUNINN_BSKY_APP_PASSWORD",
         "BSKY_HANDLE", "BSKY_APP_PASSWORD", "BSKY_IDENTITY"]


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    """No ambient credentials, no cached session, no live requests."""
    for v in PAIRS:
        monkeypatch.delenv(v, raising=False)
    bsky.clear_session()

    class Resp:
        status_code = 200

        def __init__(self, handle):
            self._handle = handle

        def raise_for_status(self):
            pass

        def json(self):
            return {"accessJwt": "jwt", "refreshJwt": "refresh",
                    "did": f"did:plc:{self._handle}", "handle": self._handle}

    def fake_post(url, json=None, headers=None, timeout=None, **kw):
        return Resp(json["identifier"] if json and "identifier" in json else "?")

    monkeypatch.setattr(bsky.requests, "post", fake_post)
    yield
    bsky.clear_session()


def set_pair(monkeypatch, prefix, handle):
    monkeypatch.setenv(f"{prefix}BSKY_HANDLE", handle)
    monkeypatch.setenv(f"{prefix}BSKY_APP_PASSWORD", "pw")


# ── selection ──────────────────────────────────────────────────────────

def test_muninn_wins_when_both_pairs_are_set(monkeypatch):
    """invariant: with both pairs present, the Muninn pair authenticates.

    This is the whole defect. A booted container holds both, and reading the
    unprefixed one first meant every authenticated read came back as the
    account owner without saying so.

    refuted: reversing IDENTITY_ORDER -> this test and
    test_authenticated_identity_names_the_pair_that_answered went red, both
    reporting owner/oskar.example.
    """
    set_pair(monkeypatch, "MUNINN_", "muninn.example")
    set_pair(monkeypatch, "", "oskar.example")
    assert bsky.get_authenticated_user() == "muninn.example"


def test_the_documented_pair_alone_still_authenticates(monkeypatch):
    """invariant: BSKY_* on its own works, with no Muninn pair anywhere.

    The skill documents the unprefixed pair. Preferring Muninn must not
    break a machine that only ever had the documented one.

    refuted: dropping "owner" from IDENTITY_ORDER -> this test went red with
    get_authenticated_user() returning None, alongside
    test_a_half_set_pair_is_skipped_not_half_used and
    test_every_identity_is_reachable_by_default.
    """
    set_pair(monkeypatch, "", "oskar.example")
    assert bsky.get_authenticated_user() == "oskar.example"


def test_no_credentials_stays_unauthenticated(monkeypatch):
    assert bsky._credentials() is None
    assert bsky.is_authenticated() is False
    assert bsky.authenticated_identity() is None


def test_a_half_set_pair_is_skipped_not_half_used(monkeypatch):
    """invariant: a pair missing either half is not a candidate.

    refuted: testing `handle or password` instead of `handle and password`
    -> this test alone went red, createSession being called with an empty
    password for muninn.example.
    """
    monkeypatch.setenv("MUNINN_BSKY_HANDLE", "muninn.example")
    set_pair(monkeypatch, "", "oskar.example")
    assert bsky.get_authenticated_user() == "oskar.example"


# ── explicit selection ─────────────────────────────────────────────────

def test_identity_owner_selects_the_unprefixed_pair(monkeypatch):
    set_pair(monkeypatch, "MUNINN_", "muninn.example")
    set_pair(monkeypatch, "", "oskar.example")
    monkeypatch.setenv("BSKY_IDENTITY", "owner")
    assert bsky.get_authenticated_user() == "oskar.example"


def test_a_named_identity_does_not_fall_through_to_the_other(monkeypatch):
    """invariant: BSKY_IDENTITY names one pair; an absent one is not substituted.

    Falling through would reintroduce the defect through the door built to
    prevent it — asking for muninn and silently getting the owner.

    refuted: letting the named branch fall through to IDENTITY_ORDER -> this
    test alone went red, returning oskar.example.
    """
    set_pair(monkeypatch, "", "oskar.example")
    monkeypatch.setenv("BSKY_IDENTITY", "muninn")
    assert bsky._credentials() is None
    assert bsky.get_authenticated_user() is None


def test_an_unknown_identity_raises_rather_than_falling_back(monkeypatch):
    """invariant: a typo'd BSKY_IDENTITY is a configuration error.

    The skill's graceful-degradation promise covers auth failure, not
    misconfiguration: silently reading as the public AppView because a
    variable was misspelled is worse than a traceback.

    refuted: returning None for an unknown name -> this test alone went red,
    no exception raised.
    """
    set_pair(monkeypatch, "MUNINN_", "muninn.example")
    monkeypatch.setenv("BSKY_IDENTITY", "muninn ")  # trailing space is fine
    assert bsky.get_authenticated_user() == "muninn.example"
    bsky.clear_session()
    monkeypatch.setenv("BSKY_IDENTITY", "nobody")
    with pytest.raises(ValueError, match="BSKY_IDENTITY"):
        bsky._credentials()


# ── reporting ──────────────────────────────────────────────────────────

def test_authenticated_identity_names_the_pair_that_answered(monkeypatch):
    """invariant: the caller can tell which identity is reading.

    refuted: dropping session["_identity"] in _create_session -> this test
    went red with identity "unknown", alongside
    test_a_refresh_carries_the_identity_across.
    """
    set_pair(monkeypatch, "MUNINN_", "muninn.example")
    set_pair(monkeypatch, "", "oskar.example")
    assert bsky.authenticated_identity() == {
        "identity": "muninn", "handle": "muninn.example",
        "did": "did:plc:muninn.example"}


def test_a_refresh_carries_the_identity_across(monkeypatch):
    """invariant: refreshSession does not blank the identity label.

    refreshSession's response has no such field, so a refresh that replaced
    the cache wholesale would leave every later call reporting "unknown".

    refuted: dropping the carry-across line -> this test alone went red with
    identity "unknown" after the refresh.
    """
    set_pair(monkeypatch, "MUNINN_", "muninn.example")
    bsky.get_authenticated_user()

    def fake_refresh(url, json=None, headers=None, timeout=None, **kw):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"accessJwt": "jwt2", "refreshJwt": "r2",
                        "did": "did:plc:muninn.example",
                        "handle": "muninn.example"}
        return R()

    monkeypatch.setattr(bsky.requests, "post", fake_refresh)
    assert bsky._refresh_session() is not None
    assert bsky.authenticated_identity()["identity"] == "muninn"


# ── registry ───────────────────────────────────────────────────────────

def test_every_identity_is_reachable_by_default():
    """invariant: IDENTITY_ORDER covers every key in IDENTITIES.

    A pair added to the dict but left out of the order is unreachable
    unless someone names it, which is a capability that exists and does
    nothing.

    refuted: adding a third IDENTITIES key without ordering it -> this test
    alone went red, naming the orphan.
    """
    assert len(IDENTITIES) >= 2
    assert set(IDENTITY_ORDER) == set(IDENTITIES)
    assert len(IDENTITY_ORDER) == len(IDENTITIES)


# totality: ratchet — both identities this skill has shipped. Dropping either
# is a behaviour change the live enumeration above cannot see: it loops
# whatever IDENTITIES now holds and stays green on a loss.
@pytest.mark.parametrize("name,prefix", [("muninn", "MUNINN_"), ("owner", "")])
def test_each_shipped_identity_keeps_its_prefix(name, prefix):
    """invariant: neither identity is dropped or repointed.

    refuted: removing "owner" from IDENTITIES -> six went red, this one on
    the owner parametrisation and with it every test that reaches the
    unprefixed pair: the reachability check, the documented-pair path, the
    half-pair skip, the explicit BSKY_IDENTITY=owner selection, and the
    no-credentials case.
    """
    assert IDENTITIES[name] == prefix
