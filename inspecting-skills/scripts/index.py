"""
index.py - Extract callable symbols from Python files using AST parsing.

Uses Python's stdlib ast module for reliable parsing. Tree-sitter is available
via mapping-codebases for multi-language support, but stdlib ast is preferred
for Python-only indexing due to zero external dependencies.
"""

import ast
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from .discover import SkillLayout, discover_all_skills, skill_name_to_module


@dataclass
class Symbol:
    """A callable symbol (function, class, method) in a module."""
    name: str
    kind: str                          # "function" | "class" | "method" | "variable"
    signature: Optional[str] = None    # e.g., "(self, x: int, y: str = 'default')"
    line: Optional[int] = None         # 1-indexed line number
    docstring: Optional[str] = None    # First line of docstring
    children: list["Symbol"] = field(default_factory=list)  # Methods for classes


@dataclass
class ModuleIndex:
    """Index of a single Python module."""
    file_path: str                     # Relative path from skill root
    module_name: str                   # Python import name
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass
class SkillIndex:
    """Complete index of a skill's exportable code."""
    name: str                          # e.g., "browsing-bluesky"
    module_name: str                   # e.g., "browsing_bluesky"
    layout_type: str                   # "scripts" | "root" | "package" | "none"
    modules: list[ModuleIndex] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)  # From __all__ if present


def get_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract function signature as a string."""
    args = node.args
    parts = []

    # Positional-only args (Python 3.8+)
    for arg in args.posonlyargs:
        parts.append(format_arg(arg))
    if args.posonlyargs:
        parts.append("/")

    # Regular args
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        default_idx = i - defaults_offset
        if default_idx >= 0:
            parts.append(format_arg(arg, args.defaults[default_idx]))
        else:
            parts.append(format_arg(arg))

    # *args
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        parts.append("*")

    # Keyword-only args
    for i, arg in enumerate(args.kwonlyargs):
        default = args.kw_defaults[i]
        parts.append(format_arg(arg, default))

    # **kwargs
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    return f"({', '.join(parts)})"


def format_arg(arg: ast.arg, default: Optional[ast.expr] = None) -> str:
    """Format a single function argument."""
    name = arg.arg

    # Add type annotation if present
    if arg.annotation:
        name += f": {ast.unparse(arg.annotation)}"

    # Add default value if present
    if default is not None:
        try:
            default_str = ast.unparse(default)
            # Truncate long defaults
            if len(default_str) > 20:
                default_str = default_str[:17] + "..."
            name += f" = {default_str}"
        except:
            name += " = ..."

    return name


def get_docstring_first_line(node: ast.AST) -> Optional[str]:
    """Extract first line of docstring if present."""
    docstring = ast.get_docstring(node)
    if docstring:
        first_line = docstring.split("\n")[0].strip()
        if len(first_line) > 80:
            first_line = first_line[:77] + "..."
        return first_line
    return None


def extract_symbols(source: str, module_name: str) -> ModuleIndex:
    """
    Extract all exportable symbols from Python source code.

    Args:
        source: Python source code
        module_name: Name of the module (for import reference)

    Returns:
        ModuleIndex with symbols and imports
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return ModuleIndex(
            file_path="",
            module_name=module_name,
            symbols=[],
            imports=[]
        )

    symbols = []
    imports = []
    exports = []  # From __all__

    for node in ast.walk(tree):
        # Collect imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    # Only process top-level definitions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private functions
            if node.name.startswith("_"):
                continue
            symbols.append(Symbol(
                name=node.name,
                kind="function",
                signature=get_signature(node),
                line=node.lineno,
                docstring=get_docstring_first_line(node)
            ))

        elif isinstance(node, ast.ClassDef):
            # Skip private classes
            if node.name.startswith("_"):
                continue

            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Include public methods
                    if not item.name.startswith("_") or item.name in ("__init__", "__call__"):
                        methods.append(Symbol(
                            name=item.name,
                            kind="method",
                            signature=get_signature(item),
                            line=item.lineno,
                            docstring=get_docstring_first_line(item)
                        ))

            symbols.append(Symbol(
                name=node.name,
                kind="class",
                line=node.lineno,
                docstring=get_docstring_first_line(node),
                children=methods
            ))

        # Look for __all__ definition
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                exports.append(elt.value)

    index = ModuleIndex(
        file_path="",
        module_name=module_name,
        symbols=symbols,
        imports=imports
    )

    return index


def index_skill(layout: SkillLayout) -> SkillIndex:
    """
    Create a complete index of a skill's exportable code.

    Args:
        layout: SkillLayout from discover module

    Returns:
        SkillIndex with all modules and symbols
    """
    modules = []
    skill_exports = []

    # Check for __init__.py exports
    init_path = layout.path / "__init__.py"
    if init_path.exists():
        source = init_path.read_text()
        init_index = extract_symbols(source, layout.entry_module or layout.name)
        init_index.file_path = "__init__.py"

        # Extract __all__ from __init__.py
        try:
            tree = ast.parse(source)
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        skill_exports.append(elt.value)
        except:
            pass

    # Index all Python files
    for py_file in layout.python_files:
        try:
            source = py_file.read_text()
            relative_path = py_file.relative_to(layout.path)

            # Determine module name
            if py_file.parent.name == "scripts":
                module_name = f"{skill_name_to_module(layout.name)}.scripts.{py_file.stem}"
            else:
                module_name = f"{skill_name_to_module(layout.name)}.{py_file.stem}"

            index = extract_symbols(source, module_name)
            index.file_path = str(relative_path)
            modules.append(index)
        except Exception as e:
            # Skip files that can't be read/parsed
            continue

    return SkillIndex(
        name=layout.name,
        module_name=skill_name_to_module(layout.name),
        layout_type=layout.layout_type,
        modules=modules,
        exports=skill_exports
    )


def index_all_skills(skills_root: Path) -> dict[str, SkillIndex]:
    """
    Index all skills in a repository.

    Args:
        skills_root: Root directory containing skill directories

    Returns:
        Dict mapping skill names to their SkillIndex
    """
    layouts = discover_all_skills(skills_root)
    return {layout.name: index_skill(layout) for layout in layouts}


def generate_registry(skills_root: Path, output_path: Optional[Path] = None) -> dict:
    """
    Generate a registry.json file mapping skill names to their exports.

    Args:
        skills_root: Root directory containing skill directories
        output_path: Optional path to write registry.json

    Returns:
        Registry dict suitable for JSON serialization
    """
    indices = index_all_skills(skills_root)

    registry = {
        "version": "1.0.0",
        "skills_root": str(skills_root),
        "skills": {}
    }

    for name, index in indices.items():
        skill_entry = {
            "module_name": index.module_name,
            "layout_type": index.layout_type,
            "exports": index.exports,
            "modules": []
        }

        for module in index.modules:
            module_entry = {
                "file": module.file_path,
                "module": module.module_name,
                "symbols": []
            }

            for symbol in module.symbols:
                symbol_entry = {
                    "name": symbol.name,
                    "kind": symbol.kind,
                    "line": symbol.line
                }
                if symbol.signature:
                    symbol_entry["signature"] = symbol.signature
                if symbol.docstring:
                    symbol_entry["doc"] = symbol.docstring
                if symbol.children:
                    symbol_entry["methods"] = [
                        {"name": m.name, "signature": m.signature, "line": m.line}
                        for m in symbol.children
                    ]
                module_entry["symbols"].append(symbol_entry)

            skill_entry["modules"].append(module_entry)

        registry["skills"][name] = skill_entry

    if output_path:
        output_path.write_text(json.dumps(registry, indent=2))

    return registry
