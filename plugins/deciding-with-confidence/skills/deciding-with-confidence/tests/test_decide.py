"""Tests for deciding-with-confidence/scripts/decide.py.

    python3 -m pytest deciding-with-confidence/tests -q

No network: `decide()` runs through fake transports, and the SDK transport
through a local HTTP server standing in for the Messages API. The confidence
formula is pinned to the published examples it was inferred from (OpenAI's
choice 0.93 and score 0.55, Strands Decider's 0.768), so a change that drifts
from the reference APIs' scale shows up here first.
"""

import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("decide", SKILL / "scripts" / "decide.py")
dz = importlib.util.module_from_spec(_spec)
sys.modules["decide"] = dz  # dataclasses resolve annotations through sys.modules
_spec.loader.exec_module(dz)

ROUTE = {
    "input": "I was charged twice for my order.",
    "questions": [{
        "type": "choice", "name": "department",
        "instructions": "Which department should handle this complaint?",
        "choices": [
            {"value": "billing", "description": "Payments, invoices, and refunds."},
            {"value": "technical", "description": "Problems using the product."},
            {"value": "shipping", "description": "Delivery and tracking."},
            {"value": "other", "description": "Requests outside these categories."},
        ],
    }],
}
SEVERITY = {
    "input": "Export fails in Safari but works in Chrome.",
    "questions": [{
        "type": "score", "name": "severity", "instructions": "How severe is this issue?",
        "levels": [
            {"label": "Cosmetic", "description": "Appearance only; no lost functionality."},
            {"label": "Workaround available", "description": "A task fails, but another way works."},
            {"label": "Fully blocked", "description": "A task fails with no workaround."},
        ],
    }],
}
DAMAGE = {
    "input": "Photo shows a mug with a hairline crack along the handle.",
    "questions": [{"type": "predicate", "name": "visible_damage",
                   "instructions": "Does the product have visible damage?"}],
}


def fake(dists_by_call, refusals=None):
    """A transport returning the given {name: {key: p}} per call, in call order."""
    calls = iter(dists_by_call)
    ref = iter(refusals or [])

    def transport(system, user):
        d = next(calls)
        if d is None:
            raise dz.DeciderError("boom")
        r = next(ref, False)
        return {"answers": {n: {"probabilities": p, "refusal": r} for n, p in d.items()}}
    return transport


# ------------------------------------------------------------ reference scales

def test_confidence_matches_openai_choice_example():
    assert round(dz.confidence([0.95, 0.02, 0.01, 0.02]), 2) == 0.93


def test_confidence_matches_openai_score_example():
    assert round(dz.confidence([0.1, 0.7, 0.2]), 2) == 0.55


def test_confidence_matches_strands_example():
    assert round(dz.confidence([0.845, 0.091, 0.064]), 3) == 0.768


def test_confidence_bounds():
    assert dz.confidence([0.25] * 4) == pytest.approx(0.0)
    assert dz.confidence([1.0, 0.0]) == pytest.approx(1.0)


def test_score_is_probability_weighted_index():
    assert dz.expected_level([0.1, 0.7, 0.2]) == pytest.approx(1.1)


# ------------------------------------------------------------ request handling

def test_normalize_predicate_gets_true_false_options():
    q, = dz.normalize_request(DAMAGE)
    assert q.type == "predicate"
    assert [o.key for o in q.options] == ["true", "false"]


def test_normalize_choice_keeps_non_string_values():
    req = {"input": "x", "questions": [{"type": "choice", "name": "n", "instructions": "i",
                                        "choices": [{"value": 1}, {"value": 2}]}]}
    q, = dz.normalize_request(req)
    assert [o.key for o in q.options] == ["1", "2"]
    assert [o.value for o in q.options] == [1, 2]


def test_normalize_score_keys_are_indices():
    q, = dz.normalize_request(SEVERITY)
    assert [o.key for o in q.options] == ["0", "1", "2"]
    assert q.options[2].label == "Fully blocked"


def test_normalize_rejects_duplicate_names_and_images():
    with pytest.raises(dz.DeciderError):
        dz.normalize_request({"input": "x", "questions": [DAMAGE["questions"][0]] * 2})
    img = {"input": [{"role": "user", "content": [{"type": "input_image", "image_url": "data:"}]}],
           "questions": DAMAGE["questions"]}
    with pytest.raises(dz.DeciderError):
        dz.normalize_request(img)


