"""
Inverted index for fast regex search using sparse n-grams.

Architecture:
- Index maps n-gram hashes → sets of file IDs
- File IDs map back to file paths
- Query decomposes regex into literals → covering n-grams → posting list intersection
- Candidates verified by actual regex match (ripgrep or Python re)
"""

import os
import re
import sre_parse
import struct
import subprocess
import time
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sparse_ngrams import (
    FrequencyWeights,
    build_all,
    build_covering,
    compute_weights,
    ngram_hash,
    ngram_text,
    weight_crc32,
)

# Default extensions to index (source code)
DEFAULT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".mts",
    ".go", ".rs", ".rb", ".java", ".c", ".h", ".cpp", ".hpp", ".cc",
    ".cs", ".php", ".swift", ".kt", ".scala", ".lua", ".zig",
    ".sh", ".bash", ".zsh", ".fish",
    ".html", ".css", ".scss", ".less",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".md", ".txt", ".rst",
    ".sql", ".graphql", ".proto",
    ".dockerfile", ".env", ".ini", ".cfg", ".conf",
    ".r", ".R", ".jl", ".ex", ".exs", ".erl", ".hrl",
    ".vim", ".el", ".clj", ".cljs", ".ml", ".mli", ".hs",
}

# Default directories to skip
DEFAULT_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".cache", "target", "vendor",
    ".tox", ".mypy_cache", ".pytest_cache", "coverage",
    ".idea", ".vscode", ".eclipse",
}

# Max file size to index (skip giant generated files)
MAX_FILE_SIZE = 1_000_000  # 1MB


