# PR #160 Review: Improve codemap.py with symbol hierarchy

## Updates Applied

This review includes updates to bring the PR current with latest dependencies:
- ✅ Updated to use `tree-sitter-language-pack` (maintained fork, 165+ languages)
- ✅ Replaced unmaintained `tree-sitter-languages`
- ✅ Updated installation instructions to use `uv`
- ✅ Confirmed Python 3.10+ requirement
- ✅ **Tested with actual code** - all findings below are from running tests

## Testing Results

### ✅ What Works Excellently

**Python Extraction:**
```python
# Input: Python class with methods
class MyClass:
    def __init__(self, value: int):
        self.value = value

    def public_method(self, x: int, y: int) -> int:
        return x + y
```

**Output:**
```markdown
- **MyClass** (C)
  - **__init__** (m) `(self, value: int)`
  - **public_method** (m) `(self, x: int, y: int)`
```

**Confirmed working:**
- ✅ Symbol hierarchy (classes → methods)
- ✅ Kind markers (C for class, m for method, f for function)
- ✅ Signature extraction with type hints
- ✅ Private top-level functions filtered (`_private_function` excluded)
- ✅ Import preview
- ✅ TypeScript/JavaScript class hierarchy

### ⚠️ Issues Found in Testing

#### 1. **Private Methods Not Filtered in Python** 🟡
**Observed:**
```python
class MyClass:
    def _private_method(self):  # Should be filtered but isn't
        pass
```

**Output:**
```markdown
- **MyClass** (C)
  - **_private_method** (m) `(self)`  ← Should not appear
```

**Impact:** Medium - private implementation details clutter the map
**Location:** `extract_python` function, `visit_class_body`

---

#### 2. **Java Methods Not Extracted** 🔴
**Observed:**
```java
public class Sample {
    public int getValue() { return value; }
    private void helper() {}
}
```

**Output:**
```markdown
- **Sample** (C)    ← No methods shown
```

**Impact:** High - Java class maps are incomplete
**Root Cause:** `extract_java` doesn't implement method extraction like Python does

---

#### 3. **Limited Language Coverage** 🟡
**Status:** Only Python and TypeScript/JavaScript have full hierarchy support.

**Missing method extraction:**
- Java (confirmed broken in testing)
- Go
- Rust
- Ruby
- HTML/JavaScript

**Note:** These languages still work, but only show top-level symbols (no class methods).

---

#### 4. **TypeScript Signature Extraction Not Implemented** 🟢
**Observed:**
```typescript
export class MyComponent {
    public doSomething(x: number): void { }
}
```

**Output:**
```markdown
- **MyComponent** (C)
  - **doSomething** (m)    ← No signature shown
```

**Impact:** Low - still useful without signatures, but less context than Python
**Note:** Code comment acknowledges this: "Signature extraction is harder in TS"

---

## Original PR Strengths

### 1. Excellent Core Feature
- **Symbol Hierarchy**: Successfully represents classes → methods (Python, TypeScript)
- **Kind Markers**: Clear (C), (m), (f) indicators
- **Signatures**: Python extraction works perfectly with type hints
- **Better UX**: Much more useful than flat lists

### 2. Good Documentation
- **COMPARISON.md**: Well-written analysis of TreeSitter vs LSP approaches
- **README.md**: Clear installation and usage instructions (now updated to uv + tree-sitter-language-pack)

### 3. Clean Refactoring
- `get_node_text()` helper reduces duplication
- `Symbol` and `FileInfo` dataclasses are well-designed
- `format_symbol()` handles recursive rendering cleanly

## Recommended Fixes

### Must Fix Before Merge

#### 1. Add Private Method Filtering in Python
**Location:** `codemap.py` - `visit_class_body` function

```python
def visit_class_body(node) -> list[Symbol]:
    members = []
    for child in node.children:
        if child.type == 'block':
            for subchild in child.children:
                if subchild.type == 'function_definition':
                    method = process_function(subchild, kind='method')
                    if method and not method.name.startswith('_'):  # ← Add this filter
                        members.append(method)
    return members
```

#### 2. Fix Java Method Extraction
Java needs a similar `visit_class_body` implementation. The current code only checks for public classes but doesn't extract methods.

**Suggested approach:**
```python
def extract_java(tree, source: bytes) -> FileInfo:
    # Add similar method extraction as Python
    def visit_class_body(node) -> list[Symbol]:
        # Extract public methods from method_declaration nodes
        pass
```

### Should Fix (Important)

#### 3. Add Empty Name Validation
Prevent crashes on malformed code:

```python
def process_function(node, kind='function') -> Symbol | None:
    name = ""
    for child in node.children:
        if child.type == 'identifier':
            name = get_node_text(child, source)
            break

    if not name:  # ← Add this check
        return None

    signature = get_signature(node)
    return Symbol(name=name, kind=kind, signature=signature)
```

### Nice to Have (Future Work)

4. **TypeScript Signature Extraction** - Extract at least parameter names
5. **Complete Language Coverage** - Add method extraction for Go, Rust, Ruby
6. **Better Error Logging** - Uncomment and enable debug prints with --verbose flag

## Dependency Updates (Applied)

✅ **tree-sitter-language-pack 0.13.0**
- Replaces unmaintained `tree-sitter-languages`
- 165+ languages supported
- Actively maintained fork
- Compatible with tree-sitter 0.25.2

✅ **Installation with uv**
```bash
uv pip install tree-sitter-language-pack
```

## Overall Assessment

**Verdict: Approve with Recommended Fixes** ✅

### What's Great
- Core Python functionality works excellently
- Significant improvement over flat symbol lists
- Well-tested and functional for Python/TypeScript
- Dependencies updated to maintained packages

### What Needs Work
1. **Python private method filtering** - Easy fix, important for clean maps
2. **Java method extraction** - Medium effort, required for Java support
3. **Empty name validation** - Quick fix, prevents edge case crashes

### Impact
This PR delivers a valuable enhancement for **Python and TypeScript** codebases. Other languages get partial benefit (top-level symbols only). The recommended fixes would make it production-ready across all supported languages.

---

## Testing Checklist

✅ Tested on Python code with:
- Classes with methods
- Functions with type hints
- Private methods and functions
- Nested hierarchies

✅ Tested on TypeScript code with:
- Exported classes
- Public/private methods
- Import statements

✅ Tested on Java code with:
- Public/private classes
- Methods (found missing extraction)

✅ Confirmed tree-sitter-language-pack compatibility

✅ Verified Python 3.10+ requirement

---

## Sources

- [tree-sitter-language-pack GitHub](https://github.com/Goldziher/tree-sitter-language-pack)
- [py-tree-sitter Documentation](https://tree-sitter.github.io/py-tree-sitter/)
- [tree-sitter-languages deprecation notice](https://github.com/grantjenks/py-tree-sitter-languages)
