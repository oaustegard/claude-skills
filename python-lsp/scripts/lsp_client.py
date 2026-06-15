"""Python LSP client: a stdio JSON-RPC client driving ``pyright-langserver``.

A thin, dependency-free client that owns the LSP lifecycle against
``pyright-langserver --stdio`` and exposes a few high-value semantic queries:
``definition``, ``references``, ``hover``, ``diagnostics``.

Why not tree-sitter? tree-sitter gives a CST — structural queries, call-site
enumeration by name. It cannot do name resolution, type inference, or
cross-file binding. pyright can. This client is the semantic overlay the
codebase skills currently approximate with ripgrep (which false-positives on
shadowed / same-named symbols).

Positions are **zero-based** line/character per the LSP spec. Convert from any
1-based UI input at the boundary (see ``Position.from_one_based``).

Usage (library)::

    from lsp_client import LSPClient
    with LSPClient("/path/to/repo") as c:
        c.did_open("pkg/service.py")
        c.wait_for_index()
        defs = c.definition("pkg/service.py", line=4, col=12)
        refs = c.references("pkg/models.py", line=0, col=6)
        sig  = c.hover("pkg/service.py", line=4, col=12)
        diags = c.diagnostics("pkg/bad.py")

Usage (CLI)::

    python lsp_client.py <root> definition  <file> <line> <col>
    python lsp_client.py <root> references  <file> <line> <col>
    python lsp_client.py <root> hover       <file> <line> <col>
    python lsp_client.py <root> diagnostics <file>
    python lsp_client.py <root> symbols     <file>          # documentSymbol outline
    python lsp_client.py <root> wsymbols    <query>         # workspace/symbol search
    python lsp_client.py bootstrap                          # self-install pyright via uv

Standard ``--stdio`` LSP framing: each message is ``Content-Length: N\\r\\n\\r\\n``
followed by ``N`` bytes of JSON.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


# ── Bootstrap ───────────────────────────────────────────────────────────────

class BootstrapError(RuntimeError):
    """Raised when pyright cannot be made available. Fails loudly, never hangs."""


def ensure_pyright(install: bool = True) -> str:
    """Return the path to ``pyright-langserver``, self-installing if needed.

    pyright wheels vendor the langserver JS bundle and run it on *system node*.
    With node present, ``uv tool install pyright`` is the whole story (~1.8s
    cold, measured 2026-06-14). With no node, pyright-python falls back to
    downloading node from nodejs.org — which may be blocked in locked-down
    containers and can hang. So this detects node and fails loudly instead.

    Raises ``BootstrapError`` rather than hanging when prerequisites are absent.
    """
    existing = shutil.which("pyright-langserver")
    if existing:
        return existing
    if not install:
        raise BootstrapError(
            "pyright-langserver not found and install=False. "
            "Install with: uv tool install pyright"
        )
    if not shutil.which("node"):
        raise BootstrapError(
            "pyright requires system 'node' but none was found on PATH.\n"
            "Without node, pyright-python falls back to downloading node from "
            "nodejs.org, which may be blocked and can hang.\n"
            "Install node (v18+) first, e.g. via your package manager or nvm, "
            "then re-run."
        )
    if not shutil.which("uv"):
        raise BootstrapError(
            "Neither pyright-langserver nor 'uv' found on PATH.\n"
            "Install uv (https://docs.astral.sh/uv/) or install pyright another "
            "way: pipx install pyright / npm install -g pyright."
        )
    try:
        subprocess.run(
            ["uv", "tool", "install", "pyright"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:  # pragma: no cover - env dependent
        raise BootstrapError(
            f"'uv tool install pyright' failed (exit {e.returncode}):\n{e.stderr}"
        ) from e
    except subprocess.TimeoutExpired as e:  # pragma: no cover - env dependent
        raise BootstrapError(
            "'uv tool install pyright' timed out after 120s. If node is absent "
            "pyright may be trying to download it; install node and retry."
        ) from e
    resolved = shutil.which("pyright-langserver")
    if not resolved:
        # uv installs into ~/.local/bin; it may not be on PATH yet this process.
        candidate = Path.home() / ".local" / "bin" / "pyright-langserver"
        if candidate.exists():
            return str(candidate)
        raise BootstrapError(
            "Installed pyright but 'pyright-langserver' is still not on PATH. "
            "Ensure ~/.local/bin is on PATH."
        )
    return resolved


# ── Positions & locations ───────────────────────────────────────────────────

@dataclass(frozen=True)
class Position:
    """A zero-based LSP position."""

    line: int
    character: int

    @classmethod
    def from_one_based(cls, line: int, col: int) -> "Position":
        """Build a zero-based position from 1-based UI coordinates."""
        return cls(line=line - 1, character=col - 1)

    def to_lsp(self) -> dict:
        return {"line": self.line, "character": self.character}


@dataclass(frozen=True)
class Location:
    """A resolved source location: path plus zero-based start/end positions."""

    path: str
    start_line: int
    start_char: int
    end_line: int
    end_char: int

    @classmethod
    def from_lsp(cls, loc: dict) -> "Location":
        # Accept both Location (uri+range) and LocationLink (targetUri+targetRange).
        uri = loc.get("uri") or loc.get("targetUri")
        rng = loc.get("range") or loc.get("targetRange")
        start, end = rng["start"], rng["end"]
        return cls(
            path=uri_to_path(uri),
            start_line=start["line"],
            start_char=start["character"],
            end_line=end["line"],
            end_char=end["character"],
        )

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "start": {"line": self.start_line, "character": self.start_char},
            "end": {"line": self.end_line, "character": self.end_char},
        }


# LSP SymbolKind enum (1-based), for human-readable kind names.
SYMBOL_KIND = {
    1: "File", 2: "Module", 3: "Namespace", 4: "Package", 5: "Class",
    6: "Method", 7: "Property", 8: "Field", 9: "Constructor", 10: "Enum",
    11: "Interface", 12: "Function", 13: "Variable", 14: "Constant",
    15: "String", 16: "Number", 17: "Boolean", 18: "Array", 19: "Object",
    20: "Key", 21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
    25: "Operator", 26: "TypeParameter",
}


@dataclass(frozen=True)
class SymbolInfo:
    """A named symbol: outline entry (documentSymbol) or search hit (workspace/symbol)."""

    name: str
    kind: int
    kind_name: str
    location: Location
    container: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind_name,
            "container": self.container,
            "location": self.location.as_dict(),
        }


def path_to_uri(path: str) -> str:
    return Path(path).resolve().as_uri()


def uri_to_path(uri: str) -> str:
    if uri.startswith("file://"):
        from urllib.parse import unquote, urlparse

        return unquote(urlparse(uri).path)
    return uri


def find_project_root(start: str) -> str:
    """Resolve the directory pyright should use as its workspace root.

    The subtle, silent failure this guards against: point pyright at a
    *sub-package* (e.g. ``scipy/optimize``) and its own absolute intra-project
    imports (``from scipy.optimize._x import Y``) no longer resolve, because
    ``scipy`` isn't importable when ``optimize`` is the root. References then
    undercount with no error — as quietly as a text grep over-counts.

    Detection is principled, not marker-based: the Python import root is the
    first ancestor that is **not itself a package**, i.e. the directory you
    would put on ``sys.path`` for ``import top_level_pkg`` to work. We climb out
    of any package the start path sits inside (every ancestor with an
    ``__init__.py``). If the start isn't inside a package, it is already an
    import-root candidate and is returned unchanged — we deliberately do NOT
    walk up to a project marker or ``.git`` from there, since that would promote
    a self-contained directory to an unrelated parent and widen every query.

    ``start`` may be a file or a directory. The return value is always an
    absolute directory path.
    """
    base = Path(start).resolve()
    if not base.is_dir():
        base = base.parent

    d = base
    while (d / "__init__.py").exists() and d.parent != d:
        d = d.parent
    return str(d)


# ── The client ──────────────────────────────────────────────────────────────

class LSPError(RuntimeError):
    """A JSON-RPC error response from the server."""


class LSPClient:
    """Owns the LSP lifecycle against ``pyright-langserver --stdio``.

    Lifecycle: ``start`` (spawn + initialize + initialized) → ``did_open`` the
    files you care about → ``wait_for_index`` → positioned queries → ``stop``
    (shutdown + exit + reap). Use as a context manager to guarantee cleanup.
    """

    def __init__(
        self,
        root: str,
        server_cmd: Optional[list[str]] = None,
        auto_install: bool = True,
        auto_root: bool = True,
    ):
        # ``scope`` is the path the caller reasons about — relative file
        # arguments resolve against it, and it scopes what callers scan/open.
        # ``root`` is what pyright is rooted at: when ``auto_root`` is set we
        # promote ``scope`` to the enclosing project/import root so the
        # project's own absolute imports resolve and references don't silently
        # undercount (see ``find_project_root``). They differ only when
        # ``scope`` sits inside a package.
        self.scope = str(Path(root).resolve())
        self.root = find_project_root(self.scope) if auto_root else self.scope
        if self.root != self.scope:
            print(
                f"python-lsp: rooted at project root {self.root} "
                f"(promoted from {self.scope} so intra-project imports resolve)",
                file=sys.stderr,
            )
        self._server_cmd = server_cmd
        self._auto_install = auto_install
        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._stderr_reader: Optional[threading.Thread] = None
        self._write_lock = threading.Lock()
        self._next_id = 1
        self._id_lock = threading.Lock()
        # id -> {"event": Event, "result": ..., "error": ...}
        self._pending: dict[int, dict] = {}
        self._pending_lock = threading.Lock()
        # uri -> list of diagnostics (latest publishDiagnostics)
        self._diagnostics: dict[str, list] = {}
        self._open_uris: set[str] = set()
        self._doc_versions: dict[str, int] = {}
        # Progress / readiness tracking.
        self._cv = threading.Condition()
        self._active_progress: set = set()
        self._progress_completed = False
        self._closed = False

    # -- framing -------------------------------------------------------------

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        with self._write_lock:
            assert self._proc and self._proc.stdin
            self._proc.stdin.write(header + body)
            self._proc.stdin.flush()

    def _notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: Any, timeout: float = 20.0) -> Any:
        with self._id_lock:
            msg_id = self._next_id
            self._next_id += 1
        event = threading.Event()
        with self._pending_lock:
            self._pending[msg_id] = {"event": event, "result": None, "error": None}
        self._send(
            {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        )
        if not event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise TimeoutError(f"LSP request {method!r} (id={msg_id}) timed out")
        with self._pending_lock:
            entry = self._pending.pop(msg_id)
        if entry["error"] is not None:
            raise LSPError(f"{method}: {entry['error']}")
        return entry["result"]

    # -- reader loop ---------------------------------------------------------

    def _read_message(self) -> Optional[dict]:
        assert self._proc and self._proc.stdout
        stream = self._proc.stdout
        headers: dict[str, str] = {}
        while True:
            line = stream.readline()
            if not line:
                return None  # EOF
            line = line.decode("ascii", errors="replace").strip()
            if line == "":
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length", 0))
        body = b""
        while len(body) < length:
            chunk = stream.read(length - len(body))
            if not chunk:
                return None
            body += chunk
        return json.loads(body.decode("utf-8"))

    def _reader_loop(self) -> None:
        while True:
            try:
                msg = self._read_message()
            except Exception:
                break
            if msg is None:
                break
            self._dispatch(msg)
        # Server stream closed: wake anyone waiting.
        with self._cv:
            self._cv.notify_all()
        with self._pending_lock:
            for entry in self._pending.values():
                entry["error"] = entry["error"] or "server stream closed"
                entry["event"].set()

    def _dispatch(self, msg: dict) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            # Response to one of our requests.
            with self._pending_lock:
                entry = self._pending.get(msg["id"])
            if entry is not None:
                entry["result"] = msg.get("result")
                entry["error"] = msg.get("error")
                entry["event"].set()
            return
        if "method" in msg and "id" in msg:
            # Server -> client request: must respond or pyright may stall.
            self._handle_server_request(msg)
            return
        if "method" in msg:
            self._handle_notification(msg)

    def _handle_server_request(self, msg: dict) -> None:
        # Any server -> client request must get a response or pyright may stall.
        # We advertise no capabilities that solicit these, but answer defensively:
        # workspace/configuration gets one empty (default) settings object per
        # item; everything else gets a null result.
        method = msg["method"]
        params = msg.get("params") or {}
        if method == "workspace/configuration":
            result: Any = [{} for _ in params.get("items", [])]
        else:
            result = None
        self._send({"jsonrpc": "2.0", "id": msg["id"], "result": result})

    def _handle_notification(self, msg: dict) -> None:
        method = msg["method"]
        params = msg.get("params") or {}
        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri")
            if uri is not None:
                with self._cv:
                    self._diagnostics[uri] = params.get("diagnostics", [])
                    self._cv.notify_all()
        elif method == "$/progress":
            self._handle_progress(params)

    def _handle_progress(self, params: dict) -> None:
        token = params.get("token")
        value = params.get("value") or {}
        kind = value.get("kind")
        with self._cv:
            if kind == "begin":
                self._active_progress.add(token)
            elif kind == "end":
                self._active_progress.discard(token)
                self._progress_completed = True
            self._cv.notify_all()

    # -- readiness -----------------------------------------------------------

    def _is_ready(self) -> bool:
        # Ready when a progress cycle has completed with nothing active, or when
        # every open document has reported diagnostics (pyright publishes for a
        # file, even an empty list, only after analyzing it).
        if self._progress_completed and not self._active_progress:
            return True
        if self._open_uris and self._open_uris <= set(self._diagnostics.keys()):
            return True
        return False

    def wait_for_index(self, timeout: float = 20.0) -> bool:
        """Block until pyright has finished analyzing, before issuing queries.

        Querying mid-index returns empty results — the most common silent
        failure. This blocks on pyright's ``$/progress`` begin/end cycle (with a
        diagnostics-arrival fallback) so queries are deterministic.

        Returns True if readiness was observed, False on timeout.
        """
        deadline = time.time() + timeout
        with self._cv:
            while time.time() < deadline:
                if self._is_ready():
                    return True
                self._cv.wait(timeout=min(0.25, max(0.0, deadline - time.time())))
            return self._is_ready()

    # -- lifecycle -----------------------------------------------------------

    def start(self, init_timeout: float = 30.0) -> "LSPClient":
        cmd = self._server_cmd
        if cmd is None:
            server = ensure_pyright(install=self._auto_install)
            cmd = [server, "--stdio"]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(
            target=self._drain_stderr, daemon=True
        )
        self._stderr_reader.start()

        root_uri = path_to_uri(self.root)
        init_params = {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "rootPath": self.root,
            "workspaceFolders": [{"uri": root_uri, "name": Path(self.root).name}],
            "capabilities": {
                "window": {"workDoneProgress": True},
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": True},
                    "definition": {"linkSupport": True},
                    "references": {},
                    "hover": {"contentFormat": ["plaintext", "markdown"]},
                    "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                    "publishDiagnostics": {"relatedInformation": True},
                },
                # Advertise ONLY workspace.symbol. Advertising
                # workspace.configuration OR workspace.workspaceFolders makes
                # pyright defer ALL analysis until the corresponding negotiation
                # completes — the server starts its service instance and then
                # goes silent (no diagnostics, no progress, queries hang). With
                # neither advertised, pyright uses its defaults and analyzes open
                # files immediately. The workspaceFolders *init param* below is
                # fine; it is the *capability* that triggers deferral.
                # (Bisected against the fixture, 2026-06-15.)
                "workspace": {"symbol": {}},
            },
        }
        self._request("initialize", init_params, timeout=init_timeout)
        self._notify("initialized", {})
        return self

    def _drain_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        for _ in iter(self._proc.stderr.readline, b""):
            pass

    def did_open(self, file: str, language_id: str = "python") -> None:
        """Open a document so the server builds its model for it."""
        path = self._abs(file)
        text = Path(path).read_text(encoding="utf-8")
        uri = path_to_uri(path)
        version = self._doc_versions.get(uri, 0) + 1
        self._doc_versions[uri] = version
        self._open_uris.add(uri)
        self._notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id,
                    "version": version,
                    "text": text,
                }
            },
        )

    def open_all(self, *files: str) -> None:
        for f in files:
            self.did_open(f)

    def stop(self, timeout: float = 5.0) -> None:
        """Shut down cleanly and reap the subprocess so sessions don't leak."""
        if self._closed:
            return
        self._closed = True
        if self._proc and self._proc.poll() is None:
            try:
                self._request("shutdown", None, timeout=timeout)
            except Exception:
                pass
            try:
                self._notify("exit", None)
            except Exception:
                pass
            try:
                self._proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
        for stream in (
            getattr(self._proc, "stdin", None),
            getattr(self._proc, "stdout", None),
            getattr(self._proc, "stderr", None),
        ):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass

    def __enter__(self) -> "LSPClient":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    # -- helpers -------------------------------------------------------------

    def _abs(self, file: str) -> str:
        p = Path(file)
        if not p.is_absolute():
            p = Path(self.scope) / p
        return str(p.resolve())

    def _text_document_position(self, file: str, line: int, col: int) -> dict:
        uri = path_to_uri(self._abs(file))
        return {
            "textDocument": {"uri": uri},
            "position": Position(line, col).to_lsp(),
        }

    def _ensure_open(self, file: str) -> None:
        uri = path_to_uri(self._abs(file))
        if uri not in self._open_uris:
            self.did_open(file)

    # -- queries -------------------------------------------------------------

    def definition(self, file: str, line: int, col: int) -> list[Location]:
        """Go-to-definition at a zero-based position; follows imports across files."""
        self._ensure_open(file)
        result = self._request(
            "textDocument/definition", self._text_document_position(file, line, col)
        )
        return _as_locations(result)

    def references(
        self, file: str, line: int, col: int, include_declaration: bool = True
    ) -> list[Location]:
        """All binding-resolved uses at a zero-based position.

        The win over ripgrep: results are resolved by pyright's binder, so a
        same-named-but-unrelated symbol is excluded.
        """
        self._ensure_open(file)
        params = self._text_document_position(file, line, col)
        params["context"] = {"includeDeclaration": include_declaration}
        result = self._request("textDocument/references", params)
        return _as_locations(result)

    def hover(self, file: str, line: int, col: int) -> Optional[str]:
        """Inferred type / signature string at a zero-based position."""
        self._ensure_open(file)
        result = self._request(
            "textDocument/hover", self._text_document_position(file, line, col)
        )
        if not result:
            return None
        return _hover_text(result.get("contents"))

    def diagnostics(self, file: str, wait: bool = True, timeout: float = 20.0) -> list:
        """pyright diagnostics for a file (from publishDiagnostics after didOpen)."""
        self._ensure_open(file)
        uri = path_to_uri(self._abs(file))
        if wait:
            deadline = time.time() + timeout
            with self._cv:
                while uri not in self._diagnostics and time.time() < deadline:
                    self._cv.wait(timeout=0.25)
        return self._diagnostics.get(uri, [])

    def document_symbols(self, file: str) -> list["SymbolInfo"]:
        """The symbol outline of one file (classes, functions, methods, ...).

        Returns a flat list in document order; nesting is captured via each
        symbol's ``container`` (the enclosing symbol's name).
        """
        self._ensure_open(file)
        uri = path_to_uri(self._abs(file))
        result = self._request(
            "textDocument/documentSymbol", {"textDocument": {"uri": uri}}
        )
        return _flatten_document_symbols(result or [], uri)

    def workspace_symbols(self, query: str) -> list["SymbolInfo"]:
        """Project-wide fuzzy symbol search (indexes the whole tree).

        Empty ``query`` returns every indexed symbol — expensive on large trees.
        """
        result = self._request("workspace/symbol", {"query": query}, timeout=120)
        out: list[SymbolInfo] = []
        for item in result or []:
            out.append(
                SymbolInfo(
                    name=item.get("name", ""),
                    kind=item.get("kind", 0),
                    kind_name=SYMBOL_KIND.get(item.get("kind", 0), "Unknown"),
                    location=Location.from_lsp(item["location"]),
                    container=item.get("containerName") or None,
                )
            )
        return out