# @lat: [[code-intelligence#N-gram Indexing]]
class NgramIndex:
    """
    Sparse n-gram inverted index for a directory of source files.

    Build once, query many times. Candidate files from index lookup
    are verified with actual regex matching for correctness.
    """

    def __init__(self, weight_fn=None):
        # n-gram hash → set of file IDs
        self.postings: Dict[int, Set[int]] = {}
        # file ID → file path
        self.files: Dict[int, str] = {}
        # file path → file ID (reverse lookup)
        self._path_to_id: Dict[str, int] = {}
        # next file ID
        self._next_id: int = 0
        # weight function
        self._weight_fn = weight_fn or weight_crc32
        # frequency weights (trained from corpus)
        self._freq_weights: Optional[FrequencyWeights] = None
        # stats
        self.stats = {
            "files_indexed": 0,
            "files_skipped": 0,
            "total_ngrams": 0,
            "unique_ngrams": 0,
            "index_time_ms": 0,
            "total_bytes": 0,
        }

    def _assign_id(self, path: str) -> int:
        """Assign a numeric ID to a file path."""
        if path in self._path_to_id:
            return self._path_to_id[path]
        fid = self._next_id
        self._next_id += 1
        self.files[fid] = path
        self._path_to_id[path] = fid
        return fid

    def _should_index(self, path: str, skip_dirs: Set[str]) -> bool:
        """Check if a file should be indexed."""
        p = Path(path)

        # Check directory exclusions
        for part in p.parts:
            if part in skip_dirs:
                return False

        # Check extension
        suffix = p.suffix.lower()
        if suffix and suffix not in DEFAULT_EXTENSIONS:
            # Also accept extensionless files (Makefile, Dockerfile, etc.)
            if suffix:
                return False

        # Check if it's a Makefile/Dockerfile/etc (no extension)
        name = p.name.lower()
        known_names = {
            "makefile", "dockerfile", "vagrantfile", "gemfile",
            "rakefile", "procfile", "brewfile", "justfile",
        }
        if not suffix and name not in known_names:
            return False

        return True

    def build(
        self,
        root: str,
        skip_dirs: Optional[Set[str]] = None,
        use_frequency_weights: bool = True,
        verbose: bool = False,
    ):
        """
        Build the index from all source files under root.

        If use_frequency_weights is True, makes two passes:
        1. Train frequency table on all file contents
        2. Index using frequency-based weights (rare pairs = high weight)
        """
        skip = skip_dirs or DEFAULT_SKIP_DIRS
        t_start = time.monotonic()

        # Collect files
        file_paths = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skip dirs
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                if self._should_index(fpath, skip):
                    try:
                        size = os.path.getsize(fpath)
                        if size <= MAX_FILE_SIZE and size > 0:
                            file_paths.append(fpath)
                        else:
                            self.stats["files_skipped"] += 1
                    except OSError:
                        self.stats["files_skipped"] += 1

        if verbose:
            print(f"Found {len(file_paths)} files to index")

        # Pass 1: train frequency weights (optional)
        if use_frequency_weights:
            if verbose:
                print("Pass 1: Training frequency weights...")
            fw = FrequencyWeights()
            for fpath in file_paths:
                try:
                    with open(fpath, "rb") as f:
                        data = f.read()
                    fw.train(data)
                    self.stats["total_bytes"] += len(data)
                except (OSError, UnicodeDecodeError):
                    pass
            fw.freeze()
            self._freq_weights = fw
            self._weight_fn = fw.weight
            if verbose:
                print(f"  Trained on {self.stats['total_bytes']:,} bytes")
        else:
            # Single pass, count bytes as we go
            pass

        # Pass 2 (or only pass): build index
        if verbose:
            print("Building sparse n-gram index...")
        total_ngrams = 0
        for i, fpath in enumerate(file_paths):
            try:
                with open(fpath, "rb") as f:
                    data = f.read()

                if not use_frequency_weights:
                    self.stats["total_bytes"] += len(data)

                fid = self._assign_id(fpath)
                weights = compute_weights(data, self._weight_fn)
                ngrams = build_all(weights)

                for start, end in ngrams:
                    h = ngram_hash(data, start, end)
                    if h not in self.postings:
                        self.postings[h] = set()
                    self.postings[h].add(fid)
                    total_ngrams += 1

                self.stats["files_indexed"] += 1

                if verbose and (i + 1) % 500 == 0:
                    print(f"  Indexed {i + 1}/{len(file_paths)} files...")

            except (OSError, UnicodeDecodeError):
                self.stats["files_skipped"] += 1

        elapsed_ms = (time.monotonic() - t_start) * 1000
        self.stats["total_ngrams"] = total_ngrams
        self.stats["unique_ngrams"] = len(self.postings)
        self.stats["index_time_ms"] = round(elapsed_ms, 1)

        if verbose:
            print(f"Index built: {self.stats['files_indexed']} files, "
                  f"{self.stats['unique_ngrams']:,} unique n-grams, "
                  f"{elapsed_ms:.0f}ms")

    def _query_literal(self, literal: bytes) -> Optional[Set[int]]:
        """
        Query the index with a literal byte string.
        Returns set of candidate file IDs, or None if no n-grams extracted.
        """
        if len(literal) < 3:
            # Too short for meaningful n-gram lookup
            return None

        weights = compute_weights(literal, self._weight_fn)
        covering = build_covering(weights)

        if not covering:
            return None

        # Intersect posting lists for all covering n-grams
        candidates = None
        for start, end in covering:
            h = ngram_hash(literal, start, end)
            posting = self.postings.get(h, set())
            if candidates is None:
                candidates = set(posting)
            else:
                candidates &= posting
            # Early termination: empty intersection
            if candidates is not None and not candidates:
                return set()

        return candidates

    def _eval_plan(self, plan: "QueryPlan") -> Optional[Set[int]]:
        """
        Evaluate a query plan tree against the index.

        AND → intersect posting lists
        OR  → union posting lists
        LITERAL → look up covering n-grams
        """
        if plan.op == "literal":
            return self._query_literal(plan.literal)
        elif plan.op == "and":
            result = None
            for child in plan.children:
                child_ids = self._eval_plan(child)
                if child_ids is not None:
                    if result is None:
                        result = set(child_ids)
                    else:
                        result &= child_ids
                    if not result:
                        return set()
            return result
        elif plan.op == "or":
            result = set()
            for child in plan.children:
                child_ids = self._eval_plan(child)
                if child_ids is None:
                    # This branch can't be indexed — any file could match
                    # So the whole OR is unbounded
                    return None
                result |= child_ids
            return result
        return None

    def search(
        self,
        pattern: str,
        root: str,
        max_results: int = 100,
        verbose: bool = False,
    ) -> List[dict]:
        """
        Search for a regex pattern. Returns list of matches.

        Each match: {"file": path, "line": line_number, "text": line_text}

        Pipeline:
        1. Parse regex into query plan tree (preserving AND/OR structure)
        2. Evaluate plan against index (intersect/union posting lists)
        3. Verify candidates with ripgrep (or Python re fallback)
        """
        start = time.monotonic()

        # Build query plan from regex
        plan = extract_query_plan(pattern)

        if verbose:
            print(f"Pattern: {pattern}")
            print(f"Query plan: {plan}")

        # Evaluate plan against index
        candidate_ids: Optional[Set[int]] = None
        if plan is not None:
            candidate_ids = self._eval_plan(plan)

        if candidate_ids is None:
            # No usable plan — fall back to scanning all files
            candidate_files = list(self.files.values())
            if verbose:
                print(f"No usable literals — scanning all {len(candidate_files)} files")
        else:
            candidate_files = [self.files[fid] for fid in candidate_ids if fid in self.files]
            if verbose:
                reduction = (1 - len(candidate_files) / max(len(self.files), 1)) * 100
                print(f"Index narrowed to {len(candidate_files)}/{len(self.files)} "
                      f"files ({reduction:.0f}% reduction)")

        # Verify with actual regex matching
        matches = verify_candidates(pattern, candidate_files, root, max_results, verbose)

        elapsed_ms = (time.monotonic() - start) * 1000
        if verbose:
            print(f"Search completed: {len(matches)} matches in {elapsed_ms:.0f}ms")

        return matches


