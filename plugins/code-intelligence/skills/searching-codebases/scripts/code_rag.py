"""
code_rag.py — TF-IDF semantic search over codebases
====================================================

Semantic search layer that bridges natural language intent to actual
codebase identifiers. Indexes docstrings, comments, function signatures,
markdown sections, and _MAP.md entries (if present).

Zero dependencies beyond scikit-learn + numpy (pre-installed).

Usage:
    python3 code_rag.py index /path/to/repo
    python3 code_rag.py search /path/to/repo "retry logic with backoff"
    python3 code_rag.py search /path/to/repo "authentication flow" --top 10
    python3 code_rag.py search /path/to/repo "error handling" --grouped
    python3 code_rag.py search /path/to/repo "middleware" --rg
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ── Chunk extraction ─────────────────────────────────────────────

@dataclass
class Chunk:
    """A searchable unit extracted from a source file."""
    file: str          # relative path from repo root
    line: int          # starting line number (1-indexed)
    kind: str          # function, class, module_doc, section, map_entry
    name: str          # identifier or heading
    text: str          # searchable content (docstring + signature + comments)
    end_line: int = 0

    @property
    def loc(self) -> str:
        return f"{self.file}:{self.line}"


def _extract_python(filepath: str, rel_path: str) -> list[Chunk]:
    """Extract functions, classes, and module docstrings from Python files.
    
    Uses regex rather than AST intentionally — we want docstrings, comments,
    and identifiers for TF-IDF vocabulary, not syntactic correctness.
    """
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
            lines = content.split('\n')
    except OSError:
        return []

    chunks = []

    # Module-level docstring
    mod_match = re.match(
        r'\s*(?:#[^\n]*\n)*\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', content
    )
    if mod_match:
        doc = mod_match.group(1).strip('"\' \n')
        if len(doc) > 20:
            chunks.append(Chunk(
                file=rel_path, line=1, kind="module_doc",
                name=Path(rel_path).stem, text=doc,
            ))

    # Functions and classes with decorators, signatures, docstrings, nearby comments
    pattern = re.compile(
        r'^((?:[ \t]*@\w+[^\n]*\n)*)'   # decorators
        r'^([ \t]*)(def|class)\s+'        # indent + keyword
        r'(\w+)'                          # name
        r'([^\n]*)\n'                     # rest of signature line
        r'((?:[ \t]*"""[\s\S]*?"""'       # optional docstring
        r"|[ \t]*'''[\s\S]*?''')?)",
        re.MULTILINE
    )

    for match in pattern.finditer(content):
        decorators = match.group(1).strip()
        kind = "class" if match.group(3) == "class" else "function"
        name = match.group(4)
        signature = f"{match.group(3)} {name}{match.group(5).strip()}"
        docstring = match.group(6).strip('"\' \n\t') if match.group(6) else ""
        line_num = content[:match.start()].count('\n') + 1

        text_parts = [name, signature]
        if decorators:
            text_parts.append(decorators)
        if docstring:
            text_parts.append(docstring)

        # Grab inline comments in the next ~20 lines
        body_start = match.end()
        body_lines = content[body_start:body_start + 2000].split('\n')[:20]
        comments = [
            l.strip().lstrip('#').strip()
            for l in body_lines if l.strip().startswith('#')
        ]
        if comments:
            text_parts.extend(comments)

        chunks.append(Chunk(
            file=rel_path, line=line_num, kind=kind,
            name=name, text=" ".join(text_parts),
            end_line=line_num + len((match.group(6) or "").split('\n')),
        ))

    return chunks


def _extract_markdown(filepath: str, rel_path: str) -> list[Chunk]:
    """Extract heading-based sections from Markdown files."""
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []

    chunks = []
    heading = None
    section_lines = []
    start = 1

    for i, line in enumerate(lines, 1):
        m = re.match(r'^(#{1,3})\s+(.+)', line)
        if m:
            if heading and section_lines:
                text = " ".join(section_lines)
                if len(text) > 30:
                    chunks.append(Chunk(
                        file=rel_path, line=start, kind="section",
                        name=heading, text=text, end_line=i - 1,
                    ))
            heading = m.group(2).strip()
            section_lines = [heading]
            start = i
        elif heading:
            stripped = line.strip()
            if stripped and not stripped.startswith('```'):
                section_lines.append(stripped)

    if heading and section_lines:
        text = " ".join(section_lines)
        if len(text) > 30:
            chunks.append(Chunk(
                file=rel_path, line=start, kind="section",
                name=heading, text=text, end_line=len(lines),
            ))

    return chunks


def _extract_map_entries(filepath: str, rel_path: str) -> list[Chunk]:
    """Extract file entries from _MAP.md files (if present in the repo).
    
    Each ### file heading becomes a chunk with the function signatures and
    class hierarchies as searchable text.
    """
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
    except OSError:
        return []

    chunks = []
    sections = re.split(r'^### (.+)$', content, flags=re.MULTILINE)

    for i in range(1, len(sections), 2):
        filename = sections[i].strip()
        body = sections[i + 1] if i + 1 < len(sections) else ""

        if len(body.strip()) > 20:
            map_dir = str(Path(rel_path).parent)
            source_path = f"{map_dir}/{filename}" if map_dir != "." else filename
            chunks.append(Chunk(
                file=source_path, line=1, kind="map_entry",
                name=filename, text=f"{filename} {body}",
            ))

    return chunks


def _extract_js_ts(filepath: str, rel_path: str) -> list[Chunk]:
    """Extract functions, classes, and interfaces from JS/TS/TSX/JSX files.

    Covers: function declarations, arrow functions assigned to const/let/var,
    class declarations, interface/type declarations, exported members,
    and JSDoc comments preceding any of the above.
    """
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
    except OSError:
        return []

    chunks = []

    # Module-level JSDoc or leading block comment
    mod_match = re.match(r'\s*(/\*\*[\s\S]*?\*/)', content)
    if mod_match:
        doc = mod_match.group(1).strip('/* \n')
        if len(doc) > 20:
            chunks.append(Chunk(
                file=rel_path, line=1, kind="module_doc",
                name=Path(rel_path).stem, text=doc,
            ))

    # --- Pattern 1: function/class/interface declarations ---
    # Captures: export? async? function name(...), class Name, interface Name, type Name
    decl_pattern = re.compile(
        r'(/\*\*[\s\S]*?\*/\s*)?'                        # optional JSDoc (group 1)
        r'^[ \t]*(export\s+(?:default\s+)?)?'             # optional export (group 2)
        r'(async\s+)?'                                     # optional async (group 3)
        r'(function\*?|class|interface|type|enum)\s+'      # keyword (group 4)
        r'(\w+)'                                           # name (group 5)
        r'([^\n]*)',                                        # rest of line (group 6)
        re.MULTILINE
    )

    for match in decl_pattern.finditer(content):
        jsdoc = match.group(1) or ""
        jsdoc_clean = re.sub(r'[/*]', ' ', jsdoc).strip()
        keyword = match.group(4)
        name = match.group(5)
        rest = match.group(6).strip()
        line_num = content[:match.start()].count('\n') + 1

        kind_map = {
            'function': 'function', 'class': 'class',
            'interface': 'class', 'type': 'class', 'enum': 'class',
        }
        # Strip trailing * from function*
        kind = kind_map.get(keyword.rstrip('*'), 'function')

        text_parts = [name, f"{keyword} {name}{rest}"]
        if jsdoc_clean:
            text_parts.append(jsdoc_clean)

        chunks.append(Chunk(
            file=rel_path, line=line_num, kind=kind,
            name=name, text=" ".join(text_parts),
        ))

    # --- Pattern 2: arrow functions assigned to variables ---
    # const myFunc = (...) => { ... }
    # const myFunc: Type = (...) => ...
    arrow_pattern = re.compile(
        r'(/\*\*[\s\S]*?\*/\s*)?'                         # optional JSDoc
        r'^[ \t]*(export\s+(?:default\s+)?)?'              # optional export
        r'(const|let|var)\s+'                              # binding keyword
        r'(\w+)'                                           # name (group 4)
        r'([^=]*?)\s*='                                    # type annotation etc
        r'\s*(?:async\s+)?'                                # optional async
        r'\([^)]*\)\s*(?::\s*[^=]+?)?\s*=>',              # arrow function signature
        re.MULTILINE
    )

    for match in arrow_pattern.finditer(content):
        jsdoc = match.group(1) or ""
        jsdoc_clean = re.sub(r'[/*]', ' ', jsdoc).strip()
        name = match.group(4)
        line_num = content[:match.start()].count('\n') + 1

        # Skip if already captured by declaration pattern (unlikely but safe)
        text_parts = [name, match.group(0).split('=>')[0].strip()]
        if jsdoc_clean:
            text_parts.append(jsdoc_clean)

        chunks.append(Chunk(
            file=rel_path, line=line_num, kind="function",
            name=name, text=" ".join(text_parts),
        ))

    # --- Pattern 3: class methods (inside class bodies) ---
    method_pattern = re.compile(
        r'(/\*\*[\s\S]*?\*/\s*)?'                         # optional JSDoc
        r'^[ \t]+((?:static|async|get|set|private|protected|public|readonly)\s+)*'
        r'(\w+)\s*\(',                                     # method name + open paren
        re.MULTILINE
    )

    for match in method_pattern.finditer(content):
        jsdoc = match.group(1) or ""
        jsdoc_clean = re.sub(r'[/*]', ' ', jsdoc).strip()
        name = match.group(3)
        line_num = content[:match.start()].count('\n') + 1

        # Skip common false positives
        if name in ('if', 'for', 'while', 'switch', 'catch', 'return',
                     'require', 'import', 'console', 'throw', 'new',
                     'typeof', 'instanceof', 'delete', 'void', 'yield',
                     'await', 'super', 'this'):
            continue

        text_parts = [name]
        if jsdoc_clean:
            text_parts.append(jsdoc_clean)

        chunks.append(Chunk(
            file=rel_path, line=line_num, kind="function",
            name=name, text=" ".join(text_parts),
        ))

    return chunks


def _extract_yaml(filepath: str, rel_path: str) -> list[Chunk]:
    """Extract top-level keys and commented sections from YAML files.

    YAML files often contain infrastructure config, CI/CD pipelines,
    Kubernetes manifests, docker-compose services, etc. The top-level
    keys and their comments are the most searchable units.
    """
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []

    # Skip very large YAML files (likely generated, e.g. lockfiles)
    if len(lines) > 2000:
        return []

    chunks = []
    current_key = None
    current_lines = []
    current_start = 1
    comment_buffer = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Accumulate comment lines preceding a key
        if stripped.startswith('#'):
            comment_buffer.append(stripped.lstrip('#').strip())
            continue

        # Top-level key: no leading whitespace, ends with ':'
        top_key_match = re.match(r'^([a-zA-Z_][\w.-]*)\s*:', line)
        if top_key_match:
            # Flush previous section
            if current_key and current_lines:
                text = " ".join(current_lines)
                if len(text) > 15:
                    chunks.append(Chunk(
                        file=rel_path, line=current_start, kind="section",
                        name=current_key, text=text,
                    ))

            current_key = top_key_match.group(1)
            current_lines = [current_key]
            current_start = i

            # Include preceding comments as searchable text
            if comment_buffer:
                current_lines.extend(comment_buffer)
            comment_buffer = []

        elif current_key and stripped:
            # Nested content: include values and inline comments
            # Strip YAML syntax noise but keep identifiers and values
            clean = re.sub(r'^\s*-\s*', '', stripped)
            clean = clean.split('#')[0].strip()  # strip inline comments into separate add
            inline_comment = stripped.split('#')[1].strip() if '#' in stripped else ""
            if clean:
                current_lines.append(clean)
            if inline_comment:
                current_lines.append(inline_comment)
        else:
            comment_buffer = []

    # Flush last section
    if current_key and current_lines:
        text = " ".join(current_lines)
        if len(text) > 15:
            chunks.append(Chunk(
                file=rel_path, line=current_start, kind="section",
                name=current_key, text=text,
            ))

    # Also create a file-level chunk with the whole file as context
    # (useful for small config files like docker-compose.yml)
    if len(lines) < 100:
        all_text = " ".join(
            l.strip() for l in lines
            if l.strip() and not l.strip().startswith('---')
        )
        if len(all_text) > 30:
            chunks.append(Chunk(
                file=rel_path, line=1, kind="module_doc",
                name=Path(rel_path).stem, text=all_text,
            ))

    return chunks


# ── Index ────────────────────────────────────────────────────────

SKIP_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist',
    'build', '.next', '.mypy_cache', '.pytest_cache', '.tox', '.eggs',
    '.ruff_cache', 'target', 'coverage', '.coverage',
}

EXTRACTORS = {
    '.py': _extract_python,
    '.md': _extract_markdown,
    '.js': _extract_js_ts,
    '.jsx': _extract_js_ts,
    '.ts': _extract_js_ts,
    '.tsx': _extract_js_ts,
    '.mjs': _extract_js_ts,
    '.mts': _extract_js_ts,
    '.yaml': _extract_yaml,
    '.yml': _extract_yaml,
}


@dataclass
class Index:
    """TF-IDF index over code chunks."""
    chunks: list[Chunk] = field(default_factory=list)
    vectorizer: Optional[TfidfVectorizer] = None
    matrix: Optional[object] = None
    build_time_ms: float = 0
    repo_path: str = ""

    def build(self, repo_path: str, skip_dirs: set[str] = None):
        """Walk repo, extract chunks, build TF-IDF matrix."""
        t0 = time.monotonic()
        self.repo_path = str(repo_path)
        skip = skip_dirs or SKIP_DIRS
        self.chunks = []

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith('.')]

            for fname in files:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, repo_path)
                ext = Path(fname).suffix.lower()

                if fname == "_MAP.md":
                    self.chunks.extend(_extract_map_entries(fpath, rel))
                elif ext in EXTRACTORS:
                    self.chunks.extend(EXTRACTORS[ext](fpath, rel))

        if not self.chunks:
            print("WARNING: No chunks extracted", file=sys.stderr)
            return self

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_df=0.80,
            min_df=2,
            stop_words="english",
            max_features=50000,
            token_pattern=r'(?u)\b[a-zA-Z_]\w{1,}\b',
        )
        self.matrix = self.vectorizer.fit_transform([c.text for c in self.chunks])
        self.build_time_ms = (time.monotonic() - t0) * 1000
        return self

    def search(self, query: str, top_k: int = 5, min_score: float = 0.01
               ) -> list[tuple[Chunk, float]]:
        """Semantic search: rank chunks by cosine similarity to query."""
        if self.vectorizer is None or self.matrix is None:
            return []

        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.matrix).flatten()
        indices = scores.argsort()[::-1]

        results = []
        for idx in indices:
            if scores[idx] < min_score:
                break
            results.append((self.chunks[idx], float(scores[idx])))
            if len(results) >= top_k:
                break
        return results

    def search_grouped(self, query: str, top_k: int = 10, min_score: float = 0.01
                       ) -> dict[str, list[tuple[Chunk, float]]]:
        """Search and group by file — useful for feeding targets to grep."""
        results = self.search(query, top_k=top_k * 3, min_score=min_score)
        grouped = {}
        for chunk, score in results:
            grouped.setdefault(chunk.file, []).append((chunk, score))
        sorted_files = sorted(
            grouped.items(), key=lambda x: x[1][0][1], reverse=True
        )
        return dict(sorted_files[:top_k])

    def stats(self) -> dict:
        if not self.chunks:
            return {"chunks": 0}
        kinds = {}
        for c in self.chunks:
            kinds[c.kind] = kinds.get(c.kind, 0) + 1
        return {
            "chunks": len(self.chunks),
            "files": len(set(c.file for c in self.chunks)),
            "vocabulary": len(self.vectorizer.get_feature_names_out()) if self.vectorizer else 0,
            "build_ms": round(self.build_time_ms),
            "kinds": kinds,
        }


# ── Output formatting ────────────────────────────────────────────

def _sanitize(text: str) -> str:
    """Strip HTML entities and normalize whitespace."""
    import html
    return html.unescape(text).replace('\n', ' ').strip()


def _format_results(results: list[tuple[Chunk, float]]) -> str:
    lines = []
    for chunk, score in results:
        preview = _sanitize(chunk.text[:140])
        if len(chunk.text) > 140:
            preview += "..."
        lines.append(f"  {score:.3f}  [{chunk.kind}] {chunk.name}  {chunk.loc}")
        lines.append(f"         {preview}")
        lines.append("")
    return "\n".join(lines)


def _format_grouped(grouped: dict[str, list[tuple[Chunk, float]]]) -> str:
    lines = []
    for filepath, hits in grouped.items():
        lines.append(f"\n  {filepath}")
        for chunk, score in hits:
            name = _sanitize(chunk.name)
            lines.append(
                f"    {score:.3f}  {chunk.kind:12s}  {name} :{chunk.line}"
            )
    return "\n".join(lines)


def _format_for_grep(grouped: dict[str, list[tuple[Chunk, float]]],
                     repo_path: str) -> str:
    lines = ["# Files ranked by relevance (use with grep -n -A25):"]
    for filepath, hits in grouped.items():
        best_score = hits[0][1]
        names = [_sanitize(h[0].name) for h in hits[:3]]
        lines.append(f"# score={best_score:.3f} matches: {', '.join(names)}")
        lines.append(os.path.join(repo_path, filepath))
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    repo_path = sys.argv[2]

    if cmd == "index":
        idx = Index()
        idx.build(repo_path)
        print(json.dumps(idx.stats(), indent=2))

    elif cmd == "search":
        if len(sys.argv) < 4:
            print("Usage: code_rag.py search /path/to/repo \"query\" [options]",
                  file=sys.stderr)
            sys.exit(1)

        query = sys.argv[3]
        top_k = 5
        grouped = "--grouped" in sys.argv
        rg = "--rg" in sys.argv

        for i, arg in enumerate(sys.argv):
            if arg == "--top" and i + 1 < len(sys.argv):
                top_k = int(sys.argv[i + 1])

        idx = Index()
        idx.build(repo_path)
        stats = idx.stats()
        print(f"Indexed {stats['chunks']} chunks from {stats['files']} files "
              f"({stats['vocabulary']} features, {stats['build_ms']}ms)",
              file=sys.stderr)

        if grouped or rg:
            results = idx.search_grouped(query, top_k=top_k)
            if rg:
                print(_format_for_grep(results, repo_path))
            else:
                print(_format_grouped(results))
        else:
            results = idx.search(query, top_k=top_k)
            if results:
                print(_format_results(results))
            else:
                print("  No results above threshold.", file=sys.stderr)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