# ── result coercion ─────────────────────────────────────────────────────────

def _flatten_document_symbols(nodes: list, uri: str) -> list["SymbolInfo"]:
    """Flatten a hierarchical DocumentSymbol tree (or flat SymbolInformation list)."""
    out: list[SymbolInfo] = []

    def walk(items: list, container: Optional[str]) -> None:
        for n in items:
            kind = n.get("kind", 0)
            # DocumentSymbol has selectionRange/range + children; SymbolInformation
            # has a `location` with uri+range instead.
            if "location" in n:
                loc = Location.from_lsp(n["location"])
                cont = n.get("containerName") or container
            else:
                rng = n.get("selectionRange") or n.get("range")
                loc = Location.from_lsp({"uri": uri, "range": rng})
                cont = container
            out.append(
                SymbolInfo(
                    name=n.get("name", ""),
                    kind=kind,
                    kind_name=SYMBOL_KIND.get(kind, "Unknown"),
                    location=loc,
                    container=cont,
                )
            )
            if n.get("children"):
                walk(n["children"], n.get("name"))

    walk(nodes, None)
    return out


def _as_locations(result: Any) -> list[Location]:
    if result is None:
        return []
    if isinstance(result, dict):
        result = [result]
    return [Location.from_lsp(item) for item in result]


