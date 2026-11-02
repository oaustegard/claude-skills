"""scripts/fresh_eyes.py: a turn that changed reader-facing text ends only after a newcomer has read it.

Real git repositories and plain directories in tmp_path stand in for a session's files. Covers which changes count,
what the packet holds, when the gate stands down, and the hook end to end.

    python3 -m pytest declauding/tests/test_fresh_eyes.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))

import fresh_eyes as g

README = """# Tilt Rally

A racing game for a phone held like a steering wheel.

## Start

Lock rotation in portrait, turn the phone a quarter turn clockwise and hold it like a wheel.

## Pedals

Tilt the top of the phone away for gas and toward you to brake.

## Log

### Round 1

Built the first track.
"""


def check(turn):
    return g.gate(turn, collect=lambda t0: g.changed_since(t0))


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat().replace("+00:00", "Z")


def turn_at(t: float, reader_at: float | None = None) -> list[dict]:
    turn = [{"type": "assistant", "timestamp": iso(t), "message": {"content": []}}]
    if reader_at is not None:
        turn.append({"type": "assistant", "timestamp": iso(reader_at), "message": {"content": [
            {"type": "tool_use", "id": "a", "name": "Agent", "input": {"prompt": f"{g.MARK}. Read /tmp/x.md"}}]}})
    return turn


def repo(tmp_path, monkeypatch, files: dict[str, str]):
    r = tmp_path / "game"
    r.mkdir()
    def git(*a, when=None):
        env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when) if when else None
        subprocess.run(["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True, env=env)
    for name, text in files.items():
        (r / name).parent.mkdir(parents=True, exist_ok=True)
        (r / name).write_text(text)
    git("init", "-q"); git("add", "."); git("commit", "-qm", "init", when=f"@{int(time.time()) - 600} +0000")
    old = time.time() - 600
    for f in r.rglob("*"):
        if f.is_file():
            os.utime(f, (old, old))
    monkeypatch.setattr(g, "changed_since", lambda t0, cwd="": g.changed_in_repos(t0, [r]))
    monkeypatch.setattr(g, "OUT_DIR", tmp_path / "out")
    return r, git


def test_bash_style_edit_blocks_with_packet_of_whole_section(tmp_path, monkeypatch):
    r, git = repo(tmp_path, monkeypatch, {"README.md": README})
    t0 = time.time() - 1
    (r / "README.md").write_text(README.replace(
        "Lock rotation in portrait, turn the phone a quarter turn clockwise and hold it like a wheel.",
        "Lock rotation in portrait and pick your options here, upright, then turn the phone once the race starts."))
    msg = check(turn_at(t0))
    assert msg and "game/README.md" in msg and g.MARK in msg
    pkt = (tmp_path / "out").glob("*.md").__next__().read_text()
    assert "## Start" in pkt and "pick your options here, upright" in pkt
    assert "# Tilt Rally" in pkt                      # the title, for orientation
    assert "## Pedals" not in pkt and "Round 1" not in pkt


def test_committed_change_counts_too(tmp_path, monkeypatch):
    r, git = repo(tmp_path, monkeypatch, {"README.md": README})
    t0 = time.time() - 1
    (r / "README.md").write_text(README.replace("toward you to brake.", "toward you to brake; the brake builds over half a second instead of slamming on."))
    git("commit", "-qam", "brake")
    items = g.changed_since(t0)
    assert [it["path"] for it in items] == ["README.md"]


def test_reader_in_turn_stands_gate_down(tmp_path, monkeypatch):
    r, git = repo(tmp_path, monkeypatch, {"README.md": README})
    t0 = time.time() - 1
    (r / "README.md").write_text(README.replace("A racing game", "A WebGPU racing game, with real circuits and friends over WebRTC,"))
    assert check(turn_at(t0, reader_at=time.time() + 1)) is None


def test_reader_before_the_last_write_does_not_count(tmp_path, monkeypatch):
    r, git = repo(tmp_path, monkeypatch, {"README.md": README})
    t0 = time.time() - 30
    (r / "README.md").write_text(README.replace("A racing game", "A WebGPU racing game, with real circuits and friends over WebRTC,"))
    assert check(turn_at(t0, reader_at=time.time() - 10)) is not None


def test_typo_log_and_old_edits_do_not_count(tmp_path, monkeypatch):
    r, git = repo(tmp_path, monkeypatch, {"README.md": README})
    t0 = time.time() - 1
    (r / "README.md").write_text(README.replace("steering wheel", "steering-wheel").replace(
        "Built the first track.", "Built the first track, then rebuilt the brakes and moved the menus upright."))
    assert check(turn_at(t0)) is None
    assert check(turn_at(time.time() + 60)) is None   # nothing written since a later turn began


def test_html_script_and_markup_changes_do_not_count(tmp_path, monkeypatch):
    page = "<html><body>\n<p class=\"a\">Choose a track and start the race.</p>\n<script>\nconst lights = brake > 0.2;\n</script>\n</body></html>\n"
    r, git = repo(tmp_path, monkeypatch, {"index.html": page})
    t0 = time.time() - 1
    (r / "index.html").write_text(page.replace('class="a"', 'class="b"').replace("brake > 0.2", "brake > 0.05 // lamps only when braking"))
    assert g.changed_since(t0) == []


def test_html_visible_change_packet_is_text_only(tmp_path, monkeypatch):
    page = "<html><body>\n<ol>\n<li><span>Lock rotation in portrait, turn the phone a quarter turn clockwise.</span></li>\n</ol>\n<script>\nconst x = 1;\n</script>\n</body></html>\n"
    r, git = repo(tmp_path, monkeypatch, {"games/x/index.html": page})
    t0 = time.time() - 1
    (r / "games/x/index.html").write_text(page.replace("turn the phone a quarter turn clockwise", "pick your options here, upright, and turn the phone after Start"))
    msg = check(turn_at(t0))
    pkt = next((tmp_path / "out").glob("*.md")).read_text()
    assert msg and "pick your options here, upright" in pkt and "<span>" not in pkt and "const x" not in pkt


def test_new_untracked_file_and_skipped_paths(tmp_path, monkeypatch):
    r, git = repo(tmp_path, monkeypatch, {"README.md": README})
    t0 = time.time() - 1
    (r / "GUIDE.md").write_text("# Guide\n\nHold the phone like a steering wheel. Tilt it toward you to brake, away for gas.\n")
    (r / "CHANGELOG.md").write_text("# Changes\n\nThe brake now builds over half a second instead of slamming on.\n")
    (r / "_site").mkdir()
    (r / "_site" / "index.html").write_text("<p>A built copy of the page, regenerated on every deploy of the site.</p>\n")
    assert [it["path"] for it in g.changed_since(t0)] == ["GUIDE.md"]


def test_generated_region_and_working_records_do_not_count(tmp_path, monkeypatch):
    page = "<h1>Toys</h1>\n<p>Small things to play with on a phone.</p>\n<!--gen:tools-->\n<li>Plumb: a pipe puzzle</li>\n<!--/gen:tools-->\n"
    r, git = repo(tmp_path, monkeypatch, {"index.html": page, "exp/ERRORS.md": "# Errors\n\nNone yet.\n"})
    t0 = time.time() - 1
    (r / "index.html").write_text(page.replace("<li>Plumb: a pipe puzzle</li>", "<li>Plumb: a pipe puzzle</li>\n<li>Tilt Rally: a racing game you steer by turning the phone</li>"))
    (r / "exp/ERRORS.md").write_text("# Errors\n\nThe first run lost its checkpoint when the container paused.\n")
    assert g.changed_since(t0) == []


def test_touching_sections_join_without_a_gap_marker():
    text = "# T\n\n## A\n\none\n\n## B\n\ntwo\n\n## C\n\nthree\n"
    assert g.sections(text, {5, 9}) == ["# T", "## A\n\none\n\n## B\n\ntwo"]
    assert len(g.sections(text, {5, 13})) == 3


def test_html_change_inside_a_style_or_script_block_never_counts_or_shows(tmp_path, monkeypatch):
    css = "".join(f"#c{i} {{ top: {i}px; }}\n" for i in range(40))
    page = f"<html><head><style>\n{css}</style></head><body>\n<p>Choose a track and start the race.</p>\n</body></html>\n"
    r, git = repo(tmp_path, monkeypatch, {"index.html": page})
    t0 = time.time() - 1
    (r / "index.html").write_text(page.replace("#c20 { top: 20px; }", "#c20 { top: 24px; left: 50%; transform: translateX(-50%); }"))
    assert g.changed_since(t0) == []
    text = page.replace("Choose a track", "Pick a circuit or a generated valley,")
    assert all("top:" not in w for w in g.html_windows(text, {44}))


def test_files_outside_any_repository_count_whole(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    (out / "site").mkdir(parents=True)
    old = out / "site" / "OLD.md"
    old.write_text("# Old\n\nWritten in an earlier turn and not touched since.\n")
    os.utime(old, (time.time() - 600, time.time() - 600))
    t0 = time.time() - 1
    (out / "site" / "GUIDE.md").write_text("# Guide\n\nHold the phone like a steering wheel and tilt it to brake.\n\n## Log\n\nRound 1.\n")
    items = g.changed_outside_repos(t0, (str(out),))
    assert [it["path"] for it in items] == ["site/GUIDE.md"]
    assert g.packet(items).count("## Log") == 0 and "steering wheel" in g.packet(items)


def test_hook_blocks_once_then_stands_down(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    out.mkdir()
    t0 = time.time() - 2
    (out / "README.md").write_text("# Tool\n\nLock rotation in portrait and pick your options here, upright.\n")
    transcript = tmp_path / "t.jsonl"
    human = {"type": "user", "message": {"content": "fix the menus"}, "timestamp": iso(t0)}
    step = {"type": "assistant", "timestamp": iso(t0 + 1), "message": {"content": []}}
    transcript.write_text("\n".join(json.dumps(r) for r in (human, step)) + "\n")
    env = dict(os.environ, FRESH_EYES_OUT=str(tmp_path / "pk"), FRESH_EYES_LOG=str(tmp_path / "log.jsonl"), CLAUDE_PROJECT_DIR="")
    def run(payload):
        r = subprocess.run([sys.executable, str(SKILL / "scripts" / "fresh_eyes.py"), "hook"], input=json.dumps(payload),
                           capture_output=True, text=True, env=env, cwd=str(out))
        assert r.returncode == 0
        return r.stdout
    got = run({"transcript_path": str(transcript), "cwd": str(out), "stop_hook_active": False})
    assert json.loads(got)["decision"] == "block" and g.MARK in json.loads(got)["reason"]
    assert run({"transcript_path": str(transcript), "cwd": str(out), "stop_hook_active": True}) == ""
    log = [json.loads(l) for l in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert [r["result"] for r in log] == ["blocked", "continuation"]


def test_hook_fails_open_on_bad_input(tmp_path):
    env = dict(os.environ, FRESH_EYES_LOG=str(tmp_path / "log.jsonl"))
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "fresh_eyes.py"), "hook"], input="not json",
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0 and r.stdout == "" and "error" in (tmp_path / "log.jsonl").read_text()
