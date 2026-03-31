"""
tree-sitting engine: AST cache + symbol extraction using tree-sitter.

Parses source files, caches ASTs in memory, and provides query APIs.
Designed to be held in a long-lived process (MCP server) for fast queries.
"""

import os
import fnmatch
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Lazy import — tree-sitter installed at skill activation time
_parsers: dict = {}

EXT_TO_LANG = {
    '.py': 'python', '.pyi': 'python',
    '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript',
    '.ts': 'typescript', '.tsx': 'tsx',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.java': 'java',
    '.c': 'c', '.h': 'c',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.hh': 'cpp',
    '.cs': 'c_sharp',
    '.swift': 'swift',
    '.kt': 'kotlin', '.kts': 'kotlin',
    '.scala': 'scala',
    '.html': 'html', '.htm': 'html',
    '.css': 'css',
    '.md': 'markdown',
    '.json': 'json',
    '.yaml': 'yaml', '.yml': 'yaml',
    '.toml': 'toml',
    '.lua': 'lua',
    '.sh': 'bash', '.bash': 'bash',
    '.el': 'elisp',
    '.zig': 'zig',
    '.ex': 'elixir', '.exs': 'elixir',
}

DEFAULT_SKIP = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build',
    '.next', '.mypy_cache', '.pytest_cache', '.tox', 'target', '.cache',
    'vendor', 'coverage', '.eggs', '*.egg-info',
}


@dataclass
class Symbol:
    name: str
    kind: str
    file: str  # relative path
    line: int
    end_line: int
    signature: Optional[str] = None
    doc: Optional[str] = None
    children: list['Symbol'] = field(default_factory=list)

    def to_dict(self, include_children=True) -> dict:
        d = {
            'name': self.name,
            'kind': self.kind,
            'file': self.file,
            'line': self.line,
            'end_line': self.end_line,
        }
        if self.signature:
            d['signature'] = self.signature
        if self.doc:
            d['doc'] = self.doc
        if include_children and self.children:
            d['children'] = [c.to_dict(include_children=False) for c in self.children]
        return d

    def format_oneline(self) -> str:
        """Format as a concise one-line string."""
        parts = [f"{self.name} ({self.kind})"]
        if self.signature:
            parts.append(f"`{self.signature}`")
        parts.append(f":{self.line}-{self.end_line}")
        if self.doc:
            parts.append(f"— {self.doc}")
        return ' '.join(parts)


def _get_parser(lang: str):
    """Get or create a cached parser for the given language."""
    if lang not in _parsers:
        from tree_sitter_language_pack import get_parser
        _parsers[lang] = get_parser(lang)
    return _parsers[lang]


def _get_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _first_doc_line(text: str) -> str:
    """Extract first meaningful line from a comment."""
    text = text.strip()
    # Strip comment markers
    for prefix in ('/**', '/*', '///', '//', '#'):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = text.rstrip('*/').strip()
    for line in text.split('\n'):
        line = line.strip().lstrip('*#/').strip()
        if line and not line.startswith('@') and not line.startswith('\\'):
            return line
    return ''


def _preceding_doc(siblings: list, idx: int, source: bytes) -> Optional[str]:
    """Get doc comment preceding siblings[idx]."""
    if idx <= 0:
        return None
    target_line = siblings[idx].start_point[0]
    prev = siblings[idx - 1]
    if prev.type != 'comment':
        return None
    if target_line - prev.end_point[0] > 1:
        return None
    text = _get_text(prev, source)
    result = _first_doc_line(text)
    return result if result else None


def _python_docstring(node, source: bytes) -> Optional[str]:
    """Extract docstring from Python function/class body."""
    for child in node.children:
        if child.type == 'block':
            for stmt in child.children:
                if stmt.type == 'expression_statement':
                    for expr in stmt.children:
                        if expr.type == 'string':
                            text = _get_text(expr, source).strip('"""').strip("'''").strip()
                            return text.split('\n')[0].strip() or None
                elif stmt.type != 'comment':
                    break
            break
    return None


# ─── Extractors ───────────────────────────────────────────────────────────

