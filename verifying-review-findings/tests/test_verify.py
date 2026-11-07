"""Offline tests for verify.py: grounding, windows, policy, gate, reply parsing. No network."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verify  # noqa: E402

SRC = '''import json


def total(items):
    total = 0
    for i in range(len(items) - 1):
        total += items[i]
    return total


def load(path):
    with open(path) as fh:
        return json.load(fh)
'''


def answers(confirmed=0.0, refuted=0.0, insufficient=0.0, sev=(0, 0, 1, 0, 0), fix=None):
    a = {"verdict": {"type": "choice", "probabilities": {
            "confirmed": confirmed, "refuted": refuted, "insufficient_context": insufficient}},
         "severity": {"type": "score", "probabilities": {str(i): p for i, p in enumerate(sev)}}}
    if fix is not None:
        a["fix_ok"] = {"type": "noul", "noul": fix}
    return a


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "util.py").write_text(SRC)
    return tmp_path


def finding(**kw):
    base = {"file": "src/util.py", "description": "claim", "code_quote": "for i in range(len(items) - 1):"}
    return {**base, **kw}


# ---------------------------------------------------------------- input

def test_load_accepts_list_wrapper_and_reportfindings_shape():
    fs = verify.load_findings({"findings": [{"file": "a.py", "summary": "s", "failure_scenario": "x -> y"}]})
    assert fs[0]["description"] == "s\nFailure scenario: x -> y"
    assert fs[0]["id"] == "1"


def test_load_rejects_missing_file_and_duplicate_ids():
    with pytest.raises(verify.VerifyError):
        verify.load_findings([{"description": "no file"}])
    with pytest.raises(verify.VerifyError):
        verify.load_findings([{"file": "a", "id": 1}, {"file": "b", "id": "1"}])


def test_claimed_severity_does_not_collide_with_verifier_severity():
    f = verify.load_findings([{"file": "a.py", "severity": "high"}])[0]
    assert f["claimed_severity"] == "high" and "severity" not in f


# ---------------------------------------------------------------- grounding

def test_locate_ignores_whitespace_differences():
    assert verify.locate(SRC, "total = 0\nfor i in range(len(items) - 1):") == (5, 6)
    assert verify.locate(SRC, "with   open(path)  as fh:") == (12, 12)


def test_locate_misses_paraphrase_and_prefers_nearest_match():
    assert verify.locate(SRC, "for i in range(len(items)):") is None
    text = "x = 1\n" + "pass\n" * 20 + "x = 1\n"
    assert verify.locate(text, "x = 1", near=20) == (22, 22)
    assert verify.locate(text, "x = 1") == (1, 1)


def test_ground_drops_missing_and_ungrounded_quotes(repo):
    fs = verify.load_findings([finding(code_quote=""), finding(code_quote="total = sum(items)"),
                               finding(file="nope.py"), finding()])
    out = verify.prepare(fs, repo, None, None)
    assert [f.get("reason") for f in out[:3]] == ["missing_code_quote", "ungrounded_code_quote", "file_not_found"]
    assert "request" in out[3] and out[3]["grounding"]["lines"] == [6, 6]


def test_ground_refuses_paths_that_escape_the_repo(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.py"
    outside.write_text("for i in range(len(items) - 1):\n")
    f = verify.load_findings([finding(file=str(Path("..") / outside.parent.name / "secret.py"))])
    assert verify.prepare(f, repo, None, None)[0]["reason"] == "file_not_found"


def test_window_covers_enclosing_top_level_block_and_marks_quote(repo):
    out = verify.prepare(verify.load_findings([finding()]), repo, None, None)[0]
    code = out["request"]["state"]["code"]
    assert "def total(items):" in code
    assert ">  6 |     for i in range(len(items) - 1):" in code
    assert [ln for ln in code.splitlines() if ln.startswith(">")] == [">  6 |     for i in range(len(items) - 1):"]


def test_window_is_clamped_on_long_blocks():
    lines = ["def f():"] + ["    x = 1"] * 1000
    lo, hi = verify.window(lines, 500, 500)
    assert hi - lo + 1 <= verify.MAX_LINES and lo <= 500 <= hi


def test_request_carries_fix_question_only_with_a_fix(repo):
    a, b = verify.prepare(verify.load_findings([finding(), finding(fix="range(len(items))")]), repo, None, None)
    assert "fix_ok" not in a["request"]["questions"] and "fix_ok" in b["request"]["questions"]


def test_diff_hunks_selects_the_finding_file():
    diff = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
            "diff --git a/y.py b/y.py\n--- a/y.py\n+++ b/y.py\n@@ -1 +1 @@\n-c\n+d\n")
    assert verify.diff_hunks(diff, "y.py") == "@@ -1 +1 @@\n-c\n+d"
    assert verify.diff_hunks(diff, "z.py") is None


def test_fingerprint_is_whitespace_insensitive():
    a = verify.fingerprint({"file": "a.py", "code_quote": "x =  1\n  y"})
    assert a == verify.fingerprint({"file": "a.py", "code_quote": "x = 1 y"})
    assert a != verify.fingerprint({"file": "b.py", "code_quote": "x = 1 y"})


# ---------------------------------------------------------------- policy

@pytest.mark.parametrize("probs,status,reason", [
    ((0.9, 0.1, 0.0), "confirmed", None),
    ((0.1, 0.8, 0.1), "dropped", "refuted_by_verifier"),
    ((0.4, 0.5, 0.1), "uncertain", "split_verdict"),
    ((0.2, 0.2, 0.6), "uncertain", "needs_more_context"),
])
def test_judge_thresholds(probs, status, reason):
    f = verify.judge({"id": "1"}, answers(*probs), 0.7, 0.7)
    assert (f["status"], f["reason"]) == (status, reason)


def test_judge_rejects_unexpected_shapes():
    with pytest.raises(verify.VerifyError):
        verify.judge({"id": "1"}, {"verdict": {"choice": "confirmed"}}, 0.7, 0.7)
    with pytest.raises(verify.VerifyError):
        verify.judge({"id": "1"}, answers(0, 0, 0), 0.7, 0.7)


def test_severity_accepts_label_keys_and_expected_level():
    a = answers(0.9, 0.1)
    a["severity"]["probabilities"] = {"info": 0, "low": 0, "medium": 0.2, "high": 0.8, "critical": 0}
    f = verify.judge({"id": "1"}, a, 0.7, 0.7)
    assert f["severity"]["expected"] == "high"
    assert verify.p_at_least(f, "high") == pytest.approx(0.8)


def test_gate_counts_only_confirmed_findings_at_or_above_level():
    hi = verify.judge({"id": "a"}, answers(0.9, 0.1, sev=(0, 0, 0.2, 0.7, 0.1)), 0.7, 0.7)
    unsure = verify.judge({"id": "b"}, answers(0.5, 0.4, sev=(0, 0, 0, 0, 1)), 0.7, 0.7)
    rep = verify.report([hi, unsure], "jev", "high", 0.5)
    assert rep["gate"]["tripped"] == ["a"] and verify.exit_code(rep) == 1
    assert verify.report([hi], "jev", "critical", 0.5)["gate"]["tripped"] == []


def test_unverified_finding_makes_the_run_incomplete_never_clean(repo):
    fs = verify.prepare(verify.load_findings([finding()]), repo, None, None)

    def broken(_):
        raise verify.VerifyError("HTTP 503")

    rep = verify.report(verify.verify(fs, "jev", broken, 0.7, 0.7), "jev", None, 0.5)
    assert rep["complete"] is False and verify.exit_code(rep) == 3
    assert rep["findings"][0]["status"] == "unverified"


def test_gate_trip_outranks_incomplete():
    hi = verify.judge({"id": "a"}, answers(0.9, 0.1, sev=(0, 0, 0, 1, 0)), 0.7, 0.7)
    rep = verify.report([hi, {"id": "b", "status": "unverified"}], "jev", "high", 0.5)
    assert verify.exit_code(rep) == 1


# ---------------------------------------------------------------- transports and replies

def test_parse_reply_reads_muninn_decide_output_with_usage_line():
    text = json.dumps(answers(0.9, 0.1)) + "\n[usage: jev-1.14.0 input 386, output 63 tokens]"
    assert verify.parse_reply(text)["verdict"]["probabilities"]["confirmed"] == 0.9
    assert verify.parse_reply({"answers": {"x": 1}}) == {"x": 1}
    with pytest.raises(verify.VerifyError):
        verify.parse_reply("no json here")


def test_pick_transport_without_credentials(monkeypatch):
    for k in ("TYPESAFE_API_KEY", "CF_API_TOKEN", "CF_ACCOUNT_ID"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(verify.VerifyError, match="no Jev transport"):
        verify.pick_transport("auto")
    with pytest.raises(verify.VerifyError):
        verify.pick_transport("jev")
    assert verify.pick_transport("decider")[0] == "decider"


def test_decider_transport_translates_both_ways(monkeypatch, repo):
    req = verify.prepare(verify.load_findings([finding(fix="f")]), repo, None, None)[0]["request"]
    seen = {}

    class FakeDecide:
        @staticmethod
        def decide(r, errors=None):
            seen["types"] = {q["name"]: q["type"] for q in r["questions"]}
            return {"answers": [
                {"type": "choice", "name": "verdict", "probabilities": [
                    {"value": "confirmed", "probability": 0.8}, {"value": "refuted", "probability": 0.1},
                    {"value": "insufficient_context", "probability": 0.1}]},
                {"type": "score", "name": "severity", "probabilities": [
                    {"value": i, "label": lv, "probability": 1.0 if lv == "high" else 0.0}
                    for i, lv in enumerate(verify.LEVELS)]},
                {"type": "predicate", "name": "fix_ok", "probability": 0.7}]}

    monkeypatch.setitem(sys.modules, "decide", FakeDecide)
    out = verify.decider_transport(req)
    assert seen["types"] == {"verdict": "choice", "severity": "score", "fix_ok": "predicate"}
    f = verify.judge({"id": "1"}, out, 0.7, 0.7)
    assert f["status"] == "confirmed" and f["severity"]["expected"] == "high" and f["fix_ok"] == 0.7


def test_emit_then_apply_round_trip(repo, tmp_path, capsys):
    (tmp_path / "f.json").write_text(json.dumps([finding(id="ok"), finding(id="gone", code_quote="nope")]))
    batch = tmp_path / "batch.json"
    assert verify.main(["emit", str(tmp_path / "f.json"), "--repo", str(repo), "--out", str(batch)]) == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["calls"] == 1 and emitted["requests"][0]["id"] == "ok"
    (tmp_path / "ans.json").write_text(json.dumps({"ok": json.dumps(answers(0.95, 0.05))}))
    assert verify.main(["apply", str(batch), str(tmp_path / "ans.json")]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert {f["id"]: f["status"] for f in rep["findings"]} == {"ok": "confirmed", "gone": "dropped"}


def test_apply_marks_missing_answers_unverified(repo, tmp_path, capsys):
    (tmp_path / "f.json").write_text(json.dumps([finding(id="ok")]))
    batch = tmp_path / "batch.json"
    verify.main(["emit", str(tmp_path / "f.json"), "--repo", str(repo), "--out", str(batch)])
    (tmp_path / "ans.json").write_text("{}")
    capsys.readouterr()
    assert verify.main(["apply", str(batch), str(tmp_path / "ans.json")]) == 3


def test_metrics_counts():
    rows = [{"label": "confirmed", "status": "confirmed", "reason": None, "verdict": {"confirmed": 0.9, "refuted": 0.1}},
            {"label": "refuted", "status": "dropped", "reason": "refuted_by_verifier",
             "verdict": {"confirmed": 0.1, "refuted": 0.9}},
            {"label": "ungrounded", "status": "dropped", "reason": "ungrounded_code_quote", "verdict": None}]
    m = verify.metrics(rows)
    assert (m["real_kept"], m["false_dropped"], m["ungrounded_dropped"]) == ("1/1", "1/1", "1/1")
    assert m["top_answer_accuracy"] == 1.0
