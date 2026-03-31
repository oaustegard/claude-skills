"""Tests for tree-sitting engine.

Run: python -m pytest tests/test_engine.py -v
Or:  python tests/test_engine.py  (standalone)
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Bootstrap parsers before importing engine
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

# If running in proxied environment, bootstrap from bundled parsers
_parsers_dir = Path(__file__).parent.parent / 'parsers'
if _parsers_dir.is_dir():
    try:
        from tree_sitter_language_pack import get_parser as _test, cache_dir
        _test('python')
    except Exception:
        cache_libs = Path(cache_dir())
        cache_libs.mkdir(parents=True, exist_ok=True)
        for so in _parsers_dir.glob('*.so'):
            dest = cache_libs / so.name
            if not dest.exists():
                shutil.copy2(so, dest)

from engine import (
    Symbol, CodeCache, extract_symbols, extract_imports,
    _get_parser, _extract_via_tags, EXTRACTORS, TAGS_SCM,
    _extract_python, _extract_c, _extract_go, _extract_rust,
    _extract_typescript, _extract_ruby, _extract_markdown,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def parse_and_extract(lang: str, code: bytes, relpath: str = 'test') -> list[Symbol]:
    parser = _get_parser(lang)
    assert parser is not None, f"Parser for {lang} not available"
    tree = parser.parse(code)
    return extract_symbols(tree, code, relpath, lang)


def names(symbols: list[Symbol]) -> list[str]:
    return [s.name for s in symbols]


def find(symbols: list[Symbol], name: str) -> Symbol:
    for s in symbols:
        if s.name == name:
            return s
        for c in s.children:
            if c.name == name:
                return c
    raise AssertionError(f"Symbol {name!r} not found in {names(symbols)}")


class AssertionError(AssertionError if False else AssertionError):
    pass


# ── Bootstrap ────────────────────────────────────────────────────────────

def test_parser_available():
    """Parsers for bundled languages are available."""
    for lang in ('python', 'javascript', 'go', 'rust', 'ruby', 'java', 'c', 'markdown'):
        parser = _get_parser(lang)
        assert parser is not None, f"Parser for {lang} should be available"


def test_parser_unavailable_graceful():
    """Unknown language returns None, not an exception."""
    parser = _get_parser('nonexistent_lang_xyz')
    assert parser is None


# ── Extraction routing ───────────────────────────────────────────────────

def test_routing_custom():
    """Languages with custom extractors use them."""
    for lang in ('python', 'c', 'go', 'rust', 'javascript', 'typescript', 'tsx', 'ruby', 'markdown'):
        assert lang in EXTRACTORS, f"{lang} should have a custom extractor"


def test_routing_tags_scm():
    """Languages without custom extractors but with tags.scm use those."""
    for lang in ('java', 'cpp', 'c_sharp'):
        assert lang not in EXTRACTORS, f"{lang} should NOT have a custom extractor"
        assert lang in TAGS_SCM, f"{lang} should have tags.scm"


def test_routing_fallback():
    """Languages with neither use generic extractor (returns something)."""
    code = b'function hello() {}\nclass Foo {}'
    # Lua uses generic — just verify no crash
    parser = _get_parser('lua')
    if parser:
        tree = parser.parse(b'function hello() end')
        syms = extract_symbols(tree, b'function hello() end', 'test.lua', 'lua')
        # Generic may or may not find symbols, but shouldn't crash
        assert isinstance(syms, list)


# ── Python extractor ────────────────────────────────────────────────────

def test_python_functions():
    syms = parse_and_extract('python', b'''
def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

def _private():
    pass
''')
    assert 'hello' in names(syms)
    hello = find(syms, 'hello')
    assert hello.kind == 'function'
    assert hello.signature == '(name: str)'
    assert hello.doc == 'Greet someone.'


def test_python_class_hierarchy():
    syms = parse_and_extract('python', b'''
class UserService:
    """Handles users."""
    def find(self, user_id: int) -> dict:
        """Find a user."""
        return {}
    def _internal(self):
        pass
''')
    svc = find(syms, 'UserService')
    assert svc.kind == 'class'
    assert svc.doc == 'Handles users.'
    method_names = [c.name for c in svc.children]
    assert 'find' in method_names
    assert '_internal' in method_names
    find_method = next(c for c in svc.children if c.name == 'find')
    assert find_method.signature == '(self, user_id: int)'
    assert find_method.doc == 'Find a user.'


# ── C extractor ──────────────────────────────────────────────────────────

def test_c_functions():
    syms = parse_and_extract('c', b'''
int add(int a, int b) {
    return a + b;
}
static void internal() {}
''')
    assert 'add' in names(syms)
    add = find(syms, 'add')
    assert add.kind == 'function'
    assert 'int' in add.signature
    # Static functions should be excluded
    assert 'internal' not in names(syms)


def test_c_structs():
    syms = parse_and_extract('c', b'''
typedef struct {
    int x, y;
} Point;

enum Color { RED, GREEN, BLUE };
''')
    assert 'Point' in names(syms)
    assert 'Color' in names(syms)


# ── Go extractor ─────────────────────────────────────────────────────────

def test_go_functions_and_types():
    syms = parse_and_extract('go', b'''package main

// Config holds settings.
type Config struct {
    Name string
}

// NewConfig creates a Config.
func NewConfig(name string) *Config {
    return &Config{Name: name}
}
''')
    assert 'Config' in names(syms)
    config = find(syms, 'Config')
    assert config.kind == 'struct'
    assert config.doc == 'Config holds settings.'

    nc = find(syms, 'NewConfig')
    assert nc.kind == 'function'
    assert '(name string)' in nc.signature
    assert nc.doc == 'NewConfig creates a Config.'


def test_go_receiver_methods():
    syms = parse_and_extract('go', b'''package main

type Server struct{}

func (s *Server) Start() error { return nil }
func (s *Server) Stop() {}
''')
    server = find(syms, 'Server')
    child_names = [c.name for c in server.children]
    assert 'Start' in child_names
    assert 'Stop' in child_names


# ── Rust extractor ───────────────────────────────────────────────────────

def test_rust_pub_items():
    syms = parse_and_extract('rust', b'''
pub struct Config { pub name: String }
pub enum Status { Active, Inactive }
pub trait Serializable { fn serialize(&self) -> String; }
pub fn create() -> Config { Config { name: String::new() } }
fn private_fn() {}
''')
    assert 'Config' in names(syms)
    assert 'Status' in names(syms)
    assert 'Serializable' in names(syms)
    assert 'create' in names(syms)
    assert 'private_fn' not in names(syms)

    create = find(syms, 'create')
    assert '-> Config' in create.signature


def test_rust_trait_impl_methods():
    """Trait impl methods don't require pub."""
    syms = parse_and_extract('rust', b'''
pub trait Runnable { fn run(&self); }
pub struct Engine {}
impl Runnable for Engine {
    fn run(&self) {}
}
impl Engine {
    pub fn new() -> Engine { Engine {} }
    fn private_helper(&self) {}
}
''')
    engine = find(syms, 'Engine')
    child_names = [c.name for c in engine.children]
    assert 'run' in child_names, "Trait impl method should be included"
    assert 'new' in child_names, "pub inherent method should be included"
    assert 'private_helper' not in child_names, "Private inherent method should be excluded"