def _extract_python(tree, source: bytes, relpath: str) -> list[Symbol]:
    symbols = []
    module = tree.root_node
    children = list(module.children)
    for i, node in enumerate(children):
        if node.type == 'function_definition':
            name = next((_get_text(c, source) for c in node.children if c.type == 'identifier'), '')
            if name and not name.startswith('_'):
                sig = next((_get_text(c, source) for c in node.children if c.type == 'parameters'), None)
                doc = _python_docstring(node, source)
                sym = Symbol(name=name, kind='function', file=relpath, line=node.start_point[0]+1,
                             end_line=node.end_point[0]+1, signature=sig, doc=doc)
                # Extract methods if it's weirdly at module level (rare)
                symbols.append(sym)
        elif node.type == 'class_definition':
            name = next((_get_text(c, source) for c in node.children if c.type == 'identifier'), '')
            if name and not name.startswith('_'):
                doc = _python_docstring(node, source)
                sym = Symbol(name=name, kind='class', file=relpath, line=node.start_point[0]+1,
                             end_line=node.end_point[0]+1, doc=doc)
                # Extract methods
                for child in node.children:
                    if child.type == 'block':
                        for sc in child.children:
                            if sc.type == 'function_definition':
                                mname = next((_get_text(c, source) for c in sc.children if c.type == 'identifier'), '')
                                if mname:
                                    msig = next((_get_text(c, source) for c in sc.children if c.type == 'parameters'), None)
                                    mdoc = _python_docstring(sc, source)
                                    sym.children.append(Symbol(
                                        name=mname, kind='method', file=relpath,
                                        line=sc.start_point[0]+1, end_line=sc.end_point[0]+1,
                                        signature=msig, doc=mdoc))
                symbols.append(sym)
    return symbols


def _extract_c(tree, source: bytes, relpath: str) -> list[Symbol]:
    symbols = []
    containers = {'preproc_ifdef', 'preproc_ifndef', 'preproc_if', 'preproc_else',
                  'preproc_elif', 'linkage_specification', 'declaration_list'}

    def collect(node):
        for child in node.children:
            if child.type in containers:
                yield from collect(child)
            else:
                yield child

    nodes = list(collect(tree.root_node))

    def find_func_name(node):
        for c in node.children:
            if c.type == 'function_declarator':
                for cc in c.children:
                    if cc.type == 'identifier':
                        return _get_text(cc, source)
            if c.type == 'pointer_declarator':
                result = find_func_name(c)
                if result:
                    return result
        return ''

    def return_type(node):
        parts = []
        for c in node.children:
            if c.type in ('function_declarator', 'pointer_declarator', 'compound_statement'):
                break
            if c.type == 'storage_class_specifier':
                continue
            if c.type in ('primitive_type', 'type_identifier', 'sized_type_specifier', 'type_qualifier'):
                parts.append(_get_text(c, source))
        has_ptr = any(c.type == 'pointer_declarator' for c in node.children)
        rt = ' '.join(parts)
        return (rt + ' *').strip() if has_ptr else rt

    def params(node):
        def find_fd(n):
            for c in n.children:
                if c.type == 'function_declarator':
                    return c
                if c.type == 'pointer_declarator':
                    r = find_fd(c)
                    if r: return r
            return None
        fd = find_fd(node)
        if fd:
            for c in fd.children:
                if c.type == 'parameter_list':
                    return ' '.join(_get_text(c, source).split())
        return ''

    def is_static(node):
        return any(c.type == 'storage_class_specifier' and _get_text(c, source) == 'static'
                   for c in node.children)

    for i, node in enumerate(nodes):
        if node.type == 'function_definition' and not is_static(node):
            name = find_func_name(node)
            if name:
                rt = return_type(node)
                p = params(node)
                sig = f"{p} -> {rt}" if rt else p
                doc = _preceding_doc(nodes, i, source)
                symbols.append(Symbol(name=name, kind='function', file=relpath,
                                      line=node.start_point[0]+1, end_line=node.end_point[0]+1,
                                      signature=sig, doc=doc))

        elif node.type == 'declaration' and not is_static(node):
            has_fd = any(c.type in ('function_declarator', 'pointer_declarator') for c in node.children)
            if has_fd:
                name = find_func_name(node)
                if name:
                    rt = return_type(node)
                    p = params(node)
                    sig = f"{p} -> {rt}" if rt else p
                    doc = _preceding_doc(nodes, i, source)
                    symbols.append(Symbol(name=name, kind='function', file=relpath,
                                          line=node.start_point[0]+1, end_line=node.end_point[0]+1,
                                          signature=sig, doc=doc))

        elif node.type == 'type_definition':
            name = next((_get_text(c, source) for c in node.children if c.type == 'type_identifier'), '')
            kind = 'typedef'
            for c in node.children:
                if c.type == 'struct_specifier': kind = 'struct'
                elif c.type == 'enum_specifier': kind = 'enum'
                elif c.type == 'union_specifier': kind = 'union'
            if name:
                doc = _preceding_doc(nodes, i, source)
                symbols.append(Symbol(name=name, kind=kind, file=relpath,
                                      line=node.start_point[0]+1, end_line=node.end_point[0]+1, doc=doc))

        elif node.type == 'struct_specifier':
            name = next((_get_text(c, source) for c in node.children if c.type == 'type_identifier'), '')
            if name:
                doc = _preceding_doc(nodes, i, source)
                symbols.append(Symbol(name=name, kind='struct', file=relpath,
                                      line=node.start_point[0]+1, end_line=node.end_point[0]+1, doc=doc))

        elif node.type == 'enum_specifier':
            name = next((_get_text(c, source) for c in node.children if c.type == 'type_identifier'), '')
            if name:
                doc = _preceding_doc(nodes, i, source)
                symbols.append(Symbol(name=name, kind='enum', file=relpath,
                                      line=node.start_point[0]+1, end_line=node.end_point[0]+1, doc=doc))

        elif node.type == 'preproc_def':
            name = next((_get_text(c, source) for c in node.children if c.type == 'identifier'), '')
            value = next((_get_text(c, source).strip() for c in node.children if c.type == 'preproc_arg'), '')
            if name and name.isupper() and value:
                symbols.append(Symbol(name=name, kind='define', file=relpath,
                                      line=node.start_point[0]+1, end_line=node.start_point[0]+1,
                                      signature=value))

    return symbols


