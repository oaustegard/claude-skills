#!/usr/bin/env python3
"""
search.py - Hybrid Grep-to-AST Retrieval Tool
Locates matches with ripgrep, then expands them into full code blocks using tree-sitter.
"""

import subprocess
import json
import sys
import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Set
from pathlib import Path
import argparse

# Try to import tree-sitter-language-pack
try:
    from tree_sitter_language_pack import get_parser
except ImportError:
    print("Error: tree-sitter-language-pack not found. Please install it using uv venv /home/claude/.venv\nuv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python.", file=sys.stderr)
    sys.exit(1)

# Configuration: Relevant node types for "context" in each language
# These are the nodes we want to capture (Functions, Classes, etc.)
RELEVANT_NODE_TYPES = {
    'python': {'function_definition', 'class_definition'},
    'javascript': {'function_declaration', 'class_declaration', 'method_definition', 'variable_declarator', 'arrow_function', 'function_expression'},
    'typescript': {'function_declaration', 'class_declaration', 'method_definition', 'variable_declarator', 'arrow_function', 'function_expression', 'interface_declaration', 'enum_declaration'},
    'go': {'function_declaration', 'type_declaration', 'method_declaration'},
    'rust': {'function_item', 'struct_item', 'impl_item', 'trait_item', 'enum_item', 'mod_item'},
    'ruby': {'method', 'class', 'module'},
    'java': {'class_declaration', 'interface_declaration', 'method_declaration', 'constructor_declaration'},
    'c': {'function_definition', 'struct_specifier'},
    'cpp': {'function_definition', 'class_specifier', 'struct_specifier'},
    'php': {'function_definition', 'class_declaration', 'method_declaration'},
    'c_sharp': {'class_declaration', 'method_declaration', 'interface_declaration', 'struct_declaration', 'enum_declaration', 'namespace_declaration'},
}

# Mapping extensions to languages (consistent with tree-sitter-language-pack)
EXT_TO_LANG = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.java': 'java',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'cpp',
    '.hpp': 'cpp',
    '.cc': 'cpp',
    '.php': 'php',
    '.cs': 'c_sharp',
}

@dataclass
class CodeContext:
    file_path: str
    start_line: int
    end_line: int
    match_line: int
    node_type: str
    name: str
    source: str
    language: str

