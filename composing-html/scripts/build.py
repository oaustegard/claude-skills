#!/usr/bin/env python3
"""composing-html / build.py — CLI entry.

Usage
-----
  build.py list                                     # all templates, one line each
  build.py describe <template>                      # parameter reference for one template
  build.py build <template> [--spec FILE|-] [--out FILE]
                                                    # render HTML; spec from FILE or stdin

The "build" command reads a JSON spec, runs it through the named template's
builder, and emits a single self-contained HTML document. With no --out, the
result is written to stdout.

Templates live in scripts/templates/. Each module registers via the @register
decorator. See SKILL.md for the workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from composer import page                              # noqa: E402
from templates import REGISTRY                         # noqa: E402


def cmd_list(_args) -> int:
    width = max(len(name) for name in REGISTRY) if REGISTRY else 0
    print(f"{len(REGISTRY)} templates available:\n")
    for name in sorted(REGISTRY):
        print(f"  {name.ljust(width)}  {REGISTRY[name]['summary']}")
    print("\nNext: build.py describe <template>")
    return 0


def _infer_default(desc: str):
    """Pick a JSON-valid placeholder value from a spec_keys description string.

    Heuristic — looks for shape hints like 'List', 'Dict', 'Bool', 'List[{...}]'.
    The output is always parseable JSON so the printed skeleton can be edited
    in place rather than retyped.
    """
    d = desc.lower()
    if d.startswith("list") or d.startswith("optional list") or "list[" in d:
        import re as _re
        m = _re.search(r"\{([^}]+)\}", desc)
        if m:
            keys = []
            for raw_key in m.group(1).split(","):
                # Each key looks like "name", "pros[]", "status?", "kind?: 'a|b'".
                key = raw_key.strip().rstrip("?").split(":")[0].strip()
                is_list_key = key.endswith("[]")
                key = key.rstrip("[]").strip()
                if not key or not key.isidentifier():
                    continue
                keys.append((key, is_list_key))
            return [{k: ([] if is_l else "") for k, is_l in keys}] if keys else []
        return []
    if d.startswith("dict") or "dict[" in d:
        return {}
    if "bool" in d.split()[:3]:
        return False
    if d.startswith("optional"):
        return None
    return ""


def cmd_describe(args) -> int:
    name = args.template
    if name not in REGISTRY:
        print(f"unknown template: {name}", file=sys.stderr)
        print(f"see: {sys.argv[0]} list", file=sys.stderr)
        return 2
    entry = REGISTRY[name]
    print(f"# {name}\n\n{entry['summary']}\n")
    print("## Spec keys\n")
    for k, desc in entry["spec_keys"].items():
        required = "" if desc.lower().startswith("optional") else "  (required)"
        print(f"- `{k}`{required}: {desc}")
    print("\n## Starter spec (valid JSON — edit and pass to `build`)\n")
    skeleton = {k: _infer_default(desc) for k, desc in entry["spec_keys"].items()}
    print("```json")
    print(json.dumps(skeleton, indent=2, ensure_ascii=False))
    print("```\n")
    print(f"For richer worked examples, see references/templates.md → ## {name}\n")
    print("Build with:\n")
    print(f"  {sys.argv[0]} build {name} --spec spec.json --out out.html")
    return 0


def cmd_build(args) -> int:
    name = args.template
    if name not in REGISTRY:
        print(f"unknown template: {name}", file=sys.stderr)
        return 2

    if args.spec == "-" or not args.spec:
        raw = sys.stdin.read()
    else:
        raw = Path(args.spec).read_text(encoding="utf-8")
    if not raw.strip():
        print("empty spec", file=sys.stderr)
        return 2
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"spec is not valid JSON: {e}", file=sys.stderr)
        return 2

    builder = REGISTRY[name]["build"]
    page_kwargs = builder(spec)
    if not isinstance(page_kwargs, dict):
        print(f"template {name} did not return a dict", file=sys.stderr)
        return 2

    html = page(**page_kwargs)
    if args.out:
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"wrote {args.out} ({len(html):,} bytes)", file=sys.stderr)
    else:
        sys.stdout.write(html)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="build.py", description="Compose HTML artifacts from a small JSON spec.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all available templates.").set_defaults(fn=cmd_list)

    pd = sub.add_parser("describe", help="Show the spec for one template.")
    pd.add_argument("template")
    pd.set_defaults(fn=cmd_describe)

    pb = sub.add_parser("build", help="Render a template using the given spec.")
    pb.add_argument("template")
    pb.add_argument("--spec", "-s", default="-", help="Path to JSON spec, or '-' for stdin (default).")
    pb.add_argument("--out", "-o", default=None, help="Write HTML to this file (default: stdout).")
    pb.set_defaults(fn=cmd_build)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