# ── TypeScript/JavaScript extractor ──────────────────────────────────────

def test_js_classes_and_functions():
    syms = parse_and_extract('javascript', b'''
/** App controller. */
class App {
    /** Initialize. */
    init(config) { this.ready = true; }
}

function createApp(name) { return new App(); }

const shutdown = async () => {};
''')
    app = find(syms, 'App')
    assert app.kind == 'class'
    assert app.doc == 'App controller.'
    assert any(c.name == 'init' for c in app.children)

    create = find(syms, 'createApp')
    assert create.kind == 'function'
    assert create.signature == '(name)'

    sd = find(syms, 'shutdown')
    assert sd.kind == 'function'


def test_ts_interfaces_and_signatures():
    syms = parse_and_extract('typescript', b'''
interface Config { name: string; }
function create(name: string): Config { return { name }; }
const process = (items: string[]): number => items.length;
''')
    assert 'Config' in names(syms)
    config = find(syms, 'Config')
    assert config.kind == 'interface'

    create = find(syms, 'create')
    assert '(name: string)' in create.signature
    assert 'Config' in create.signature  # return type


# ── Ruby extractor ───────────────────────────────────────────────────────

def test_ruby_module_hierarchy():
    syms = parse_and_extract('ruby', b'''
module Auth
  class User
    def find(email)
    end
    def self.all
    end
  end
  class Admin < User
    def permissions
    end
  end
end
''')
    auth = find(syms, 'Auth')
    assert auth.kind == 'module'
    child_names = [c.name for c in auth.children]
    assert 'User' in child_names
    assert 'Admin' in child_names

    user = next(c for c in auth.children if c.name == 'User')
    method_names = [m.name for m in user.children]
    assert 'find' in method_names
    assert 'self.all' in method_names


def test_ruby_method_signatures():
    syms = parse_and_extract('ruby', b'''
def process(data, format: :json)
end
''')
    proc = find(syms, 'process')
    assert proc.signature is not None
    assert 'data' in proc.signature


# ── Markdown extractor ───────────────────────────────────────────────────

def test_markdown_heading_hierarchy():
    syms = parse_and_extract('markdown', b'''# Title

## Chapter 1

### Section 1.1

### Section 1.2

## Chapter 2

### Section 2.1
''')
    assert len(syms) == 1  # one h1
    title = syms[0]
    assert title.name == 'Title'
    assert title.kind == 'h1'
    assert len(title.children) == 2  # two h2s
    ch1 = title.children[0]
    assert ch1.name == 'Chapter 1'
    assert len(ch1.children) == 2  # two h3s
    assert ch1.children[0].name == 'Section 1.1'


# ── tags.scm extractor ──────────────────────────────────────────────────