def _extract_generic(tree, source: bytes, relpath: str, lang: str) -> list[Symbol]:
    """Generic extractor using node type heuristics. Works for many languages."""
    symbols = []
    # Walk top-level children looking for common patterns
    def visit(node, siblings=None, idx=None, depth=0):
        kind = None
        name = ''

        # Function/method definitions
        if node.type in ('function_definition', 'function_declaration', 'function_item',
                         'method_definition', 'method_declaration', 'function_signature_item'):
            kind = 'function'
            for c in node.children:
                if c.type in ('identifier', 'name', 'field_identifier', 'property_identifier'):
                    name = _get_text(c, source)
                    break

        # Class/struct/type definitions
        elif node.type in ('class_definition', 'class_declaration', 'struct_item',
                           'enum_item', 'trait_item', 'interface_declaration',
                           'type_declaration', 'type_spec'):
            kind = node.type.split('_')[0]  # 'class', 'struct', 'enum', etc.
            for c in node.children:
                if c.type in ('identifier', 'type_identifier', 'name'):
                    name = _get_text(c, source)
                    break

        if kind and name:
            doc = _preceding_doc(siblings, idx, source) if siblings and idx is not None else None
            symbols.append(Symbol(name=name, kind=kind, file=relpath,
                                  line=node.start_point[0]+1, end_line=node.end_point[0]+1,
                                  doc=doc))

        # Recurse (limited depth)
        if depth < 2:
            children = list(node.children)
            for i, child in enumerate(children):
                visit(child, siblings=children, idx=i, depth=depth+1)

    top = list(tree.root_node.children)
    for i, child in enumerate(top):
        visit(child, siblings=top, idx=i, depth=0)

    return symbols


# ─── Extractor dispatch ───────────────────────────────────────────────────

EXTRACTORS = {
    'python': _extract_python,
    'c': _extract_c,
}


def extract_symbols(tree, source: bytes, relpath: str, lang: str) -> list[Symbol]:
    """Extract symbols from a parsed tree."""
    extractor = EXTRACTORS.get(lang)
    if extractor:
        return extractor(tree, source, relpath)
    return _extract_generic(tree, source, relpath, lang)


