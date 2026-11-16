"""Tests for scripts/hypothesis_stats.py: the parser on captured output, and
one live run against a throwaway Hypothesis suite."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hypothesis_stats.py"
spec = importlib.util.spec_from_file_location("hypothesis_stats", SCRIPT)
hs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hs)

CAPTURED = """\
============================ Hypothesis Statistics =============================
test_m.py::TestNoCache::runTest:

  - during generate phase (0.39 seconds):
    - 50 passing, 0 failing, and 0 invalid test cases
    - Events:
      * 72.00%, Retried draw from sampled_from([Rule(...)]).filter(x) to satisfy filter
      * 3.00%, gave up because: Aborted test because unable to satisfy x
      * 16.00%, N=1 k<N=False
      * 2.00%, N=3 k<N=True

  - during shrink phase (0.10 seconds):
    - Events:
      * 99.00%, shrink-only label

test_m.py::test_plain:

  - during generate phase (0.01 seconds):
    - 10 passing, 0 failing, and 0 invalid test cases
"""


def test_parse_keeps_generate_phase_user_events_only():
    stats = hs.parse(CAPTURED)
    assert stats == {
        "test_m.py::TestNoCache::runTest": {"N=1 k<N=False": 16.0, "N=3 k<N=True": 2.0},
        "test_m.py::test_plain": {},
    }


def test_check_reports_a_class_below_its_floor_and_one_that_never_fired():
    stats = hs.parse(CAPTURED)
    misses = hs.check(stats, [("k<N=True", 5.0), ("overwrite", 1.0)], None)
    assert len(misses) == 2
    assert "best 2%" in misses[0]
    assert "never fired" in misses[1]


def test_check_passes_when_the_floor_is_met():
    stats = hs.parse(CAPTURED)
    assert hs.check(stats, [("k<N", 10.0)], None) == []


def test_live_run(tmp_path):
    pytest.importorskip("hypothesis")
    (tmp_path / "test_live.py").write_text(
        "from hypothesis import event, given, settings, strategies as st\n"
        "@settings(max_examples=200, derandomize=True)\n"
        "@given(st.integers(0, 9))\n"
        "def test_x(x):\n"
        "    event('small' if x < 5 else 'large')\n"
        "    event('nine') if x == 9 else None\n"
    )
    base = [sys.executable, str(SCRIPT)]
    run = lambda *a: subprocess.run([*base, *a, "--", sys.executable, "-m", "pytest", "-q",
                                     "-p", "no:cacheprovider", str(tmp_path / "test_live.py")],
                                    capture_output=True, text=True, cwd=tmp_path)
    ok = run("--min", "small=20")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "small" in ok.stdout
    missing = run("--min", "never-emitted=1")
    assert missing.returncode == 1 and "never fired" in missing.stdout


def test_no_statistics_is_exit_2(tmp_path):
    (tmp_path / "test_plain.py").write_text("def test_ok():\n    assert True\n")
    r = subprocess.run([sys.executable, str(SCRIPT), "--", sys.executable, "-m", "pytest",
                        "-q", "-p", "no:cacheprovider", str(tmp_path / "test_plain.py")],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 2