def test_tags_scm_java():
    """Java uses tags.scm (no custom extractor)."""
    syms = parse_and_extract('java', b'''
public class UserService {
    public User find(int id) { return null; }
}
public interface Repository {
    User find(int id);
}
''')
    assert 'UserService' in names(syms)
    assert 'Repository' in names(syms)
    svc = find(syms, 'UserService')
    assert svc.kind == 'class'
    repo = find(syms, 'Repository')
    assert repo.kind == 'interface'


# ── CodeCache ────────────────────────────────────────────────────────────

def test_cache_scan():
    """scan() parses files and builds index."""
    tmpdir = tempfile.mkdtemp()
    try:
        Path(tmpdir, 'main.py').write_text('def hello(): pass\ndef world(): pass\n')
        Path(tmpdir, 'README.md').write_text('# Hello\n## World\n')

        cache = CodeCache()
        stats = cache.scan(tmpdir)
        assert stats['files'] == 2
        assert stats['symbols'] >= 3  # 2 python + at least 1 markdown
        assert stats['errors'] == 0
        assert 'python' in stats['languages']
        assert 'markdown' in stats['languages']
    finally:
        shutil.rmtree(tmpdir)


def test_cache_find_symbol():
    """find_symbol() works across files."""
    tmpdir = tempfile.mkdtemp()
    try:
        Path(tmpdir, 'a.py').write_text('def create_user(): pass\n')
        Path(tmpdir, 'b.py').write_text('def create_order(): pass\n')

        cache = CodeCache()
        cache.scan(tmpdir)
        results = cache.find_symbol('create*')
        result_names = [s.name for s in results]
        assert 'create_user' in result_names
        assert 'create_order' in result_names
    finally:
        shutil.rmtree(tmpdir)


def test_cache_file_symbols():
    """file_symbols() returns symbols for a specific file."""
    tmpdir = tempfile.mkdtemp()
    try:
        Path(tmpdir, 'lib.py').write_text('class Foo:\n    def bar(self): pass\n')

        cache = CodeCache()
        cache.scan(tmpdir)
        syms = cache.file_symbols('lib.py')
        assert len(syms) == 1
        assert syms[0].name == 'Foo'
        assert any(c.name == 'bar' for c in syms[0].children)
    finally:
        shutil.rmtree(tmpdir)


def test_cache_get_source_range():
    """get_source_range() returns correct lines."""
    tmpdir = tempfile.mkdtemp()
    try:
        Path(tmpdir, 'code.py').write_text('line1\nline2\nline3\nline4\n')
        cache = CodeCache()
        cache.scan(tmpdir)
        src = cache.get_source_range('code.py', 2, 3)
        assert 'line2' in src
        assert 'line3' in src
        assert 'line1' not in src
    finally:
        shutil.rmtree(tmpdir)


def test_cache_references():
    """references() finds text occurrences across files."""
    tmpdir = tempfile.mkdtemp()
    try:
        Path(tmpdir, 'a.py').write_text('class Config: pass\n')
        Path(tmpdir, 'b.py').write_text('def make():\n    c = Config()\n    return c\n')

        cache = CodeCache()
        cache.scan(tmpdir)
        refs = cache.references('Config')
        files = [r['file'] for r in refs]
        assert 'a.py' in files
        assert 'b.py' in files
    finally:
        shutil.rmtree(tmpdir)


def test_cache_imports():
    """Import extraction works for Python."""
    tmpdir = tempfile.mkdtemp()
    try:
        Path(tmpdir, 'app.py').write_text('import os\nfrom pathlib import Path\n')
        cache = CodeCache()
        cache.scan(tmpdir)
        imps = cache.file_imports('app.py')
        assert 'os' in imps
        assert 'pathlib' in imps
    finally:
        shutil.rmtree(tmpdir)


def test_cache_tree_overview():
    """tree_overview() produces a readable summary."""
    tmpdir = tempfile.mkdtemp()
    try:
        sub = Path(tmpdir, 'src')
        sub.mkdir()
        Path(sub, 'main.py').write_text('def main(): pass\n')
        Path(tmpdir, 'README.md').write_text('# Hello\n')

        cache = CodeCache()
        cache.scan(tmpdir)
        overview = cache.tree_overview()
        assert 'src/' in overview
        assert 'files' in overview.lower()
    finally:
        shutil.rmtree(tmpdir)


def test_cache_skip_dirs():
    """scan() skips node_modules and similar."""
    tmpdir = tempfile.mkdtemp()
    try:
        nm = Path(tmpdir, 'node_modules', 'pkg')
        nm.mkdir(parents=True)
        Path(nm, 'index.js').write_text('function internal() {}\n')
        Path(tmpdir, 'app.js').write_text('function main() {}\n')

        cache = CodeCache()
        stats = cache.scan(tmpdir)
        assert stats['files'] == 1  # only app.js, not node_modules
    finally:
        shutil.rmtree(tmpdir)


# ── Standalone runner ────────────────────────────────────────────────────

if __name__ == '__main__':
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  ✓ {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
