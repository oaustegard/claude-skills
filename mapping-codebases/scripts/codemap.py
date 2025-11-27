#!/usr/bin/env python3
"""
codemap.py - Generate _MAP.md files for each directory in a codebase.
Extracts exports/imports via tree-sitter. No LLM, deterministic, fast.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from tree_sitter_languages import get_parser

# Language detection by extension
EXT_TO_LANG = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.jsx': 'javascript',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.java': 'java',
}

# Directories to skip
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next'}

@dataclass
class FileInfo:
    name: str
    exports: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def get_language(filepath: Path) -> str | None:
    return EXT_TO_LANG.get(filepath.suffix.lower())


def extract_python(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Python AST."""
    exports = []
    imports = []
    
    def visit(node):
        # Imports
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'dotted_name':
                    imports.append(source[child.start_byte:child.end_byte].decode())
        elif node.type == 'import_from_statement':
            module = None
            for child in node.children:
                if child.type == 'dotted_name':
                    module = source[child.start_byte:child.end_byte].decode()
                    break
                elif child.type == 'relative_import':
                    module = source[child.start_byte:child.end_byte].decode()
                    break
            if module:
                imports.append(module)
        
        # Exports (top-level definitions)
        elif node.type == 'function_definition' and node.parent.type == 'module':
            for child in node.children:
                if child.type == 'identifier':
                    name = source[child.start_byte:child.end_byte].decode()
                    if not name.startswith('_'):
                        exports.append(name)
                    break
        elif node.type == 'class_definition' and node.parent.type == 'module':
            for child in node.children:
                if child.type == 'identifier':
                    name = source[child.start_byte:child.end_byte].decode()
                    if not name.startswith('_'):
                        exports.append(name)
                    break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", exports=exports, imports=imports)