def _hover_text(contents: Any) -> Optional[str]:
    if contents is None:
        return None
    if isinstance(contents, str):
        return contents.strip() or None
    if isinstance(contents, dict):
        return (contents.get("value") or "").strip() or None
    if isinstance(contents, list):
        parts = []
        for c in contents:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                parts.append(c.get("value", ""))
        return "\n".join(p for p in parts if p).strip() or None
    return str(contents)


# ── CLI ─────────────────────────────────────────────────────────────────────

def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "bootstrap":
        try:
            path = ensure_pyright(install=True)
        except BootstrapError as e:
            print(f"bootstrap failed: {e}", file=sys.stderr)
            return 1
        print(f"pyright-langserver ready: {path}")
        return 0

    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    root, command = argv[0], argv[1]
    rest = argv[2:]

    def pos_args() -> tuple[str, int, int]:
        file, line, col = rest[0], int(rest[1]), int(rest[2])
        return file, line, col

    with LSPClient(root) as client:
        if command == "diagnostics":
            file = rest[0]
            client.did_open(file)
            client.wait_for_index()
            _print_json(client.diagnostics(file))
            return 0
        if command == "symbols":
            file = rest[0]
            client.did_open(file)
            client.wait_for_index()
            _print_json([s.as_dict() for s in client.document_symbols(file)])
            return 0
        if command == "wsymbols":
            query = rest[0] if rest else ""
            client.wait_for_index()
            _print_json([s.as_dict() for s in client.workspace_symbols(query)])
            return 0

        file, line, col = pos_args()
        client.did_open(file)
        client.wait_for_index()
        if command == "definition":
            _print_json([loc.as_dict() for loc in client.definition(file, line, col)])
        elif command == "references":
            _print_json([loc.as_dict() for loc in client.references(file, line, col)])
        elif command == "hover":
            _print_json({"hover": client.hover(file, line, col)})
        else:
            print(f"unknown command: {command}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
