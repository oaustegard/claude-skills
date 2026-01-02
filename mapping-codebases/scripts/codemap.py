#!/usr/bin/env python3
"""
codemap.py - Generate _MAP.md files for each directory in a codebase.
Extracts exports/imports via tree-sitter. No LLM, deterministic, fast.
Updated to support symbol hierarchy (Classes -> Methods) and Kinds.
Requires Python 3.10+ and tree-sitter-language-pack.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from tree_sitter_language_pack import get_parser

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
class Symbol:
    name: str
    kind: str  # 'class', 'function', 'method', 'variable', 'interface'
    signature: str | None = None
    children: list['Symbol'] = field(default_factory=list)

@dataclass
class FileInfo:
    name: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def get_language(filepath: Path) -> str | None:
    return EXT_TO_LANG.get(filepath.suffix.lower())

def get_node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode()

def extract_python(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Python AST."""
    symbols = []
    imports = []
    
    def get_signature(node) -> str | None:
        for child in node.children:
            if child.type == 'parameters':
                return get_node_text(child, source)
        return None

    def visit_class_body(node) -> list[Symbol]:
        members = []
        for child in node.children:
             if child.type == 'block':
                 for subchild in child.children:
                    if subchild.type == 'function_definition':
                        members.append(process_function(subchild, kind='method'))
        return members

    def process_function(node, kind='function') -> Symbol:
        name = ""
        for child in node.children:
            if child.type == 'identifier':
                name = get_node_text(child, source)
                break

        signature = get_signature(node)
        return Symbol(name=name, kind=kind, signature=signature)

    def process_class(node) -> Symbol:
        name = ""
        for child in node.children:
            if child.type == 'identifier':
                name = get_node_text(child, source)
                break

        children = visit_class_body(node)
        return Symbol(name=name, kind='class', children=children)

    def visit(node):
        # Imports
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'dotted_name':
                    imports.append(get_node_text(child, source))
        elif node.type == 'import_from_statement':
            module = None
            for child in node.children:
                if child.type == 'dotted_name':
                    module = get_node_text(child, source)
                    break
                elif child.type == 'relative_import':
                    module = get_node_text(child, source)
                    break
            if module:
                imports.append(module)
        
        # Top-level definitions
        elif node.type == 'function_definition':
            sym = process_function(node)
            if not sym.name.startswith('_'):
                symbols.append(sym)
        
        elif node.type == 'class_definition':
            sym = process_class(node)
            if not sym.name.startswith('_'):
                symbols.append(sym)

        # Recurse only if module (don't recurse into functions/classes in the main loop)
        if node.type == 'module':
            for child in node.children:
                visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", symbols=symbols, imports=imports)