def extract_imports(tree, source: bytes, lang: str) -> list[str]:
    """Extract import/include paths from a file."""
    imports = []
    for node in tree.root_node.children:
        if lang == 'python':
            if node.type == 'import_statement':
                for c in node.children:
                    if c.type == 'dotted_name':
                        imports.append(_get_text(c, source))
            elif node.type == 'import_from_statement':
                for c in node.children:
                    if c.type in ('dotted_name', 'relative_import'):
                        imports.append(_get_text(c, source))
                        break
        elif lang in ('c', 'cpp'):
            if node.type == 'preproc_include':
                for c in node.children:
                    if c.type in ('system_lib_string', 'string_literal'):
                        imports.append(_get_text(c, source).strip('"<>'))
        elif lang in ('javascript', 'typescript', 'tsx'):
            if node.type == 'import_statement':
                for c in node.children:
                    if c.type == 'string':
                        imports.append(_get_text(c, source).strip('"\''))
        elif lang == 'go':
            if node.type == 'import_declaration':
                def find_imports(n):
                    if n.type == 'interpreted_string_literal':
                        imports.append(_get_text(n, source).strip('"'))
                    for c in n.children:
                        find_imports(c)
                find_imports(node)
        elif lang == 'rust':
            if node.type == 'use_declaration':
                for c in node.children:
                    if c.type in ('scoped_identifier', 'identifier'):
                        imports.append(_get_text(c, source))
    return imports


# ─── Cache ────────────────────────────────────────────────────────────────

@dataclass
class FileEntry:
    path: str       # relative path
    lang: str
    source: bytes
    tree: object    # tree-sitter Tree
    symbols: list[Symbol]
    imports: list[str]