def test_input_messages_flatten_to_text():
    req = {"input": [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
           "questions": DAMAGE["questions"]}
    assert dz.input_text(req) == "hello"


def test_unnamed_questions_get_positional_names():
    req = {"input": "x", "questions": [{"type": "predicate", "instructions": "a"},
                                       {"type": "predicate", "instructions": "b"}]}
    assert [q.name for q in dz.normalize_request(req)] == ["question_0", "question_1"]


# ------------------------------------------------------------ sampling

def test_samples_permute_choice_order():
    qs = dz.normalize_request(ROUTE)
    orders = {tuple(dz.presented_order(qs[0], i)) for i in range(8)}
    assert len(orders) > 1
    for o in orders:
        assert sorted(o) == sorted(x.key for x in qs[0].options)


def test_samples_alternate_score_direction():
    q, = dz.normalize_request(SEVERITY)
    assert dz.presented_order(q, 0) == ["0", "1", "2"]
    assert dz.presented_order(q, 1) == ["2", "1", "0"]


def test_sample_prompt_carries_input_and_every_option():
    qs = dz.normalize_request(ROUTE)
    text = dz.sample_prompt(ROUTE, qs, 0)
    assert "charged twice" in text
    for k in ("billing", "technical", "shipping", "other"):
        assert k in text


# ------------------------------------------------------------ parsing

def test_parse_accepts_fenced_json_and_renormalizes():
    qs = dz.normalize_request(DAMAGE)
    reply = '```json\n{"answers": {"visible_damage": {"probabilities": {"true": 3, "false": 1}}}}\n```'
    parsed = dz.parse_reply(reply, qs)
    assert parsed["visible_damage"]["probs"] == pytest.approx({"true": 0.75, "false": 0.25})


def test_parse_omitted_keys_share_the_unassigned_mass():
    qs = dz.normalize_request(ROUTE)
    got = dz.parse_reply({"answers": {"department": {"probabilities": {"billing": 0.8, "technical": 0.1}}}}, qs)
    assert got["department"]["probs"] == pytest.approx(
        {"billing": 0.8, "technical": 0.1, "shipping": 0.05, "other": 0.05})
    got = dz.parse_reply({"answers": {"department": {"probabilities": {"billing": 0.9, "technical": 0.1}}}}, qs)
    assert got["department"]["probs"]["shipping"] == 0.0


def test_parse_no_known_key_or_zero_mass_is_none():
    qs = dz.normalize_request(DAMAGE)
    assert dz.parse_reply({"answers": {"visible_damage": {"probabilities": {"yes": 1}}}}, qs)["visible_damage"] is None
    assert dz.parse_reply({"answers": {"visible_damage": {"probabilities": {"true": 0, "false": 0}}}},
                          qs)["visible_damage"] is None
    assert dz.parse_reply("not json", qs) is None


# ------------------------------------------------------------ decide()

def test_decide_choice_shape_matches_openai():
    t = fake([{"department": {"billing": 0.95, "technical": 0.02, "shipping": 0.01, "other": 0.02}}])
    out = dz.decide(ROUTE, k=1, transport=t, calibration={})
    a, = out["answers"]
    assert a["type"] == "choice" and a["name"] == "department" and a["choice"] == "billing"
    assert [p["value"] for p in a["probabilities"]] == ["billing", "technical", "shipping", "other"]
    assert a["confidence"] == pytest.approx(0.93, abs=0.005)


def test_decide_score_shape_matches_openai():
    t = fake([{"severity": {"0": 0.1, "1": 0.7, "2": 0.2}}])
    a, = dz.decide(SEVERITY, k=1, transport=t, calibration={})["answers"]
    assert a["type"] == "score" and a["score"] == pytest.approx(1.1)
    assert a["probabilities"][1] == {"value": 1, "label": "Workaround available", "probability": pytest.approx(0.7)}


def test_decide_predicate_returns_probability_of_true():
    t = fake([{"visible_damage": {"true": 0.8, "false": 0.2}}, {"visible_damage": {"true": 0.6, "false": 0.4}}])
    a, = dz.decide(DAMAGE, k=2, transport=t, calibration={})["answers"]
    assert a == {"type": "predicate", "name": "visible_damage", "probability": pytest.approx(0.7),
                 "diagnostics": a["diagnostics"]}


def test_disagreement_between_samples_lowers_confidence():
    agree = fake([{"department": {"billing": 0.9, "technical": 0.04, "shipping": 0.03, "other": 0.03}}] * 3)
    split = fake([{"department": {"billing": 0.9, "technical": 0.04, "shipping": 0.03, "other": 0.03}},
                  {"department": {"billing": 0.04, "technical": 0.9, "shipping": 0.03, "other": 0.03}},
                  {"department": {"billing": 0.9, "technical": 0.04, "shipping": 0.03, "other": 0.03}}])
    a1, = dz.decide(ROUTE, k=3, transport=agree, calibration={})["answers"]
    a2, = dz.decide(ROUTE, k=3, transport=split, calibration={})["answers"]
    assert a2["confidence"] < a1["confidence"]
    assert a2["diagnostics"]["agreement"] == pytest.approx(2 / 3)
    assert a1["diagnostics"]["agreement"] == 1.0


def test_failed_samples_are_dropped_and_counted():
    t = fake([None, {"visible_damage": {"true": 0.9, "false": 0.1}}, None])
    a, = dz.decide(DAMAGE, k=3, transport=t, calibration={})["answers"]
    assert a["probability"] == pytest.approx(0.9)
    assert a["diagnostics"]["samples"] == 1 and a["diagnostics"]["failed"] == 2


def test_total_failure_is_none_not_a_default_answer():
    assert dz.decide(DAMAGE, k=2, transport=fake([None, None]), calibration={}) is None


def test_majority_refusal_returns_refusal_answer():
    d = {"visible_damage": {"true": 0.5, "false": 0.5}}
    a, = dz.decide(DAMAGE, k=3, transport=fake([d, d, d], refusals=[True, True, False]),
                   calibration={})["answers"]
    assert a == {"type": "refusal", "name": "visible_damage"}


def test_calibration_temperature_is_applied_per_type():
    t = fake([{"visible_damage": {"true": 0.95, "false": 0.05}}])
    a, = dz.decide(DAMAGE, k=1, transport=t, calibration={"predicate": 2.0})["answers"]
    assert 0.5 < a["probability"] < 0.95
    assert a["diagnostics"]["temperature"] == 2.0


# ------------------------------------------------------------ calibration and metrics

def test_temperature_above_one_flattens():
    p = dz.temper({"a": 0.9, "b": 0.1}, 2.0)
    assert 0.5 < p["a"] < 0.9 and sum(p.values()) == pytest.approx(1.0)


def test_fit_temperature_recovers_overconfidence():
    rng = random.Random(0)
    recs = []
    for _ in range(400):  # says 0.95 but is right 75% of the time
        right = rng.random() < 0.75
        recs.append(({"a": 0.95, "b": 0.05}, "a" if right else "b"))
    T = dz.fit_temperature(recs)
    assert T > 1.5
    assert dz.nll(recs, T) < dz.nll(recs, 1.0)


def test_metrics_on_known_rows():
    rows = [{"type": "predicate", "probs": {"true": 0.9, "false": 0.1}, "label": "true"},
            {"type": "predicate", "probs": {"true": 0.2, "false": 0.8}, "label": "true"}]
    m = dz.metrics(rows)
    assert m["accuracy"] == 0.5
    assert m["brier"] == pytest.approx(((0.1 ** 2 + 0.1 ** 2) + (0.8 ** 2 + 0.8 ** 2)) / 2 / 2)


# ------------------------------------------------------------ transports

def test_cli_transport_is_isolated_from_session_config():
    argv = dz.claude_argv("sys", "user")
    for flag in ("--tools", "--setting-sources", "--strict-mcp-config", "--no-session-persistence",
                 "--system-prompt"):
        assert flag in argv
    assert "--json-schema" not in argv  # a second turn and ~3x output tokens
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--setting-sources") + 1] == ""


def test_system_prompt_is_the_asset():
    sp = dz.system_prompt()
    assert sp.startswith("You are a decision model.")
    assert "---" not in sp.splitlines()[0]


def test_auto_transport_prefers_api_key_then_cli(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert dz.pick_transport().__name__ == "transport"  # the SDK closure
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(dz.shutil, "which", lambda _: "/usr/bin/claude")
    assert dz.pick_transport() is dz.cli_transport
    monkeypatch.setattr(dz.shutil, "which", lambda _: None)
    with pytest.raises(dz.DeciderError):
        dz.pick_transport()


def test_message_params_fit_haiku_5_5():
    m = dz.message_params("claude-haiku-5-5", "sys", "user")
    assert m["thinking"] == {"type": "disabled"} and m["output_config"] == {"effort": "low"}
    assert "temperature" not in m  # non-default sampling values are a 400 on Haiku 5.5
    assert m["messages"][-1]["role"] == "user"  # no assistant prefill


def test_api_transport_round_trip_against_a_local_server(monkeypatch):
    pytest.importorskip("anthropic")
    import http.server
    import threading
    seen = {}
    reply = {"answers": {"visible_damage": {"probabilities": {"true": 0.8, "false": 0.2}, "refusal": False}}}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
            body = json.dumps({"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
                               "content": [{"type": "text", "text": json.dumps(reply)}],
                               "stop_reason": "end_turn", "stop_sequence": None,
                               "usage": {"input_tokens": 900, "output_tokens": 60}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setattr(dz, "_CLIENTS", {})
    try:
        out = dz.decide(DAMAGE, k=1, transport=dz.pick_transport("api"), calibration={})
    finally:
        srv.shutdown()
    assert seen["path"] == "/v1/messages" and seen["body"]["model"] == "claude-haiku-5-5"
    assert seen["body"]["thinking"] == {"type": "disabled"}
    assert out["answers"][0]["probability"] == pytest.approx(0.8)
    assert out["usage"]["cost_usd"] == pytest.approx((900 * 0.10 + 60 * 0.50) / 1e6)


def test_every_bundled_eval_item_parses_and_its_labels_resolve():
    items = [json.loads(line) for line in (SKILL / "assets" / "eval.jsonl").read_text().splitlines() if line.strip()]
    assert len(items) == 104
    for it in items:
        for q in dz.normalize_request(it):
            dz.label_key(q, it["labels"][q.name])


def test_bundled_calibration_loads():
    cal = dz.load_calibration()
    assert 0.3 < cal["choice"] < 1.0 and "predicate" not in cal


def test_emit_then_aggregate_round_trip(tmp_path):
    batch = dz.emit(ROUTE, k=2)
    assert len(batch["samples"]) == 2 and batch["samples"][0]["model"] == "haiku"
    assert batch["samples"][0]["prompt"].startswith("You are a decision model.")  # any Haiku subagent works
    assert all(s["prompt"].endswith("[no-context]") for s in batch["samples"])  # no transcript chunks appended
    replies = [json.dumps({"answers": {"department": {"probabilities": {
        "billing": 0.9, "technical": 0.05, "shipping": 0.03, "other": 0.02}}}})] * 2
    out = dz.aggregate(batch["request"], replies, calibration={})
    assert out["answers"][0]["choice"] == "billing"
    assert math.isclose(out["answers"][0]["diagnostics"]["agreement"], 1.0)


def test_api_transport_without_credentials_is_none_with_a_reason(monkeypatch):
    pytest.importorskip("anthropic")
    for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")  # no `ant auth login` profile either
    monkeypatch.setattr(dz, "_CLIENTS", {})
    errors = []
    assert dz.decide(DAMAGE, k=1, transport=dz.pick_transport("api"), calibration={}, errors=errors) is None
    assert errors and "authentication" in errors[0]


def test_agent_definition_body_is_the_system_prompt():
    text = (SKILL / "agents" / "decider.md").read_text()
    assert text.split("---", 2)[2].strip() == dz.system_prompt()
    assert "\nmodel: claude-haiku-5-5\n" in text  # pinned: the calibration is fitted on this model


def test_emit_for_an_installed_agent_omits_the_system_prompt():
    batch = dz.emit(ROUTE, k=1, agent="decider")
    assert batch["samples"][0]["subagent_type"] == "decider"
    assert batch["samples"][0]["prompt"].startswith("<evidence>")
