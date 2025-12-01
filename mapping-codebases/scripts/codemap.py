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
    '.html': 'html',
}

# Default directories to skip
DEFAULT_SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next'}

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
                    for subchild in child.children:
                        if subchild.type == 'identifier':
                            exports.append(get_text(subchild))
                            break
                elif child.type == 'class_declaration':
                    for subchild in child.children:
                        if subchild.type == 'type_identifier':
                            exports.append(get_text(subchild))
                            break
                elif child.type == 'lexical_declaration':
                    for subchild in child.children:
                        if subchild.type == 'variable_declarator':
                            for id_node in subchild.children:
                                if id_node.type == 'identifier':
                                    exports.append(get_text(id_node))
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
                    text = get_text(child).strip('"')
                    imports.append(text)
        
        # Exports (capitalized top-level)
        elif node.type in ('function_declaration', 'type_declaration'):
            for child in node.children:
                if child.type == 'identifier':
                    name = get_text(child)
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
    
    def visit(node):
        # Use statements
        if node.type == 'use_declaration':
            for child in node.children:
                if child.type in ('scoped_identifier', 'identifier'):
                    imports.append(get_text(child))
        
        # Public items
        elif node.type == 'attribute_item':
            is_pub = False
            for child in node.children:
                if child.type == 'visibility_modifier' and get_text(child) == 'pub':
                    is_pub = True
            if is_pub:
                for child in node.children:
                    if child.type in ('function_item', 'struct_item', 'enum_item', 'trait_item'):
                        for subchild in child.children:
                            if subchild.type in ('identifier', 'type_identifier'):
                                exports.append(get_text(subchild))
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
        if node.type == 'call' and any(
            child.type == 'identifier' and get_text(child) == 'require' 
            for child in node.children
        ):
            for child in node.children:
                if child.type == 'argument_list':
                    for arg in child.children:
                        if arg.type == 'string':
                            text = get_text(arg).strip('"\'')
                            imports.append(text)
        
        # Top-level definitions
        elif node.type in ('method', 'class', 'module'):
            for child in node.children:
                if child.type in ('identifier', 'constant'):
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
    
    def visit(node):
        # Imports
        if node.type == 'import_declaration':
            for child in node.children:
                if child.type == 'scoped_identifier':
                    imports.append(get_text(child))
        
        # Public classes/interfaces
        elif node.type in ('class_declaration', 'interface_declaration'):
            is_public = False
            for child in node.children:
                if child.type == 'modifiers':
                    mod_text = get_text(child)
                    if 'public' in mod_text:
                        is_public = True
            if is_public:
                for child in node.children:
                    if child.type == 'identifier':
                        exports.append(get_text(child))
                        break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", exports=exports, imports=imports)


def extract_html_javascript(tree, source: bytes) -> FileInfo:
    """Extract JavaScript functions and imports from HTML <script> tags."""
    functions = []
    imports = []

    def get_text(node):
        return source[node.start_byte:node.end_byte].decode()

    def find_script_elements(node):
        """Recursively find all script elements in HTML."""
        script_contents = []

        if node.type == 'script_element':
            # Check if this is an inline script (not src-only)
            has_src = False
            for child in node.children:
                if child.type == 'start_tag':
                    tag_text = get_text(child)
                    if 'src=' in tag_text:
                        has_src = True
                        # Extract the src value for imports
                        try:
                            import_match = tag_text.split('src=')[1].split()[0].strip('"\'>')
                            if import_match and not import_match.startswith('http'):
                                imports.append(import_match)
                        except:
                            pass
                elif child.type == 'raw_text':
                    # This is inline JavaScript code
                    js_code = get_text(child)
                    if js_code.strip():
                        script_contents.append(js_code)

        for child in node.children:
            script_contents.extend(find_script_elements(child))

        return script_contents

    # Extract all script contents
    script_contents = find_script_elements(tree.root_node)

    # Parse each script block as JavaScript
    if script_contents:
        try:
            js_parser = get_parser('javascript')
            for script_code in script_contents:
                js_tree = js_parser.parse(script_code.encode())

                # Extract function declarations
                def visit_js(node):
                    js_source = script_code.encode()
                    node_text = js_source[node.start_byte:node.end_byte].decode()

                    # Function declarations: function foo() {}
                    if node.type == 'function_declaration':
                        for child in node.children:
                            if child.type == 'identifier':
                                func_name = js_source[child.start_byte:child.end_byte].decode()
                                if func_name not in functions:
                                    functions.append(func_name)
                                break

                    # Variable declarations with functions: const foo = function() {}
                    # Also arrow functions: const foo = () => {}
                    elif node.type == 'variable_declarator':
                        identifier = None
                        is_function = False
                        for child in node.children:
                            if child.type == 'identifier':
                                identifier = js_source[child.start_byte:child.end_byte].decode()
                            elif child.type in ('function', 'arrow_function', 'function_expression'):
                                is_function = True
                        if identifier and is_function and identifier not in functions:
                            functions.append(identifier)

                    # Import statements
                    elif node.type == 'import_statement':
                        for child in node.children:
                            if child.type == 'string':
                                import_path = js_source[child.start_byte:child.end_byte].decode().strip('"\'')
                                if import_path not in imports:
                                    imports.append(import_path)

                    for child in node.children:
                        visit_js(child)

                visit_js(js_tree.root_node)
        except Exception:
            # If JavaScript parsing fails, silently continue
            pass

    return FileInfo(name="", exports=functions, imports=imports)


