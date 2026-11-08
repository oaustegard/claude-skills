"""Offline tests: nothing here reaches Bluesky, Turso, GitHub or a model.

What is under test is the decision logic: which terms a cluster yields, how topic scores are normalised, the
screen, the judge's reply parsing, the round-robin quota, the weekly drop rules, insight matching, and the
guards that keep writes on Muninn's own list.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bsky
import curate
import store
import topics
import vet

ATLAS = [
    {"id": "wgsl-forge", "c": "WebGPU", "p": "Hand-written WGSL kernels for WebGPU on SwiftShader"},
    {"id": "wgsl-diffusion", "c": "WebGPU", "p": "A WGSL diffusion sampler on WebGPU, verified on SwiftShader"},
    {"id": "lfm-wgsl", "c": "WebGPU", "p": "LFM2.5 in WGSL with parity"},
    {"id": "haiku-cc", "c": "Agents", "p": "Haiku subagent briefs; subagent context filter"},
    {"id": "swarm", "c": "Agents", "p": "Haiku swarm of subagent workers on SWE-bench"},
    {"id": "erdos", "c": "Maths", "p": "Closed (compute exhausted)"},
]


# ── topics ─────────────────────────────────────────────────────────────

def test_cluster_terms_need_two_experiments_and_skip_ambiguous_words():
    ct = topics.cluster_terms(ATLAS)
    assert "WGSL" in ct["WebGPU"] and "SwiftShader" in ct["WebGPU"]
    assert "LFM2.5" not in ct["WebGPU"]                 # one experiment only, and a dotted token
    assert "subagent" in ct["Agents"]
    assert all(t.lower() != "haiku" for t in ct["Agents"])   # a search for Haiku returns poems
    assert ct["Maths"] == []


def test_topic_specs_put_seeds_first_and_cover_every_cluster():
    specs = topics.topic_specs(ATLAS, extra=[{"name": "promoted-x", "label": "X", "terms": ["a", "b", "c"]}])
    names = [s["name"] for s in specs]
    assert {"atlas-webgpu", "atlas-agents", "atlas-maths", "promoted-x"} <= set(names)
    assert sum(s["kind"] == "interest" for s in specs) == len(topics.load_assets()["interests"])
    norway = next(s for s in specs if s["name"] == "norway-politics")
    assert norway["lang"] is None                        # Norwegian posts are not lang:en


def test_positives_cap_per_author_and_drop_thin_terms():
    def post(i, did):
        return {"uri": f"at://{did}/p/{i}", "author": {"did": did}, "record": {"text": f"words about the thing {i}"}}
    hits = {"big": [post(i, "did:a") for i in range(40)] + [post(i, f"did:{i}") for i in range(40, 60)],
            "thin": [post(i, "did:z") for i in range(100, 105)]}
    texts, kept, ah = topics.positives({"terms": ["big", "thin"]}, hits)
    assert kept == ["big"]
    assert len(texts) == topics.MAX_PER_AUTHOR + 20
    assert ah["did:a"] == 40


def test_fit_and_norm_scores_separate_classes():
    np = pytest.importorskip("numpy")
    pytest.importorskip("sklearn")
    rng = np.random.default_rng(0)
    d = 16
    centre = np.zeros(d); centre[0] = 3
    Xpos = rng.normal(size=(300, d)) + centre
    Xneg = rng.normal(size=(300, d))
    m = topics.fit(Xpos, Xneg)
    assert m["auc"] > 0.9 and m["pos"] > m["base"]
    on = topics.norm_scores({"t": m}, rng.normal(size=(50, d)) + centre)["t"]
    off = topics.norm_scores({"t": m}, rng.normal(size=(50, d)))["t"]
    assert on > 0.7 and abs(off) < 0.3
    assert topics.fit(Xpos[:10], Xneg) is None
    assert topics.norm_scores({"t": m}, np.zeros((0, d))) == {}


# ── screen and judge ───────────────────────────────────────────────────

def test_stats_and_screen():
    now = 1_000_000_000
    posts = [{"t": now - k * 3600, "text": "x", "reply": k % 2 == 0} for k in range(20)]
    st = vet.stats(posts, now)
    assert st["n"] == 20 and st["reply_frac"] == 0.5 and st["last_days"] == 0
    assert vet.screen("alice.bsky.social", "Alice", "writes about rivers", st) is None
    assert vet.screen("someone.ap.brid.gy", "S", "", st) == "bridgy mirror"
    assert vet.screen("ainews.bsky.social", "AI News", "daily headlines", st) == "bot or feed words"
    assert vet.screen("x.bsky.social", "", "", {**st, "ppd": 55}) == "more than 40 posts a day"
    assert vet.screen("x.bsky.social", "", "", {**st, "last_days": 45}) == "no post in 30 days"
    assert vet.screen("x.bsky.social", "", "", {**st, "n": 4}) == "fewer than 10 posts"
    assert vet.stats([], now)["last_days"] is None


def test_parse_verdict_is_strict_about_keys():
    raw = 'Sure: {"0": {"keep": 1, "why": "researcher"}, "1": {"keep": 0, "why": "feed"}}'
    assert vet.parse_verdict(raw, 2) == {0: (True, "researcher"), 1: (False, "feed")}
    with pytest.raises(ValueError):
        vet.parse_verdict('{"0": {"keep": 1}}', 2)
    with pytest.raises(ValueError):
        vet.parse_verdict("no json here", 1)


def test_judge_marks_unusable_batch_as_unjudged_not_rejected():
    rows = [{"did": f"did:{i}", "handle": f"h{i}", "ppd": 1, "samples": []} for i in range(3)]
    vet.judge(rows, runner=lambda prompt: "garbage")
    assert all(r["keep"] is None for r in rows)          # None, never False: a failure is not a verdict
    vet.judge(rows, explore=True, runner=lambda p: json.dumps({str(i): {"keep": i % 2, "why": "w"} for i in range(3)}))
    assert [r["keep"] for r in rows] == [False, True, False]


# ── selection ──────────────────────────────────────────────────────────

def test_topic_order_is_round_robin_least_represented_first():
    groups = {"ai": ["a1", "a2", "a3"], "bike": ["b1"], "norway": ["n1", "n2"]}
    order = list(curate.topic_order(groups, {"ai": 2}))
    assert order[:3] == [("bike", "b1"), ("norway", "n1"), ("ai", "a1")]
    assert len(order) == 6


def test_pick_enforces_cap_on_keeps_and_skips_capped_topics():
    rows = {d: {"did": d, "handle": d, "ppd": 1, "samples": []} for d in ("a1", "a2", "a3", "b1", "b2")}
    order = curate.topic_order({"ai": ["a1", "a2", "a3"], "bike": ["b1", "b2"]}, {"ai": 1})
    seen = []

    def runner(prompt):
        n = len(re.findall(r"^\[\d+\] @", prompt, re.MULTILINE))
        seen.append(n)
        return json.dumps({str(i): {"keep": 1, "why": "ok"} for i in range(n)})
    kept, rejected = curate.pick(order, 4, rows, False, counts={"ai": 1}, cap=2, judge=runner)
    topics_kept = Counter(r["did"][0] for r in kept)
    assert topics_kept["a"] == 1 and topics_kept["b"] == 2   # ai already had one member, cap 2
    assert rejected == []


def test_apply_verdicts_leaves_missing_as_none():
    rows = [{"did": "did:1"}, {"did": "did:2"}]
    vet.apply_verdicts(rows, {"did:1": {"keep": 1, "why": "yes"}})
    assert rows[0]["keep"] is True and rows[1]["keep"] is None


# ── weekly rules ───────────────────────────────────────────────────────

class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def insights(self, since):
        return self.rows


def _member(kind, added, **kw):
    return {"handle": kw.pop("handle", "h"), "kind": kind, "topic": "t" if kind == "topic" else None, "norm": 0.5,
            "added": added, "weeks_below": kw.pop("weeks_below", 0), **kw}


def test_evaluate_members_rules():
    old = "2026-01-01"
    p = dict(curate.DEFAULTS)
    members = {
        "did:gone": _member("topic", old),
        "did:silent": _member("topic", old),
        "did:low1": _member("topic", old, weeks_below=0),
        "did:low2": _member("topic", old, weeks_below=1),
        "did:ok": _member("topic", old, weeks_below=1),
        "did:exp_old": _member("explore", old, handle="quiet.example"),
        "did:exp_ins": _member("explore", old, handle="lively.example"),
        "did:exp_new": _member("explore", curate.today()),
        "did:flaky": _member("topic", old, weeks_below=1),
    }
    rows = {
        "did:silent": {"handle": "s", "last_days": 90, "norm": 0.5, "topic": "t"},
        "did:low1": {"handle": "l1", "last_days": 2, "norm": 0.1, "topic": "t"},
        "did:low2": {"handle": "l2", "last_days": 2, "norm": 0.1, "topic": "t"},
        "did:ok": {"handle": "ok", "last_days": 2, "norm": 0.6, "topic": "u"},
        "did:exp_old": {"handle": "quiet.example", "last_days": 1, "norm": 0.0},
        "did:exp_ins": {"handle": "lively.example", "last_days": 1, "norm": 0.0},
        "did:exp_new": {"handle": "new", "last_days": 1, "norm": 0.0},
        "did:flaky": {"handle": "f", "fail": "feed unavailable"},
    }
    ins = [{"summary": "2026-11-01 insight from @lively.example https://bsky.app/...", "created_at": "2026-11-01"}]
    drops = {d["did"]: d["reason"] for d in curate.evaluate_members(members, rows, FakeStore(ins), p)}
    assert drops["did:gone"] == "account gone"
    assert drops["did:silent"].startswith("silent")
    assert drops["did:low2"].startswith("below topic threshold 2")
    assert drops["did:exp_old"].startswith("no insight")
    assert "did:low1" not in drops and members["did:low1"]["weeks_below"] == 1
    assert "did:ok" not in drops and members["did:ok"]["weeks_below"] == 0 and members["did:ok"]["topic"] == "u"
    assert "did:exp_ins" not in drops and members["did:exp_ins"]["insights"] == 1
    assert "did:exp_new" not in drops                       # inside its four-week grace
    assert "did:flaky" not in drops and members["did:flaky"]["weeks_below"] == 1   # no data, no change


def test_evaluate_members_skips_exploration_rule_without_insight_data():
    members = {"did:e": _member("explore", "2026-01-01")}
    rows = {"did:e": {"handle": "e", "last_days": 1, "norm": 0.0}}
    assert curate.evaluate_members(members, rows, FakeStore(None), dict(curate.DEFAULTS)) == []


def test_evaluate_members_caps_removals():
    p = {**curate.DEFAULTS, "max_remove": 2}
    members = {f"did:{i}": _member("topic", "2026-01-01") for i in range(5)}
    assert len(curate.evaluate_members(members, {}, FakeStore([]), p)) == 2


def test_insight_counts_match_did_or_handle_and_respect_start_dates():
    members = {"did:plc:abc": {"handle": "alice.example"}, "did:plc:xyz": {"handle": "bob.example"}}
    rows = [{"summary": "from did:plc:abc ...", "created_at": "2026-11-02"},
            {"summary": "https://bsky.app/profile/bob.example/post/1", "created_at": "2026-10-01"},
            {"summary": "mentions @Alice.Example again", "created_at": "2026-11-03"}]
    assert store.insight_counts(rows, members) == {"did:plc:abc": 2, "did:plc:xyz": 1}
    assert store.insight_counts(rows, members, {"did:plc:xyz": "2026-10-15"})["did:plc:xyz"] == 0


def test_state_file_roundtrip(tmp_path):
    s = store.Store(tmp_path / "state.json")
    st = s.load()
    assert st["members"] == {} and st["list_uri"] is None
    st["members"]["did:x"] = {"handle": "x"}
    s.save(st)
    assert store.Store(tmp_path / "state.json").load()["members"] == {"did:x": {"handle": "x"}}
    assert s.insights("2026-01-01") is None


def test_store_without_credentials_or_file_refuses(monkeypatch):
    monkeypatch.delenv("TURSO_URL", raising=False)
    monkeypatch.delenv("TURSO_TOKEN", raising=False)
    with pytest.raises(store.StoreError):
        store.Store()


# ── write guards ───────────────────────────────────────────────────────

def test_session_never_reads_oskars_credentials(monkeypatch):
    monkeypatch.delenv("MUNINN_BSKY_HANDLE", raising=False)
    monkeypatch.delenv("MUNINN_BSKY_APP_PASSWORD", raising=False)
    monkeypatch.setenv("BSKY_HANDLE", "austegard.com")
    monkeypatch.setenv("BSKY_APP_PASSWORD", "not-used")
    with pytest.raises(bsky.BskyError, match="MUNINN_BSKY"):
        bsky.session()


def test_session_refuses_an_unexpected_account(monkeypatch):
    monkeypatch.setenv("MUNINN_BSKY_HANDLE", "someone")
    monkeypatch.setenv("MUNINN_BSKY_APP_PASSWORD", "pw")
    monkeypatch.setattr(bsky, "_send", lambda req, tries=5: {"did": "did:plc:other", "handle": "x", "accessJwt": "j"})
    with pytest.raises(bsky.BskyError, match="refusing"):
        bsky.session()


def test_list_writes_refuse_a_list_in_another_repo(monkeypatch):
    auth = {"did": bsky.MUNINN_DID, "pds": "https://pds.example", "token": "t"}
    monkeypatch.setattr(bsky, "own_items", lambda a, u: pytest.fail("must not read before the guard"))
    with pytest.raises(bsky.BskyError, match="refusing"):
        bsky.add_items(auth, "at://did:plc:r2whjvupgfw55mllpksnombn/app.bsky.graph.list/3lankcdrlip2f", ["did:x"])
    with pytest.raises(bsky.BskyError, match="refusing"):
        bsky.remove_items(auth, "at://did:plc:someoneelse/app.bsky.graph.list/abc", ["did:x"])


def test_add_items_skips_existing_members(monkeypatch):
    auth = {"did": bsky.MUNINN_DID, "pds": "https://pds.example", "token": "t"}
    uri = f"at://{bsky.MUNINN_DID}/app.bsky.graph.list/abc"
    monkeypatch.setattr(bsky, "own_items", lambda a, u: {"did:old": f"at://{bsky.MUNINN_DID}/x/1"})
    sent = []
    monkeypatch.setattr(bsky, "post", lambda ep, body, base, token: sent.append(body))
    assert bsky.add_items(auth, uri, ["did:old", "did:new", "did:new"]) == ["did:new"]
    assert len(sent) == 1 and [w["value"]["subject"] for w in sent[0]["writes"]] == ["did:new"]


def test_memory_text_names_changes():
    out = {"date": "2026-11-15", "list_url": "https://bsky.app/profile/m/lists/x",
           "members": {"total": 3, "topic": 2, "explore": 1},
           "added": [{"handle": "a", "topic_label": "cycling"}, {"handle": "b"}],
           "removed": [{"handle": "c", "reason": "silent 70 days"}],
           "topics_fitted": {"x": {}}, "topics_skipped": [], "seconds": 12, "themes": ["rivers (3)"]}
    t = curate.memory_text("refresh", out)
    assert "@a (cycling)" in t and "@b (explore)" in t and "@c (silent 70 days)" in t and "rivers (3)" in t


def test_read_digest_keeps_members_own_recent_posts(tmp_path, monkeypatch):
    now = curate.time.time()
    iso = curate.dt.datetime.fromtimestamp(now - 3600, curate.dt.timezone.utc).isoformat()
    old = curate.dt.datetime.fromtimestamp(now - 20 * 86400, curate.dt.timezone.utc).isoformat()
    state = store.empty_state() | {
        "list_uri": f"at://{bsky.MUNINN_DID}/app.bsky.graph.list/abc",
        "members": {"did:plc:a": {"handle": "a.example", "kind": "explore"},
                    "did:plc:b": {"handle": "b.example", "kind": "topic", "topic": "cycling"}},
        "topics_last_run": {"cycling": {"label": "cycling and training physiology"}}}
    (tmp_path / "s.json").write_text(json.dumps(state))

    def item(did, rkey, text, t, reason=False):
        it = {"post": {"uri": f"at://{did}/app.bsky.feed.post/{rkey}", "author": {"did": did}, "indexedAt": t,
                       "record": {"text": text}, "likeCount": 3}}
        return it | ({"reason": {"$type": "repost"}} if reason else {})
    feed = [item("did:plc:a", "1", "a long enough thought about rivers and dams", iso),
            item("did:plc:b", "2", "threshold intervals today felt very different", iso),
            item("did:plc:b", "3", "a repost should not count at all here", iso, reason=True),
            item("did:plc:x", "4", "not a member of the list at all", iso),
            item("did:plc:a", "5", "an old post from three weeks ago now", old)]
    monkeypatch.setattr(bsky, "list_feed", lambda uri, since: feed)
    out = tmp_path / "d.md"
    curate.main(["--state-file", str(tmp_path / "s.json"), "read", "--out", str(out)])
    text = out.read_text()
    assert "/profile/did:plc:a/post/1" in text and "/profile/did:plc:b/post/2" in text
    assert "post/3" not in text and "post/4" not in text and "post/5" not in text
    assert "[explore]" in text and "[cycling and training physiology]" in text


def test_pick_without_judge_collects_candidates_for_an_outside_judge(monkeypatch):
    monkeypatch.setattr(vet, "available", lambda: False)
    monkeypatch.setattr(curate, "PENDING", [])
    rows = {f"d{i}": {"did": f"d{i}", "handle": f"h{i}", "samples": []} for i in range(10)}
    kept, rejected = curate.pick([f"d{i}" for i in range(10)], 2, rows, True)
    assert kept == [] and rejected == []
    assert [r["did"] for r in curate.PENDING] == ["d0", "d1", "d2", "d3", "d4", "d5"]
    assert all(r["explore"] for r in curate.PENDING)


def test_set_param_and_restore_state(tmp_path):
    f = str(tmp_path / "s.json")
    curate.main(["--state-file", f, "set-param", "topic_drop", "0.15"])
    assert json.loads(Path(f).read_text())["params"] == {"topic_drop": 0.15}
    curate.main(["--state-file", f, "set-param", "topic_drop", "default"])
    assert json.loads(Path(f).read_text())["params"] == {}
    backup = tmp_path / "b.json"
    backup.write_text(json.dumps(store.empty_state() | {"list_uri": "at://x", "members": {"did:a": {}}}))
    curate.main(["--state-file", f, "restore-state", str(backup)])
    assert json.loads(Path(f).read_text())["members"] == {"did:a": {}}


def test_cross_negatives_sample_other_topics_and_skip_own_term_matches():
    texts = {"bike": ["my FTP went up", "zone 2 again", "cycling in rain"],
             "ai": ["LLM evals", "agents that ride FTP servers", "a cycling LLM"]}
    out = topics.cross_negatives("bike", texts, ["FTP", "cycling"], per_topic=5)
    assert list(out) == ["ai"]
    assert out["ai"] == [0]                    # the two AI posts naming FTP or cycling are not negatives
    assert topics.term_matcher(["AI Act"]).search("the ai act passed") is not None
    assert topics.term_matcher(["RAG"]).search("ragged edges") is None


def test_weeks_below_counts_once_per_week():
    p = dict(curate.DEFAULTS)
    members = {"did:t": _member("topic", "2026-01-01", weeks_below=1, last_eval=curate.today())}
    rows = {"did:t": {"handle": "t", "last_days": 1, "norm": 0.1, "topic": "t"}}
    assert curate.evaluate_members(members, rows, FakeStore([]), p) == []
    assert members["did:t"]["weeks_below"] == 1
    members["did:t"]["last_eval"] = "2026-01-01"
    assert len(curate.evaluate_members(members, rows, FakeStore([]), p)) == 1


def test_themes_need_three_members_and_drop_chatter():
    pytest.importorskip("sklearn")
    member = {f"m{i}": ["salmon watershed restoration yeah really", f"distinct{i} words here"] for i in range(4)}
    member["m9"] = ["entirely unrelated quilting"]
    bg = ["cat photo cute", "good morning everyone", "weekend plans coffee"] * 10
    found = " ".join(curate.themes(member, bg))
    assert "salmon" in found and "yeah" not in found and "really" not in found and "quilting" not in found
