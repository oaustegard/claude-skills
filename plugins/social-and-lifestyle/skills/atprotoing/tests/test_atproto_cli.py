"""Offline tests for the three source-routed commands added in 0.3.0.

Every test stubs `http`, so nothing here touches plc.directory, Constellation
or UFOs. What is under test is the shaping: which source each command picks,
how it folds the response, and what the digest says when the answer is empty.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import atproto  # noqa: E402


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    """A per-test SQLite scratch, so the identity cache never leaks across."""
    monkeypatch.setattr(atproto, "DB", str(tmp_path / "scratch.db"))


@pytest.fixture
def routes(monkeypatch):
    """Stub `http` with a url-substring -> payload table."""
    table: dict[str, object] = {}
    calls: list[str] = []

    def fake(url, params=None, body=None, headers=None, timeout=25, tries=3):
        calls.append(f"{url}?{params}" if params else url)
        # Routes match on the URL's tail, not anywhere in it: query strings
        # live in `params`, so every request URL ends at its path. Substring
        # matching would route /did:plc:aaa/log/audit to the /did:plc:aaa
        # DID-document stub and hand identity_history the wrong object.
        hits = [f for f in table if url.endswith(f)]
        if not hits:
            raise AssertionError(f"unstubbed request: {url} {params}")
        payload = table[hits[0]]
        if isinstance(payload, Exception):
            raise payload
        return payload

    monkeypatch.setattr(atproto, "http", fake)
    return table, calls


IDENT = {
    "did:plc:aaa": {
        "alsoKnownAs": ["at://alice.example"],
        "service": [{"type": "AtprotoPersonalDataServer",
                     "serviceEndpoint": "https://pds.example"}],
    }
}


def stub_identity(table):
    table["identity.resolveHandle"] = {"did": "did:plc:aaa"}
    table["plc.directory/did:plc:aaa"] = IDENT["did:plc:aaa"]


# ── backlinks ──────────────────────────────────────────────────────────

def test_backlinks_counts_drop_empty_paths_and_sort_by_volume(routes):
    """invariant: the counts digest lists only non-empty sources, busiest first.

    refuted: `if n:` -> `if True:` in backlinks -> this test alone went red
    (the zero-record sh.tangled.repo.issue row survived into sources).
    """
    table, _ = routes
    stub_identity(table)
    table["/links/all"] = {"links": {
        "app.bsky.graph.follow": {".subject": {"records": 9, "distinct_dids": 9}},
        "sh.tangled.repo.issue": {".owner": {"records": 0, "distinct_dids": 0}},
        "com.example.vouch": {".subject": {"records": 40, "distinct_dids": 3}},
    }}
    out = atproto.backlinks("alice.example")
    assert [r["collection"] for r in out["sources"]] == [
        "com.example.vouch", "app.bsky.graph.follow"]
    assert out["total"] == 49
    assert out["source_count"] == 2
    assert out["asked"] == "alice.example"
    assert out["target"] == "did:plc:aaa"


def test_limited_counts_still_report_the_whole_index(routes):
    """invariant: --limit slices what is shown, never what is counted.

    refuted: dropping source_count and printing len(sources) -> this test and
    test_backlinks_counts_drop_empty_paths_and_sort_by_volume went red, and
    the live header claimed "62 links from 3 sources" on a target with five.
    """
    table, _ = routes
    stub_identity(table)
    table["/links/all"] = {"links": {
        f"com.example.c{i}": {".subject": {"records": i, "distinct_dids": 1}}
        for i in range(1, 7)}}
    out = atproto.backlinks("alice.example", limit=2)
    assert len(out["sources"]) == 2
    assert out["source_count"] == 6
    assert out["total"] == 21
    assert "from 6 sources (showing 2)" in atproto.fmt_backlinks(out)


def test_backlinks_reaches_lexicons_interactions_cannot(routes):
    """invariant: backlinks is not restricted to the five LINK_PATHS collections.

    refuted: filtering the links_all loop to LINK_PATHS collections -> this
    test and the counts test went red; com.example.vouch vanished.
    """
    table, _ = routes
    stub_identity(table)
    exotic = "com.example.vouch"
    assert exotic not in {c for c, _p, _k in atproto.LINK_PATHS}
    table["/links/all"] = {"links": {
        exotic: {".subject": {"records": 2, "distinct_dids": 2}}}}
    assert atproto.backlinks("alice.example")["sources"][0]["collection"] == exotic


def test_backlinks_passes_did_and_at_uri_through_unresolved(routes):
    """invariant: only a handle costs a resolve; DIDs and at:// URIs are already keys.

    refuted: dropping "did:" from the backlink_target passthrough -> this
    test alone went red on the unexpected resolveHandle call.
    """
    table, calls = routes
    table["/links/all"] = {"links": {}}
    for target in ("did:plc:zzz", "at://did:plc:zzz/app.bsky.feed.post/abc"):
        assert atproto.backlinks(target)["target"] == target
    assert not any("resolveHandle" in c for c in calls)


def test_backlinks_enumeration_resolves_handles(routes):
    """invariant: enumerated records carry handles, not bare DIDs.

    refuted: returning r["did"] instead of the resolve_many lookup -> this
    test alone went red.
    """
    table, _ = routes
    stub_identity(table)
    table["/links"] = {"linking_records": [
        {"did": "did:plc:aaa", "collection": "com.example.vouch", "rkey": "r1"}],
        "cursor": None}
    out = atproto.backlinks("alice.example", "com.example.vouch", ".subject")
    assert out["records"] == [{
        "handle": "alice.example",
        "uri": "at://did:plc:aaa/com.example.vouch/r1"}]


def test_fmt_backlinks_says_nothing_rather_than_printing_an_empty_table():
    assert "Nothing references" in atproto.fmt_backlinks(
        {"target": "did:plc:aaa", "asked": "alice.example",
         "sources": [], "total": 0})


# ── identity ───────────────────────────────────────────────────────────

AUDIT = [
    {"createdAt": "2024-11-11T03:10:53.000Z", "nullified": False, "operation": {
        "type": "plc_operation", "alsoKnownAs": ["at://alice.bsky.social"],
        "services": {"atproto_pds": {"endpoint": "https://old.example"}},
        "rotationKeys": ["did:key:1"]}},
    {"createdAt": "2025-01-02T00:00:00.000Z", "nullified": False, "operation": {
        "type": "plc_operation", "alsoKnownAs": ["at://alice.example"],
        "services": {"atproto_pds": {"endpoint": "https://new.example"}},
        "rotationKeys": ["did:key:1"]}},
]


def test_identity_history_names_what_changed_at_each_step(routes):
    """invariant: the first entry is a creation; later entries name their deltas.

    refuted: hardcoding `changed = []` -> this test alone went red on the
    second entry's empty delta set.
    """
    table, _ = routes
    stub_identity(table)
    table["/log/audit"] = AUDIT
    ev = atproto.identity_history("alice.example")["events"]
    assert ev[0]["changed"] == []
    assert set(ev[1]["changed"]) == {"handle", "pds"}
    assert ev[1]["prev"]["handle"] == "alice.bsky.social"
    assert ev[1]["pds"] == "https://new.example"


def test_identity_history_reads_both_pds_endpoint_spellings(routes):
    """invariant: PLC writes the PDS as serviceEndpoint or endpoint; both parse.

    refuted: reading only `endpoint` -> this test alone went red with
    pds None.
    """
    table, _ = routes
    stub_identity(table)
    table["/log/audit"] = [{"createdAt": "2024-01-01T00:00:00Z", "nullified": False,
                            "operation": {"type": "plc_operation",
                                          "alsoKnownAs": ["at://alice.example"],
                                          "services": {"atproto_pds": {
                                              "serviceEndpoint": "https://a.example"}},
                                          "rotationKeys": []}}]
    assert atproto.identity_history("alice.example")["events"][0][
        "pds"] == "https://a.example"


def test_fmt_identity_states_a_single_entry_history_plainly(routes):
    table, _ = routes
    stub_identity(table)
    table["/log/audit"] = AUDIT[:1]
    out = atproto.fmt_identity(atproto.identity_history("alice.example"))
    assert "Never renamed, never migrated." in out
    assert "created" in out


# ── lexicons ───────────────────────────────────────────────────────────

ROWS = [
    {"nsid": "app.bsky.feed.like", "creates": 9, "updates": 0, "deletes": 0,
     "dids_estimate": 9},
    {"nsid": "com.atproto.lexicon.schema", "creates": 8, "updates": 0,
     "deletes": 0, "dids_estimate": 8},
    {"nsid": "chat.bsky.actor.declaration", "creates": 7, "updates": 0,
     "deletes": 0, "dids_estimate": 7},
    {"nsid": "fm.teal.feed.play", "creates": 6, "updates": 0, "deletes": 0,
     "dids_estimate": 6},
]


def test_lexicons_others_drops_every_core_prefix(routes):
    """invariant: --others excludes each member of CORE_PREFIXES, and only those.

    refuted: dropping "chat.bsky." from CORE_PREFIXES -> this test alone
    went red; chat.bsky.actor.declaration leaked into kept.
    """
    table, _ = routes
    table["/collections"] = {"collections": ROWS}
    live = atproto.CORE_PREFIXES
    assert len(live) >= 3
    kept = [r["nsid"] for r in atproto.lexicons(others=True)]
    assert kept == ["fm.teal.feed.play"]
    for prefix in live:
        assert any(r["nsid"].startswith(prefix) for r in ROWS), prefix


def test_lexicons_overfetches_when_filtering(routes):
    """invariant: filtering asks upstream for more than the caller's limit.

    The core collections occupy the head of the leaderboard, so a limit-sized
    page would come back empty after the filter.

    refuted: dropping the `* 8` -> this test alone went red on limit 3.
    """
    table, calls = routes
    table["/collections"] = {"collections": ROWS}
    atproto.lexicons(limit=3, others=True)
    assert "'limit': 24" in calls[-1]
    calls.clear()
    atproto.lexicons(limit=3)
    assert "'limit': 3" in calls[-1]


def test_lexicons_query_searches_instead_of_listing(routes):
    table, calls = routes
    table["/search"] = {"matches": [ROWS[3]]}
    assert atproto.lexicons("teal")[0]["nsid"] == "fm.teal.feed.play"
    assert "/search" in calls[-1]


def test_lexicons_hours_windows_the_leaderboard(routes):
    table, calls = routes
    table["/collections"] = {"collections": ROWS}
    atproto.lexicons(hours=24)
    assert "since" in calls[-1]
    calls.clear()
    atproto.lexicons()
    assert "since" not in calls[-1]


def test_lexicon_schema_derives_the_publisher_by_reversing_two_segments(routes):
    """invariant: com.whtwnd.blog.entry is published by whtwnd.com, not blog.whtwnd.com.

    refuted: reversing the two segments the other way -> this test alone
    went red; the resolve went to com.whtwnd.
    """
    table, calls = routes
    table["identity.resolveHandle"] = {"did": "did:plc:aaa"}
    table["plc.directory/did:plc:aaa"] = IDENT["did:plc:aaa"]
    table["getRecord"] = {"uri": "at://did:plc:aaa/com.atproto.lexicon.schema/x"}
    atproto.lexicon_schema("com.whtwnd.blog.entry")
    assert any("'handle': 'whtwnd.com'" in c for c in calls)


def test_lexicon_schema_missing_record_says_so_without_the_http_noise(routes):
    """refuted: with the RecordNotFound branch removed, the message is a bare HTTP 400."""
    table, _ = routes
    table["identity.resolveHandle"] = {"did": "did:plc:aaa"}
    table["plc.directory/did:plc:aaa"] = IDENT["did:plc:aaa"]
    table["getRecord"] = atproto.Unavailable('HTTP 400: {"error":"RecordNotFound"}')
    with pytest.raises(atproto.Unavailable, match="publishes no schema record"):
        atproto.lexicon_schema("com.whtwnd.blog.entry")


# ── cli wiring ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("argv", [
    ["backlinks", "alice.example"],
    ["identity", "alice.example"],
    ["lexicons"],
])
def test_new_commands_reach_a_handler(routes, capsys, argv):
    """invariant: every command added in 0.3.0 is wired into main's dispatch.

    refuted: disabling the `identity` dispatch branch -> this test alone
    went red, on the identity parametrisation, with empty stdout.
    """
    table, _ = routes
    stub_identity(table)
    table["/links/all"] = {"links": {}}
    table["/log/audit"] = AUDIT[:1]
    table["/collections"] = {"collections": ROWS}
    assert atproto.main(argv) == 0
    assert capsys.readouterr().out.strip()


def test_unavailable_exits_two_with_the_reason_on_stderr(routes, capsys):
    table, _ = routes
    stub_identity(table)
    table["/links/all"] = atproto.Unavailable("Constellation is down")
    assert atproto.main(["backlinks", "alice.example"]) == 2
    assert "Constellation is down" in capsys.readouterr().err


def test_every_exported_name_resolves():
    """invariant: every member of __all__ is importable from the package.

    refuted: dropping `backlinks` from the `from .scripts.atproto import`
    list while leaving it in `__all__` -> this test alone went red.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import atprotoing

    assert len(atprotoing.__all__) >= 12
    missing = [n for n in atprotoing.__all__ if not hasattr(atprotoing, n)]
    assert not missing, missing
