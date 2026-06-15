"""Tests for the Python LSP client.

Round-trips against a small multi-file fixture driving a real
``pyright-langserver``. Verifies binding-resolved queries, the indexing-wait,
diagnostics, and subprocess cleanup.

Run: python -m pytest tests/test_lsp_client.py -v
Or:  python tests/test_lsp_client.py   (standalone)

Requires pyright (and system node). The bootstrap test self-installs if needed.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lsp_client import (  # noqa: E402
    BootstrapError,
    LSPClient,
    Location,
    Position,
    SymbolInfo,
    ensure_pyright,
    uri_to_path,
)

FIXTURE = Path(__file__).parent / "fixture"


def _rel(loc: Location) -> str:
    return str(Path(loc.path).relative_to(FIXTURE.resolve()))


def _pyright_proc_count() -> int:
    out = subprocess.run(
        ["pgrep", "-f", "pyright-langserver"], capture_output=True, text=True
    ).stdout
    return len([line for line in out.splitlines() if line.strip()])


@pytest.fixture(scope="module")
def client():
    ensure_pyright()  # skip below if unavailable
    c = LSPClient(str(FIXTURE)).start()
    c.open_all("pkg/models.py", "pkg/service.py", "pkg/other.py", "bad.py")
    assert c.wait_for_index(timeout=30), "pyright never reached a ready state"
    yield c
    c.stop()


# ── unit: position / location coercion (no server) ──────────────────────────

def test_position_zero_based_conversion():
    p = Position.from_one_based(line=5, col=10)
    assert (p.line, p.character) == (4, 9)
    assert p.to_lsp() == {"line": 4, "character": 9}


def test_location_from_lsp_handles_locationlink():
    link = {
        "targetUri": "file:///tmp/x.py",
        "targetRange": {
            "start": {"line": 1, "character": 2},
            "end": {"line": 1, "character": 6},
        },
    }
    loc = Location.from_lsp(link)
    assert loc.path == "/tmp/x.py"
    assert (loc.start_line, loc.start_char) == (1, 2)


def test_uri_to_path_roundtrip():
    assert uri_to_path("file:///home/user/a%20b.py") == "/home/user/a b.py"


# ── bootstrap ───────────────────────────────────────────────────────────────

def test_ensure_pyright_returns_executable():
    path = ensure_pyright()
    assert Path(path).name.startswith("pyright-langserver")


def test_bootstrap_fails_loudly_without_node(monkeypatch):
    # With pyright absent and node absent, must raise (not hang).
    import lsp_client

    def fake_which(name):
        return None  # nothing on PATH

    monkeypatch.setattr(lsp_client.shutil, "which", fake_which)
    with pytest.raises(BootstrapError) as exc:
        ensure_pyright(install=True)
    assert "node" in str(exc.value).lower()


# ── semantic queries (the win over ripgrep) ─────────────────────────────────

def test_definition_follows_import_across_files(client):
    # service.py line 4 (`    u = User(name)`), col 8 sits on `User`.
    locs = client.definition("pkg/service.py", 4, 8)
    targets = {_rel(loc) for loc in locs}
    assert "pkg/models.py" in targets
    # Points at the class definition (line 0 of models.py).
    assert any(loc.start_line == 0 for loc in locs)


def test_references_are_binding_resolved_not_textual(client):
    # models.py line 8 (`def helper(...)`), col 4 is the `helper` definition.
    locs = client.references("pkg/models.py", 8, 4)
    files = {_rel(loc) for loc in locs}
    # Includes the def, the import, and the call in service.py ...
    assert "pkg/models.py" in files
    assert "pkg/service.py" in files
    # ... but EXCLUDES the same-named, unrelated helper in other.py.
    assert "pkg/other.py" not in files, (
        "references must be binding-resolved: other.py defines an unrelated "
        "`helper` that ripgrep would match but pyright must not."
    )


def test_hover_returns_inferred_type(client):
    # service.py line 4 col 4 is the local `u`, whose type is inferred as User.
    text = client.hover("pkg/service.py", 4, 4)
    assert text is not None and "User" in text


def test_hover_returns_signature(client):
    text = client.hover("pkg/service.py", 5, 10)  # `helper` call
    assert text is not None and "helper" in text and "int" in text


def test_diagnostics_flag_intentional_type_error(client):
    diags = client.diagnostics("bad.py")
    assert diags, "expected at least one diagnostic for the bad assignment"
    assert any("int" in d.get("message", "") for d in diags)


def test_clean_file_has_no_diagnostics(client):
    assert client.diagnostics("pkg/models.py") == []


# ── indexing-wait determinism ───────────────────────────────────────────────

def test_indexing_wait_makes_queries_deterministic():
    # This is the test that would flake WITHOUT wait_for_index: a fresh server
    # returns empty results until analysis completes. Repeating it several times
    # must yield the same non-empty answer every time.
    ensure_pyright()
    for _ in range(3):
        with LSPClient(str(FIXTURE)) as c:
            c.open_all("pkg/models.py", "pkg/service.py")
            assert c.wait_for_index(timeout=30)
            locs = c.definition("pkg/service.py", 4, 8)
            assert {_rel(loc) for loc in locs} == {"pkg/models.py"}


# ── lifecycle / cleanup ─────────────────────────────────────────────────────

def test_subprocess_reaped_on_stop():
    ensure_pyright()
    before = _pyright_proc_count()
    c = LSPClient(str(FIXTURE)).start()
    c.did_open("pkg/models.py")
    c.wait_for_index(timeout=30)
    assert _pyright_proc_count() == before + 1
    pid = c.pid
    c.stop()
    # Give the OS a beat to reap.
    for _ in range(20):
        if _pyright_proc_count() == before:
            break
        time.sleep(0.1)
    assert _pyright_proc_count() == before, "pyright-langserver leaked after stop()"
    # The exact subprocess is gone.
    with pytest.raises(OSError):
        import os

        os.kill(pid, 0)


def test_context_manager_cleans_up():
    ensure_pyright()
    before = _pyright_proc_count()
    with LSPClient(str(FIXTURE)) as c:
        c.did_open("pkg/models.py")
        c.wait_for_index(timeout=30)
    assert _pyright_proc_count() == before


# ── config-capability regression (the self-inflicted hang) ──────────────────

def test_no_configuration_capability_and_no_nudge():
    # Regression for the over-engineered v0.1.0: advertising
    # workspace.configuration made pyright defer all analysis until a
    # didChangeConfiguration nudge arrived. The fix is to NOT advertise it.
    # This pins both halves: the capability is absent from `initialize`, and
    # no workspace/didChangeConfiguration is ever sent — yet analysis works.
    ensure_pyright()
    sent: list[dict] = []
    c = LSPClient(str(FIXTURE))
    real_send = c._send

    def spy(payload):
        sent.append(payload)
        return real_send(payload)

    c._send = spy  # type: ignore[method-assign]
    try:
        c.start()
        init = next(m for m in sent if m.get("method") == "initialize")
        workspace_caps = init["params"]["capabilities"].get("workspace", {})
        assert "configuration" not in workspace_caps
        assert not any(
            m.get("method") == "workspace/didChangeConfiguration" for m in sent
        ), "no configuration nudge should be needed"
        # And analysis still proceeds with no nudge.
        c.did_open("bad.py")
        assert c.wait_for_index(timeout=30)
        assert c.diagnostics("bad.py"), "pyright analyzed without any config push"
    finally:
        c.stop()


# ── documentSymbol / workspace symbol ───────────────────────────────────────

def test_document_symbols_outline(client):
    syms = client.document_symbols("pkg/models.py")
    by_name = {s.name: s for s in syms}
    assert by_name["User"].kind_name == "Class"
    assert by_name["helper"].kind_name == "Function"
    # `greet` is a method nested under User → its container is the class.
    assert "greet" in by_name
    assert by_name["greet"].kind_name == "Method"
    assert by_name["greet"].container == "User"


def test_document_symbol_location_in_file(client):
    syms = client.document_symbols("pkg/models.py")
    user = next(s for s in syms if s.name == "User")
    assert _rel(user.location) == "pkg/models.py"
    assert user.location.start_line == 0


def test_workspace_symbols_find_class(client):
    hits = client.workspace_symbols("User")
    names = {(s.name, _rel(s.location)) for s in hits if isinstance(s, SymbolInfo)}
    assert ("User", "pkg/models.py") in names


# ── standalone runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
