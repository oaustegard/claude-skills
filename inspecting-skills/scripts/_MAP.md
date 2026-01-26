# scripts/
*Files: 4*

## Files

### __init__.py
> Imports: `.discover, .index, .skill_imports`
- *No top-level symbols*

### discover.py
> Imports: `pathlib, dataclasses, typing`
- **discover_skill** (f) `(skill_path: Path)` :26
- **discover_all_skills** (f) `(
    skills_root: Path,
    exclude: Optional[set[str]] = None
)` :93
- **skill_name_to_module** (f) `(skill_name: str)` :126
- **module_to_skill_name** (f) `(module_name: str)` :137
- **find_skill_by_name** (f) `(
    name: str,
    skills_root: Path
)` :151

### index.py
> Imports: `ast, json, pathlib, dataclasses, typing`...
- **get_signature** (f) `(node: ast.FunctionDef | ast.AsyncFunctionDef)` :48
- **format_arg** (f) `(arg: ast.arg, default: Optional[ast.expr] = None)` :86
- **get_docstring_first_line** (f) `(node: ast.AST)` :108
- **extract_symbols** (f) `(source: str, module_name: str)` :119
- **index_skill** (f) `(layout: SkillLayout)` :212
- **index_all_skills** (f) `(skills_root: Path)` :274
- **generate_registry** (f) `(skills_root: Path, output_path: Optional[Path] = None)` :288

### skill_imports.py
> Imports: `sys, os, importlib, importlib.abc, importlib.util`...
- **get_skills_root** (f) `()` :38
- **set_skills_root** (f) `(path: Union[str, Path])` :44
- **setup_skill_path** (f) `(skills_root: Union[str, Path, None] = None)` :55
- **skill_import** (f) `(
    skill_name: str,
    symbols: Optional[list[str]] = None
)` :110
- **register_skill** (f) `(skill_name: str, skill_path: Union[str, Path])` :187
- **SkillImportFinder** (C) :202
  - **find_spec** (m) `(self, fullname: str, path, target=None)` :210
  - **_create_spec** (m) `(self, fullname: str, skill_path: Path, parts: list[str])` :232
- **list_importable_skills** (f) `()` :280