def extract_typescript(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from TypeScript/JavaScript AST."""
    exports = []
    imports = []
    
    def get_text(node):
        return source[node.start_byte:node.end_byte].decode()
    
    def visit(node):
        # Import declarations
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'string':
                    text = get_text(child).strip('"\'')
                    imports.append(text)
        
        # Export declarations
        elif node.type == 'export_statement':
            for child in node.children:
                if child.type == 'function_declaration':
                    for c in child.children:
                        if c.type == 'identifier':
                            exports.append(get_text(c))
                            break
                elif child.type == 'class_declaration':
                    for c in child.children:
                        if c.type == 'type_identifier':
                            exports.append(get_text(c))
                            break
                elif child.type == 'lexical_declaration':
                    for c in child.children:
                        if c.type == 'variable_declarator':
                            for cc in c.children:
                                if cc.type == 'identifier':
                                    exports.append(get_text(cc))
                                    break
                elif child.type == 'identifier':
                    exports.append(get_text(child))
                elif child.type == 'type_alias_declaration':
                    for c in child.children:
                        if c.type == 'type_identifier':
                            exports.append(get_text(c))
                            break
                elif child.type == 'interface_declaration':
                    for c in child.children:
                        if c.type == 'type_identifier':
                            exports.append(get_text(c))
                            break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", exports=exports, imports=imports)


def extract_go(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Go AST."""
    exports = []
    imports = []
    
    def get_text(node):
        return source[node.start_byte:node.end_byte].decode()
    
    def visit(node):
        # Imports
        if node.type == 'import_spec':
            for child in node.children:
                if child.type == 'interpreted_string_literal':
                    imports.append(get_text(child).strip('"'))
                    break
        
        # Exports (capitalized identifiers at package level)
        elif node.type == 'function_declaration':
            for child in node.children:
                if child.type == 'identifier':
                    name = get_text(child)
                    if name[0].isupper():
                        exports.append(name)
                    break
        elif node.type == 'type_declaration':
            for child in node.children:
                if child.type == 'type_spec':
                    for c in child.children:
                        if c.type == 'type_identifier':
                            name = get_text(c)
                            if name[0].isupper():
                                exports.append(name)
                            break
        elif node.type in ('var_declaration', 'const_declaration'):
            for child in node.children:
                if child.type in ('var_spec', 'const_spec'):
                    for c in child.children:
                        if c.type == 'identifier':
                            name = get_text(c)
                            if name[0].isupper():
                                exports.append(name)
                            break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", exports=exports, imports=imports)


def extract_rust(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Rust AST."""
    exports = []
    imports = []
    
    def get_text(node):
        return source[node.start_byte:node.end_byte].decode()
    
    def is_pub(node):
        for child in node.children:
            if child.type == 'visibility_modifier':
                return True
        return False
    
    def visit(node):
        # Use statements
        if node.type == 'use_declaration':
            text = get_text(node)
            # Extract the path part
            if '::' in text:
                imports.append(text.split('use ')[-1].rstrip(';').split('::')[0])
        
        # Public items
        elif node.type == 'function_item' and is_pub(node):
            for child in node.children:
                if child.type == 'identifier':
                    exports.append(get_text(child))
                    break
        elif node.type == 'struct_item' and is_pub(node):
            for child in node.children:
                if child.type == 'type_identifier':
                    exports.append(get_text(child))
                    break
        elif node.type == 'enum_item' and is_pub(node):
            for child in node.children:
                if child.type == 'type_identifier':
                    exports.append(get_text(child))
                    break
        elif node.type == 'trait_item' and is_pub(node):
            for child in node.children:
                if child.type == 'type_identifier':
                    exports.append(get_text(child))
                    break
        elif node.type == 'impl_item' and is_pub(node):
            for child in node.children:
                if child.type == 'type_identifier':
                    exports.append(get_text(child))
                    break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", exports=exports, imports=imports)


def extract_ruby(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Ruby AST."""
    exports = []
    imports = []
    
    def get_text(node):
        return source[node.start_byte:node.end_byte].decode()
    
    def visit(node):
        # Requires
        if node.type == 'call':
            children = list(node.children)
            if children and children[0].type == 'identifier':
                method = get_text(children[0])
                if method in ('require', 'require_relative'):
                    for child in children:
                        if child.type == 'argument_list':
                            for arg in child.children:
                                if arg.type == 'string':
                                    text = get_text(arg).strip('"\'')
                                    imports.append(text)
        
        # Class and module definitions (top-level)
        elif node.type == 'class' and node.parent.type == 'program':
            for child in node.children:
                if child.type == 'constant':
                    exports.append(get_text(child))
                    break
        elif node.type == 'module' and node.parent.type == 'program':
            for child in node.children:
                if child.type == 'constant':
                    exports.append(get_text(child))
                    break
        # Top-level methods
        elif node.type == 'method' and node.parent.type == 'program':
            for child in node.children:
                if child.type == 'identifier':
                    exports.append(get_text(child))
                    break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", exports=exports, imports=imports)


def extract_java(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Java AST."""
    exports = []
    imports = []
    
    def get_text(node):
        return source[node.start_byte:node.end_byte].decode()
    
    def is_public(node):
        for child in node.children:
            if child.type == 'modifiers':
                modifiers_text = get_text(child)
                return 'public' in modifiers_text
        return False
    
    def visit(node):
        # Import declarations
        if node.type == 'import_declaration':
            for child in node.children:
                if child.type == 'scoped_identifier':
                    imports.append(get_text(child))
                    break
        
        # Public class/interface/enum
        elif node.type == 'class_declaration' and is_public(node):
            for child in node.children:
                if child.type == 'identifier':
                    exports.append(get_text(child))
                    break
        elif node.type == 'interface_declaration' and is_public(node):
            for child in node.children:
                if child.type == 'identifier':
                    exports.append(get_text(child))
                    break
        elif node.type == 'enum_declaration' and is_public(node):
            for child in node.children:
                if child.type == 'identifier':
                    exports.append(get_text(child))
                    break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", exports=exports, imports=imports)


EXTRACTORS = {
    'python': extract_python,
    'javascript': extract_typescript,
    'typescript': extract_typescript,
    'tsx': extract_typescript,
    'go': extract_go,
    'rust': extract_rust,
    'ruby': extract_ruby,
    'java': extract_java,
}


def analyze_file(filepath: Path) -> FileInfo | None:
    """Analyze a single file and return its info."""
    lang = get_language(filepath)
    if not lang or lang not in EXTRACTORS:
        return None
    
    try:
        parser = get_parser(lang)
        source = filepath.read_bytes()
        tree = parser.parse(source)
        info = EXTRACTORS[lang](tree, source)
        info.name = filepath.name
        return info
    except Exception as e:
        print(f"Warning: Failed to parse {filepath}: {e}", file=sys.stderr)
        return None


def generate_map_for_directory(dirpath: Path) -> str | None:
    """Generate _MAP.md content for a single directory."""
    files_info = []
    subdirs = []
    
    for entry in sorted(dirpath.iterdir()):
        if entry.name.startswith('.') or entry.name == '_MAP.md':
            continue
        if entry.is_dir():
            if entry.name not in SKIP_DIRS:
                subdirs.append(entry.name)
        elif entry.is_file():
            info = analyze_file(entry)
            if info:
                files_info.append(info)
    
    if not files_info and not subdirs:
        return None
    
    lines = [f"# {dirpath.name}/\n"]
    
    if subdirs:
        lines.append("## Subdirectories\n")
        for d in subdirs:
            lines.append(f"- [{d}/](./{d}/_MAP.md)")
        lines.append("")
    
    if files_info:
        lines.append("## Files\n")
        for info in files_info:
            parts = [f"**{info.name}**"]
            if info.exports:
                parts.append(f"exports: `{', '.join(info.exports[:8])}`{'...' if len(info.exports) > 8 else ''}")
            if info.imports:
                # Shorten imports for readability
                short_imports = [i.split('/')[-1] for i in info.imports[:5]]
                parts.append(f"imports: `{', '.join(short_imports)}`{'...' if len(info.imports) > 5 else ''}")
            lines.append(f"- {' — '.join(parts)}")
    
    return '\n'.join(lines) + '\n'


def generate_maps(root: Path, dry_run: bool = False):
    """Walk directory tree and generate _MAP.md files."""
    count = 0
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
        
        path = Path(dirpath)
        content = generate_map_for_directory(path)
        
        if content:
            map_path = path / '_MAP.md'
            if dry_run:
                print(f"Would write: {map_path}")
                print(content)
                print("---")
            else:
                map_path.write_text(content)
                print(f"Wrote: {map_path}")
            count += 1
    
    return count


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate _MAP.md files for codebase navigation')
    parser.add_argument('path', nargs='?', default='.', help='Root directory to process')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Print output without writing files')
    parser.add_argument('--clean', action='store_true', help='Remove all _MAP.md files')
    args = parser.parse_args()
    
    root = Path(args.path).resolve()
    
    if args.clean:
        count = 0
        for map_file in root.rglob('_MAP.md'):
            if not any(skip in map_file.parts for skip in SKIP_DIRS):
                map_file.unlink()
                print(f"Removed: {map_file}")
                count += 1
        print(f"Cleaned {count} _MAP.md files")
        return
    
    count = generate_maps(root, dry_run=args.dry_run)
    print(f"\nGenerated {count} _MAP.md files")


if __name__ == '__main__':
    main()