class QueryPlan:
    """
    Tree structure representing how to combine index lookups.
    
    AND nodes: all children must match (intersect posting lists)
    OR nodes: any child can match (union posting lists)
    LITERAL nodes: leaf — look up in index
    """
    __slots__ = ("op", "children", "literal")

    def __init__(self, op: str, children=None, literal: bytes = None):
        self.op = op  # "and", "or", "literal"
        self.children = children or []
        self.literal = literal

    def __repr__(self):
        if self.op == "literal":
            return f"LIT({self.literal!r})"
        kids = ", ".join(repr(c) for c in self.children)
        return f"{self.op.upper()}({kids})"


def extract_query_plan(pattern: str) -> Optional[QueryPlan]:
    """
    Parse a regex and produce a QueryPlan tree preserving AND/OR structure.

    Sequential literals → AND (intersect)
    Alternations (a|b) → OR (union)
    """
    try:
        parsed = sre_parse.parse(pattern)
    except Exception:
        encoded = pattern.encode("utf-8")
        if len(encoded) >= 3:
            return QueryPlan("literal", literal=encoded)
        return None

    plan = _build_plan(parsed)
    return _simplify(plan)


def _build_plan(parsed) -> Optional[QueryPlan]:
    """Recursively build a query plan from parsed regex."""
    parts = []  # AND children from sequential processing
    current = bytearray()

    def flush():
        nonlocal current
        if current:
            parts.append(QueryPlan("literal", literal=bytes(current)))
        current = bytearray()

    for op, av in parsed:
        if op == sre_parse.LITERAL:
            current.append(av)
        elif op == sre_parse.AT:
            pass  # anchors
        elif op == sre_parse.SUBPATTERN:
            if av[3] is not None:
                sub = _build_plan(av[3])
                if sub:
                    flush()
                    parts.append(sub)
        elif op == sre_parse.BRANCH:
            flush()
            branches = []
            for branch in av[1]:
                bp = _build_plan(branch)
                if bp:
                    branches.append(bp)
            if branches:
                if len(branches) == 1:
                    parts.append(branches[0])
                else:
                    parts.append(QueryPlan("or", children=branches))
        else:
            flush()

    flush()

    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return QueryPlan("and", children=parts)


def _simplify(plan: Optional[QueryPlan]) -> Optional[QueryPlan]:
    """Flatten nested AND(AND(...)) and OR(OR(...)) nodes."""
    if plan is None:
        return None
    if plan.op == "literal":
        return plan

    new_children = []
    for child in plan.children:
        s = _simplify(child)
        if s is None:
            continue
        # Flatten: AND(AND(a,b), c) → AND(a,b,c)
        if s.op == plan.op:
            new_children.extend(s.children)
        else:
            new_children.append(s)

    if not new_children:
        return None
    if len(new_children) == 1:
        return new_children[0]
    return QueryPlan(plan.op, children=new_children)


def extract_literals(pattern: str) -> List[bytes]:
    """
    Legacy interface: extract flat list of AND-literals from a pattern.
    For simple patterns without alternation — all literals must be present.
    """
    plan = extract_query_plan(pattern)
    if plan is None:
        return []
    lits = []
    _collect_and_literals(plan, lits)
    return lits