class HybridRetriever:
    def __init__(self):
        self.parsers = {}

    def _get_language(self, file_path: str) -> Optional[str]:
        ext = os.path.splitext(file_path)[1].lower()
        return EXT_TO_LANG.get(ext)

    def _get_parser(self, language: str):
        if language not in self.parsers:
            try:
                self.parsers[language] = get_parser(language)
            except Exception as e:
                print(f"Warning: Could not load parser for {language}: {e}", file=sys.stderr)
                self.parsers[language] = None
        return self.parsers[language]

    def _run_ripgrep(self, query: str, path: str, glob: Optional[str] = None) -> List[Dict]:
        """
        Phase 1: The Dragnet. Fast, text-based search.
        """
        command = [
            "rg", "--json", "-e", query,
            "--path-separator", "/",
            path
        ]
        if glob:
            command.extend(["--glob", glob])

        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except FileNotFoundError:
            # Auto-install ripgrep and retry
            print("ripgrep not found, installing...", file=sys.stderr)
            install_result = subprocess.run(
                ["apt-get", "install", "-y", "-qq", "ripgrep"],
                capture_output=True, text=True
            )
            if install_result.returncode != 0:
                print(f"Error: Failed to install ripgrep: {install_result.stderr}", file=sys.stderr)
                sys.exit(1)
            # Retry the search
            result = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
        except Exception as e:
            print(f"Error running ripgrep: {e}", file=sys.stderr)
            return []

        matches = []
        for line in result.stdout.splitlines():
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    matches.append(data["data"])
            except json.JSONDecodeError:
                continue
        return matches

    def _get_node_name(self, node, source_bytes: bytes) -> str:
        """Attempt to extract a name from a node."""
        # Generic heuristic: look for "name" or "identifier" child
        child = node.child_by_field_name("name")
        if child:
            return source_bytes[child.start_byte:child.end_byte].decode('utf-8', errors='replace')

        # Fallback: scan children for identifier
        for child in node.children:
            if child.type in ('identifier', 'type_identifier', 'property_identifier', 'name'):
                 return source_bytes[child.start_byte:child.end_byte].decode('utf-8', errors='replace')

        return "anonymous"

    def _get_node_at_line(self, root_node, line_number: int, language: str):
        """
        Finds the smallest relevant node (Function/Class) containing the line number.
        """
        target_node = None
        relevant_types = RELEVANT_NODE_TYPES.get(language, set())

        cursor = root_node.walk()
        visited_children = False

        while True:
            # Check if current node covers the line
            if cursor.node.start_point[0] <= line_number and cursor.node.end_point[0] >= line_number:

                # If this node is one of our target types, it's a candidate
                # ONLY update if we are visiting for the first time (going down)
                # This prevents backtracking from overwriting a more specific match with a parent.
                if not visited_children and cursor.node.type in relevant_types:
                    target_node = cursor.node

                if not visited_children:
                    if cursor.goto_first_child():
                        continue

            visited_children = True
            if cursor.goto_next_sibling():
                visited_children = False
                continue

            if cursor.goto_parent():
                visited_children = True
                continue
            else:
                break

        return target_node

    def _expand_context(self, file_path: str, line_number: int) -> Optional[CodeContext]:
        """
        Phase 2: The Scalpel. Syntax-aware context expansion.
        """
        lang = self._get_language(file_path)
        if not lang:
            return None # Skip unsupported languages

        parser = self._get_parser(lang)
        if not parser:
            return None

        try:
            with open(file_path, "rb") as f:
                source_bytes = f.read()

            tree = parser.parse(source_bytes)
            node = self._get_node_at_line(tree.root_node, line_number, lang)

            if not node:
                # Fallback: If no AST match, we could return the line, but for this tool
                # we primarily want the AST block.
                # Optionally, we could return a small window around the line.
                # For now, let's stick to returning None if no structural context is found,
                # effectively filtering out "noise" (comments, top-level scripts) unless we add logic for them.
                return None

            node_name = self._get_node_name(node, source_bytes)

            return CodeContext(
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                match_line=line_number + 1,
                node_type=node.type,
                name=node_name,
                source=source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='replace'),
                language=lang
            )

        except Exception as e:
            # print(f"Error parsing {file_path}: {e}", file=sys.stderr)
            return None

    def search(self, query: str, path: str = ".", glob: Optional[str] = None) -> List[CodeContext]:
        raw_matches = self._run_ripgrep(query, path, glob)
        contexts = []
        seen_ranges = set() # (file_path, start_line, end_line)

        for match in raw_matches:
            file_path = match["path"]["text"]
            line_num = match["line_number"] - 1 # 0-indexed for Tree-sitter

            context = self._expand_context(file_path, line_num)

            if context:
                dedup_key = (context.file_path, context.start_line, context.end_line)
                if dedup_key not in seen_ranges:
                    contexts.append(context)
                    seen_ranges.add(dedup_key)

        return contexts

def main():
    parser = argparse.ArgumentParser(description="Hybrid Grep-to-AST Code Search")
    parser.add_argument("query", help="Search query (passed to ripgrep)")
    parser.add_argument("path", nargs="?", default=".", help="Root directory to search")
    parser.add_argument("--glob", help="Glob pattern for filtering files (e.g. '*.py')")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")

    args = parser.parse_args()

    retriever = HybridRetriever()
    results = retriever.search(args.query, args.path, args.glob)

    if args.json:
        output = []
        for res in results:
            output.append({
                "file": res.file_path,
                "name": res.name,
                "type": res.node_type,
                "start_line": res.start_line,
                "end_line": res.end_line,
                "source": res.source
            })
        print(json.dumps(output, indent=2))
    else:
        if not results:
            print("No structural matches found.")
            return

        print(f"Found {len(results)} matches for '{args.query}':\n")
        for res in results:
            print(f"### {res.file_path} matches `{args.query}`")
            print(f"**{res.node_type}**: `{res.name}` (Lines {res.start_line}-{res.end_line})")
            print(f"```{res.language}")
            print(res.source)
            print("```\n")

if __name__ == "__main__":
    main()