class CodeCache:
    """In-memory cache of parsed source files and extracted symbols."""

    def __init__(self):
        self.root: Optional[Path] = None
        self.files: dict[str, FileEntry] = {}  # relpath -> FileEntry
        self._symbol_index: dict[str, list[Symbol]] = {}  # name -> [Symbol, ...]

    @property
    def is_loaded(self) -> bool:
        return self.root is not None and len(self.files) > 0

    def scan(self, root: str, skip: set[str] | None = None) -> dict:
        """Parse all recognized files under root. Returns stats."""
        self.root = Path(root).resolve()
        self.files.clear()
        self._symbol_index.clear()
        skip_dirs = skip or DEFAULT_SKIP
        total_bytes = 0
        errors = 0

        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames
                           if d not in skip_dirs and not d.startswith('.')]
            for fn in sorted(filenames):
                fp = Path(dirpath) / fn
                lang = EXT_TO_LANG.get(fp.suffix.lower())
                if not lang:
                    continue
                relpath = str(fp.relative_to(self.root))
                try:
                    source = fp.read_bytes()
                    total_bytes += len(source)
                    parser = _get_parser(lang)
                    tree = parser.parse(source)
                    syms = extract_symbols(tree, source, relpath, lang)
                    imps = extract_imports(tree, source, lang)
                    self.files[relpath] = FileEntry(
                        path=relpath, lang=lang, source=source,
                        tree=tree, symbols=syms, imports=imps)
                    # Index symbols
                    for sym in syms:
                        self._symbol_index.setdefault(sym.name, []).append(sym)
                        for child in sym.children:
                            self._symbol_index.setdefault(child.name, []).append(child)
                except Exception as e:
                    errors += 1

        return {
            'root': str(self.root),
            'files': len(self.files),
            'symbols': sum(len(e.symbols) for e in self.files.values()),
            'bytes': total_bytes,
            'errors': errors,
            'languages': sorted(set(e.lang for e in self.files.values())),
        }

    def find_symbol(self, query: str, kind: str | None = None,
                    limit: int = 20) -> list[Symbol]:
        """Find symbols matching a name pattern. Supports * wildcards."""
        results = []
        if '*' in query or '?' in query:
            for name, syms in self._symbol_index.items():
                if fnmatch.fnmatch(name, query):
                    results.extend(syms)
        elif query in self._symbol_index:
            results = list(self._symbol_index[query])
        else:
            # Substring match
            q = query.lower()
            for name, syms in self._symbol_index.items():
                if q in name.lower():
                    results.extend(syms)
        if kind:
            results = [s for s in results if s.kind == kind]
        return results[:limit]

    def file_symbols(self, path: str) -> list[Symbol]:
        """Get all symbols in a specific file."""
        entry = self.files.get(path)
        if entry:
            return entry.symbols
        # Try matching by basename or partial path
        for relpath, entry in self.files.items():
            if relpath.endswith(path) or path in relpath:
                return entry.symbols
        return []

    def file_imports(self, path: str) -> list[str]:
        """Get imports for a file."""
        entry = self.files.get(path)
        if entry:
            return entry.imports
        for relpath, entry in self.files.items():
            if relpath.endswith(path) or path in relpath:
                return entry.imports
        return []

    def dir_overview(self, dirpath: str = '', depth: int = 1) -> str:
        """Get a directory overview showing files and top-level symbols."""
        lines = []
        # Normalize path
        dirpath = dirpath.strip('/')

        # Collect files and subdirs
        files_here = []
        subdirs = set()
        for relpath, entry in sorted(self.files.items()):
            if dirpath and not relpath.startswith(dirpath + '/') and relpath != dirpath:
                continue
            if not dirpath:
                rest = relpath
            else:
                rest = relpath[len(dirpath)+1:]

            parts = rest.split('/')
            if len(parts) == 1:
                files_here.append(entry)
            elif depth > 0 and len(parts) > 1:
                subdirs.add(parts[0])

        display = dirpath or str(self.root.name) if self.root else '.'
        lines.append(f"# {display}/")
        if subdirs:
            lines.append(f"\n## Directories")
            for sd in sorted(subdirs):
                subpath = f"{dirpath}/{sd}" if dirpath else sd
                file_count = sum(1 for r in self.files if r.startswith(subpath + '/'))
                lines.append(f"  {sd}/ ({file_count} files)")

        if files_here:
            lines.append(f"\n## Files ({len(files_here)})")
            for entry in files_here:
                fname = Path(entry.path).name
                sym_summary = ', '.join(
                    f"{s.name}({s.kind[0]})" for s in entry.symbols[:8])
                if len(entry.symbols) > 8:
                    sym_summary += f", ... +{len(entry.symbols)-8}"
                lines.append(f"  {fname}: {sym_summary}" if sym_summary else f"  {fname}")

        return '\n'.join(lines)

    def get_source_range(self, filepath: str, start_line: int, end_line: int) -> str:
        """Get source code for a line range."""
        entry = self.files.get(filepath)
        if not entry:
            for rp, e in self.files.items():
                if rp.endswith(filepath) or filepath in rp:
                    entry = e
                    break
        if not entry:
            return f"File not found: {filepath}"
        lines = entry.source.decode('utf-8', errors='replace').split('\n')
        selected = lines[start_line-1:end_line]
        return '\n'.join(f"{start_line+i:4d} | {line}" for i, line in enumerate(selected))

    def references(self, symbol_name: str, limit: int = 20) -> list[dict]:
        """Find text references to a symbol across the codebase."""
        results = []
        name_bytes = symbol_name.encode()
        for relpath, entry in self.files.items():
            if name_bytes not in entry.source:
                continue
            lines = entry.source.decode('utf-8', errors='replace').split('\n')
            for i, line in enumerate(lines):
                if symbol_name in line:
                    results.append({
                        'file': relpath,
                        'line': i + 1,
                        'text': line.strip()[:120],
                    })
                    if len(results) >= limit:
                        return results
        return results

    def tree_overview(self) -> str:
        """High-level directory tree with symbol counts."""
        if not self.root:
            return "No codebase scanned."
        dir_stats: dict[str, dict] = {}
        for relpath, entry in self.files.items():
            dirpart = str(Path(relpath).parent)
            if dirpart == '.':
                dirpart = ''
            if dirpart not in dir_stats:
                dir_stats[dirpart] = {'files': 0, 'symbols': 0, 'langs': set()}
            dir_stats[dirpart]['files'] += 1
            dir_stats[dirpart]['symbols'] += len(entry.symbols)
            dir_stats[dirpart]['langs'].add(entry.lang)

        lines = [f"# {self.root.name}/ ({len(self.files)} files, "
                 f"{sum(len(e.symbols) for e in self.files.values())} symbols)\n"]

        for dirpath in sorted(dir_stats.keys()):
            stats = dir_stats[dirpath]
            indent = '  ' * dirpath.count('/') if dirpath else ''
            dirname = Path(dirpath).name if dirpath else '.'
            langs = ','.join(sorted(stats['langs']))
            lines.append(f"{indent}{dirname}/ — {stats['files']} files, "
                         f"{stats['symbols']} symbols [{langs}]")

        return '\n'.join(lines)


# Singleton for CLI/MCP use
cache = CodeCache()