EXTRACTORS = {
    'python': extract_python,
    'javascript': extract_typescript,
    'typescript': extract_typescript,
    'tsx': extract_typescript,
    'go': extract_go,
    'rust': extract_rust,
    'ruby': extract_ruby,
    'java': extract_java,
    'html': extract_html_javascript,
}


def analyze_file(filepath: Path) -> FileInfo | None:
    """Analyze a single file and return its info."""
    lang = get_language(filepath)
    if not lang:
        return None
    
    try:
        parser = get_parser(lang)
        source = filepath.read_bytes()
        tree = parser.parse(source)
        
        extractor = EXTRACTORS.get(lang)
        if not extractor:
            return None
        
        info = extractor(tree, source)
        info.name = filepath.name
        return info
    except Exception:
        return None


def generate_map_for_directory(dirpath: Path, skip_dirs: set[str]) -> str | None:
    """Generate _MAP.md content for a single directory."""
    files_info = []
    subdirs = []
    
    for entry in sorted(dirpath.iterdir()):
        if entry.name.startswith('.') or entry.name == '_MAP.md':
            continue
        if entry.is_dir():
            if entry.name not in skip_dirs:
                subdirs.append(entry.name)
        elif entry.is_file():
            info = analyze_file(entry)
            if info:
                files_info.append(info)
    
    if not files_info and not subdirs:
        return None
    
    # Header with stats
    lines = [f"# {dirpath.name}/"]
    
    # Add summary stats
    stats = []
    if files_info:
        stats.append(f"Files: {len(files_info)}")
    if subdirs:
        stats.append(f"Subdirectories: {len(subdirs)}")
    if stats:
        lines.append(f"*{' | '.join(stats)}*\n")
    else:
        lines.append("")
    
    if subdirs:
        lines.append("## Subdirectories\n")
        for d in subdirs:
            lines.append(f"- [{d}/](./{d}/_MAP.md)")
        lines.append("")
    
    if files_info:
        lines.append("## Files\n")
        for info in files_info:
            parts = [f"**{info.name}**"]
            
            # Show export count if truncated
            if info.exports:
                export_preview = ', '.join(info.exports[:8])
                if len(info.exports) > 8:
                    parts.append(f"exports ({len(info.exports)}): `{export_preview}`...")
                else:
                    parts.append(f"exports: `{export_preview}`")
            
            # Show import count if truncated
            if info.imports:
                # Shorten imports for readability
                short_imports = [i.split('/')[-1] for i in info.imports[:5]]
                import_preview = ', '.join(short_imports)
                if len(info.imports) > 5:
                    parts.append(f"imports ({len(info.imports)}): `{import_preview}`...")
                else:
                    parts.append(f"imports: `{import_preview}`")
            
            lines.append(f"- {' — '.join(parts)}")
    
    return '\n'.join(lines) + '\n'


def generate_maps(root: Path, skip_dirs: set[str], dry_run: bool = False):
    """Walk directory tree and generate _MAP.md files."""
    count = 0
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith('.')]
        
        path = Path(dirpath)
        content = generate_map_for_directory(path, skip_dirs)
        
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
    parser.add_argument('--skip', help='Comma-separated list of additional directories to skip (e.g., "locale,migrations,tests")')
    args = parser.parse_args()
    
    root = Path(args.path).resolve()
    
    # Build skip set
    skip_dirs = DEFAULT_SKIP_DIRS.copy()
    if args.skip:
        skip_dirs.update(s.strip() for s in args.skip.split(','))
    
    if args.clean:
        count = 0
        for map_file in root.rglob('_MAP.md'):
            if not any(skip in map_file.parts for skip in skip_dirs):
                map_file.unlink()
                print(f"Removed: {map_file}")
                count += 1
        print(f"Cleaned {count} _MAP.md files")
        return
    
    count = generate_maps(root, skip_dirs, dry_run=args.dry_run)
    print(f"\nGenerated {count} _MAP.md files")


if __name__ == '__main__':
    main()