def extract_typescript(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from TypeScript/JavaScript AST."""
    symbols = []
    imports = []
    
    def get_signature(node) -> str | None:
        for child in node.children:
            if child.type in ('formal_parameters', 'type_parameters'):
                 # We might want to combine type params and formal params
                 return get_node_text(child, source)
        return None

    def process_method(node) -> Symbol:
        name = ""
        for child in node.children:
            if child.type in ('property_identifier', 'method_definition'):
                 name = get_node_text(child, source)
                 break
        return Symbol(name=name, kind='method') # Signature extraction is harder in TS due to complexity

    def process_class_body(node) -> list[Symbol]:
        members = []
        for child in node.children:
            if child.type == 'class_body':
                for subchild in child.children:
                    if subchild.type == 'method_definition':
                        # extract name
                        name = ""
                        for part in subchild.children:
                            if part.type == 'property_identifier':
                                name = get_node_text(part, source)
                                break
                        if name:
                            members.append(Symbol(name=name, kind='method'))
        return members

    def visit(node):
        # Import declarations
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'string':
                    text = get_node_text(child, source).strip('"\'')
                    imports.append(text)
        
        # Export declarations
        elif node.type == 'export_statement':
            for child in node.children:
                if child.type == 'function_declaration':
                    name = ""
                    for subchild in child.children:
                        if subchild.type == 'identifier':
                            name = get_node_text(subchild, source)
                            break
                    if name:
                        symbols.append(Symbol(name=name, kind='function'))

                elif child.type == 'class_declaration':
                    name = ""
                    for subchild in child.children:
                        if subchild.type == 'type_identifier':
                            name = get_node_text(subchild, source)
                            break
                    if name:
                        members = process_class_body(child)
                        symbols.append(Symbol(name=name, kind='class', children=members))

        # TODO: Handle non-exported top-level items if desired, or `export default`
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", symbols=symbols, imports=imports)


def extract_go(tree, source: bytes) -> FileInfo:
    symbols = []
    imports = []
    
    def visit(node):
        if node.type == 'import_spec':
            for child in node.children:
                if child.type == 'interpreted_string_literal':
                    imports.append(get_node_text(child, source).strip('"'))
        elif node.type in ('function_declaration', 'type_declaration'):
            for child in node.children:
                if child.type == 'identifier':
                    name = get_node_text(child, source)
                    if name[0].isupper():
                        symbols.append(Symbol(name=name, kind='func' if node.type == 'function_declaration' else 'type'))
                    break
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", symbols=symbols, imports=imports)


def extract_rust(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Rust AST."""
    symbols = []
    imports = []
    
    def visit(node):
        # Use statements
        if node.type == 'use_declaration':
            for child in node.children:
                if child.type in ('scoped_identifier', 'identifier'):
                    imports.append(get_node_text(child, source))
        
        # Public items
        elif node.type in ('function_item', 'struct_item', 'enum_item', 'trait_item'):
             # Check for public visibility in parent attribute item if needed,
             # but tree-sitter structure for rust can be: attribute_item -> visibility_modifier
             # or direct if it's top level.
             # Wait, the previous logic handled `attribute_item` which wrapped the declaration.
             # But sometimes `pub fn` is directly a `function_item` with a `visibility_modifier` child.

             is_pub = False
             for child in node.children:
                 if child.type == 'visibility_modifier' and get_node_text(child, source) == 'pub':
                     is_pub = True

             if is_pub:
                 name = ""
                 for child in node.children:
                     if child.type in ('identifier', 'type_identifier'):
                         name = get_node_text(child, source)
                         break
                 if name:
                    kind = node.type.replace('_item', '')
                    symbols.append(Symbol(name=name, kind=kind))

        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", symbols=symbols, imports=imports)


def extract_ruby(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Ruby AST."""
    symbols = []
    imports = []
    
    def visit(node):
        # Requires
        if node.type == 'call' and any(
            child.type == 'identifier' and get_node_text(child, source) == 'require'
            for child in node.children
        ):
            for child in node.children:
                if child.type == 'argument_list':
                    for arg in child.children:
                        if arg.type == 'string':
                            text = get_node_text(arg, source).strip('"\'')
                            imports.append(text)
        
        # Top-level definitions
        elif node.type in ('method', 'class', 'module'):
            for child in node.children:
                if child.type in ('identifier', 'constant'):
                    name = get_node_text(child, source)
                    symbols.append(Symbol(name=name, kind=node.type))
                    break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", symbols=symbols, imports=imports)


def extract_java(tree, source: bytes) -> FileInfo:
    """Extract exports and imports from Java AST."""
    symbols = []
    imports = []
    
    def visit(node):
        # Imports
        if node.type == 'import_declaration':
            for child in node.children:
                if child.type == 'scoped_identifier':
                    imports.append(get_node_text(child, source))
        
        # Public classes/interfaces
        elif node.type in ('class_declaration', 'interface_declaration'):
            is_public = False
            for child in node.children:
                if child.type == 'modifiers':
                    mod_text = get_node_text(child, source)
                    if 'public' in mod_text:
                        is_public = True
            if is_public:
                for child in node.children:
                    if child.type == 'identifier':
                        name = get_node_text(child, source)
                        kind = node.type.replace('_declaration', '')
                        symbols.append(Symbol(name=name, kind=kind))
                        break
        
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return FileInfo(name="", symbols=symbols, imports=imports)


def extract_html_javascript(tree, source: bytes) -> FileInfo:
    """Extract JavaScript functions and imports from HTML <script> tags."""
    symbols = []
    imports = []

    def find_script_elements(node):
        """Recursively find all script elements in HTML."""
        script_contents = []

        if node.type == 'script_element':
            # Check if this is an inline script (not src-only)
            has_src = False
            for child in node.children:
                if child.type == 'start_tag':
                    tag_text = get_node_text(child, source)
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
                    js_code = get_node_text(child, source)
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
                    # Helper since we have different source here
                    def get_js_text(n):
                        return js_source[n.start_byte:n.end_byte].decode()

                    # Function declarations: function foo() {}
                    if node.type == 'function_declaration':
                        for child in node.children:
                            if child.type == 'identifier':
                                func_name = get_js_text(child)
                                symbols.append(Symbol(name=func_name, kind='function'))
                                break

                    # Variable declarations with functions: const foo = function() {}
                    # Also arrow functions: const foo = () => {}
                    elif node.type == 'variable_declarator':
                        identifier = None
                        is_function = False
                        for child in node.children:
                            if child.type == 'identifier':
                                identifier = get_js_text(child)
                            elif child.type in ('function', 'arrow_function', 'function_expression'):
                                is_function = True
                        if identifier and is_function:
                             symbols.append(Symbol(name=identifier, kind='function'))

                    # Import statements
                    elif node.type == 'import_statement':
                        for child in node.children:
                            if child.type == 'string':
                                import_path = get_js_text(child).strip('"\'')
                                if import_path not in imports:
                                    imports.append(import_path)

                    for child in node.children:
                        visit_js(child)

                visit_js(js_tree.root_node)
        except Exception:
            # If JavaScript parsing fails, silently continue
            pass

    return FileInfo(name="", symbols=symbols, imports=imports)


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
    except Exception as e:
        # print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return None


def format_symbol(symbol: Symbol, indent: int = 0) -> list[str]:
    lines = []
    prefix = "  " * indent

    kind_marker = ""
    if symbol.kind == 'class': kind_marker = "(C)"
    elif symbol.kind == 'method': kind_marker = "(m)"
    elif symbol.kind == 'function': kind_marker = "(f)"
    else: kind_marker = f"({symbol.kind})"

    sig = f"`{symbol.signature}`" if symbol.signature else ""

    lines.append(f"{prefix}- **{symbol.name}** {kind_marker} {sig}")

    for child in symbol.children:
        lines.extend(format_symbol(child, indent + 1))

    return lines

def generate_map_for_directory(dirpath: Path, skip_dirs: set[str]) -> str | None:
    """Generate _MAP.md content for a single directory."""
    files_info = []
    subdirs = []
    
    # print(f"Processing directory: {dirpath}", file=sys.stderr)

    for entry in sorted(dirpath.iterdir()):
        if entry.name.startswith('.') or entry.name == '_MAP.md':
            continue
        if entry.is_dir():
            if entry.name not in skip_dirs:
                subdirs.append(entry.name)
        elif entry.is_file():
            # print(f"  Analyzing file: {entry}", file=sys.stderr)
            info = analyze_file(entry)
            if info:
                # print(f"    Found info for {entry.name}: {len(info.symbols)} symbols", file=sys.stderr)
                files_info.append(info)
            else:
                # print(f"    No info for {entry.name}", file=sys.stderr)
                pass
    
    if not files_info and not subdirs:
        # print("    No content for map.", file=sys.stderr)
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
            lines.append(f"### {info.name}")
            
            # Imports
            if info.imports:
                short_imports = [i.split('/')[-1] for i in info.imports[:5]]
                import_preview = ', '.join(short_imports)
                if len(info.imports) > 5:
                    lines.append(f"> Imports: `{import_preview}`...")
                else:
                    lines.append(f"> Imports: `{import_preview}`")

            # Symbols
            if info.symbols:
                for sym in info.symbols:
                    lines.extend(format_symbol(sym))
            else:
                lines.append("- *No top-level symbols*")
            
            lines.append("") # Spacer
    
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