def _collect_and_literals(plan: QueryPlan, out: list):
    """Collect literals from AND nodes only (conservative: no OR)."""
    if plan.op == "literal":
        out.append(plan.literal)
    elif plan.op == "and":
        for child in plan.children:
            _collect_and_literals(child, out)
    # OR nodes are skipped — can't AND their children


def verify_candidates(
    pattern: str,
    candidate_files: List[str],
    root: str,
    max_results: int = 100,
    verbose: bool = False,
) -> List[dict]:
    """
    Verify candidate files by actually running the regex.
    Uses ripgrep if available, falls back to Python re.
    """
    if not candidate_files:
        return []

    # Try ripgrep first
    rg = _find_ripgrep()
    if rg:
        return _verify_ripgrep(rg, pattern, candidate_files, max_results, verbose)
    else:
        return _verify_python(pattern, candidate_files, max_results, verbose)


def _find_ripgrep() -> Optional[str]:
    """Find ripgrep binary."""
    for name in ["rg", "ripgrep"]:
        try:
            result = subprocess.run(
                ["which", name], capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
    return None


def _verify_ripgrep(
    rg_path: str,
    pattern: str,
    files: List[str],
    max_results: int,
    verbose: bool,
) -> List[dict]:
    """Verify candidates using ripgrep for speed."""
    matches = []

    # ripgrep can accept file list via stdin with --files-from
    # But simpler: pass files as arguments (may hit ARG_MAX for huge lists)
    # For large lists, batch them
    BATCH_SIZE = 500
    for i in range(0, len(files), BATCH_SIZE):
        batch = files[i : i + BATCH_SIZE]
        cmd = [
            rg_path,
            "--no-heading",
            "--with-filename",
            "--line-number",
            "--color=never",
            "--max-count=50",  # limit per file
            "-e", pattern,
        ] + batch

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.splitlines():
                # Format: file:line:text — but file paths could contain colons
                # Use --line-number to guarantee line field is numeric
                parts = line.split(":", 2)
                if len(parts) >= 3 and parts[1].isdigit():
                    matches.append({
                        "file": parts[0],
                        "line": int(parts[1]),
                        "text": parts[2],
                    })
                    if len(matches) >= max_results:
                        return matches
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            if verbose:
                print(f"ripgrep error: {e}")

    return matches


def _verify_python(
    pattern: str,
    files: List[str],
    max_results: int,
    verbose: bool,
) -> List[dict]:
    """Verify candidates using Python re (fallback)."""
    matches = []
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        if verbose:
            print(f"Invalid regex: {e}")
        return []

    for fpath in files:
        try:
            with open(fpath, "r", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    if compiled.search(line):
                        matches.append({
                            "file": fpath,
                            "line": line_num,
                            "text": line.rstrip(),
                        })
                        if len(matches) >= max_results:
                            return matches
        except OSError:
            pass

    return matches


def _brute_force_search(
    pattern: str,
    root: str,
    skip_dirs: Set[str],
    max_results: int = 100,
) -> List[dict]:
    """
    Brute-force search (no index) for benchmarking comparison.
    Walks all files and matches with ripgrep or Python re.
    """
    rg = _find_ripgrep()
    if rg:
        cmd = [
            rg,
            "--no-heading",
            "--line-number",
            "--color=never",
        ]
        for d in skip_dirs:
            cmd.extend(["--glob", f"!{d}"])
        cmd.extend(["-e", pattern, root])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            matches = []
            for line in result.stdout.splitlines():
                parts = line.split(":", 2)
                if len(parts) >= 3 and parts[1].isdigit():
                    matches.append({
                        "file": parts[0],
                        "line": int(parts[1]),
                        "text": parts[2],
                    })
                    if len(matches) >= max_results:
                        break
            return matches
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

    # Fallback: Python re over all files
    try:
        compiled = re.compile(pattern)
    except re.error:
        return []

    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(fpath)
                if size > MAX_FILE_SIZE or size == 0:
                    continue
                with open(fpath, "r", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        if compiled.search(line):
                            matches.append({
                                "file": fpath,
                                "line": line_num,
                                "text": line.rstrip(),
                            })
                            if len(matches) >= max_results:
                                return matches
            except (OSError, UnicodeDecodeError):
                pass
    return matches
