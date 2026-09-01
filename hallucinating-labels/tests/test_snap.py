"""Tests for scripts/snap.py — the deterministic half of the pattern."""
import json, pickle, subprocess, sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SNAP = HERE.parent / "scripts" / "snap.py"
sys.path.insert(0, str(SNAP.parent))
from snap import Index, interleave  # noqa: E402

LABELS = ["Coffee Tables", "Throw Pillows", "Kids Beds", "Massage Chairs", "Bar Stools"]


def test_snap_resolves_an_invented_label_to_a_real_one():
    idx = Index(LABELS)
    [[(label, score)]] = idx.rank(["Connected Coffee Tables"], k=1)
    assert label == "Coffee Tables" and score > 0.5


def test_output_is_always_in_the_vocabulary():
    """The whole guarantee: whatever the model wrote, the result is legal."""
    idx = Index(LABELS)
    for ranked in idx.rank(["utter nonsense zzzqq", "", "Hydraulic Styling Thrones"], k=3):
        assert all(l in LABELS for l, _ in ranked)


def test_empty_vocabulary_exits_rather_than_returning_nothing():
    with pytest.raises(SystemExit):
        Index([])


def test_unknown_backend_exits():
    with pytest.raises(SystemExit):
        Index(LABELS, backend="word2vec")


def test_documented_backends_are_all_constructible():
    """Registry invariant: the CLI advertises two backends in --backend choices.
    A third added there without an entry here is what this catches."""
    import argparse, snap
    src = SNAP.read_text()
    advertised = set(eval(src.split('choices=')[1].split(')')[0].strip().rstrip(','))) \
        if 'choices=' in src else set()
    assert advertised == {"tfidf", "minilm"}
    Index(LABELS, backend="tfidf")
    pytest.importorskip("sentence_transformers")
    Index(LABELS, backend="minilm")


def test_interleave_dedups_and_keeps_earliest_position():
    assert interleave([("a", 1.0), ("b", 0.9)], [("b", 0.8), ("c", 0.7)], 3) == \
        [("a", 1.0), ("b", 0.8), ("c", 0.7)]


def test_interleave_respects_k():
    assert len(interleave([("a", 1.0), ("b", .9)], [("c", .8), ("d", .7)], 2)) == 2


def _write(tmp, name, lines):
    p = tmp / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_cli_build_then_snap(tmp_path):
    vocab = _write(tmp_path, "v.txt", LABELS)
    labels = _write(tmp_path, "l.txt", ["Connected Coffee Tables", "Turquoise Pillows"])
    index = tmp_path / "i.pkl"
    subprocess.run([sys.executable, str(SNAP), "build", "--vocab", str(vocab),
                    "--out", str(index)], check=True, capture_output=True)
    out = subprocess.run([sys.executable, str(SNAP), "snap", "--index", str(index),
                          "--labels", str(labels), "--k", "2"],
                         check=True, capture_output=True, text=True)
    got = json.loads(out.stdout)
    assert [g["label"] for g in got] == ["Coffee Tables", "Throw Pillows"]


def test_min_score_reports_null_rather_than_a_bad_snap(tmp_path):
    vocab = _write(tmp_path, "v.txt", LABELS)
    labels = _write(tmp_path, "l.txt", ["quantum chromodynamics seminar"])
    index = tmp_path / "i.pkl"
    subprocess.run([sys.executable, str(SNAP), "build", "--vocab", str(vocab),
                    "--out", str(index)], check=True, capture_output=True)
    out = subprocess.run([sys.executable, str(SNAP), "snap", "--index", str(index),
                          "--labels", str(labels), "--min-score", "0.9"],
                         check=True, capture_output=True, text=True)
    assert json.loads(out.stdout)[0]["label"] is None


def test_union_requires_matching_line_counts(tmp_path):
    """A mismatch means the reply lost a line; snapping anyway shifts every later
    item onto its neighbour's label silently."""
    vocab = _write(tmp_path, "v.txt", LABELS)
    labels = _write(tmp_path, "l.txt", ["a", "b"])
    items = _write(tmp_path, "it.txt", ["one"])
    index = tmp_path / "i.pkl"
    subprocess.run([sys.executable, str(SNAP), "build", "--vocab", str(vocab),
                    "--out", str(index)], check=True, capture_output=True)
    r = subprocess.run([sys.executable, str(SNAP), "snap", "--index", str(index),
                        "--labels", str(labels), "--items", str(items), "--union"],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "line for line" in r.stderr
