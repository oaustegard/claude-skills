#!/usr/bin/env python3
"""composing-html / build.py — CLI entry.

Usage
-----
  build.py list                                     # all templates, one line each
  build.py describe <template>                      # parameter reference for one template
  build.py build <template> [--spec FILE|-] [--set K=V ...] [--out FILE]
                                                    # render HTML; spec from FILE, stdin,
                                                    # and/or --set overrides

The "build" command reads a JSON spec, runs it through the named template's
builder, and emits a single self-contained HTML document. With no --out, the
result is written to stdout.

--set lets you supply or override a spec field from the command line, including
loading the value from a file via the @PATH suffix:

  build.py build freeform --set title='My Page' --set body_html=@body.html --out out.html

This sidesteps JSON-string escaping for multi-line HTML/CSS/JS bodies.

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


def _apply_set(spec: dict, set_args: list[str]) -> int:
    """Mutate spec from --set KEY=VALUE / KEY=@FILE entries.

    Escape hatch for fields whose content fights JSON-string escaping
    (multi-line HTML, CSS, JS). Lets the caller keep the spec lean and
    point at raw files for the heavy bits.

    Syntax:
      --set body_html=@body.html        # spec['body_html'] = file contents
      --set title='My Page'             # spec['title']     = 'My Page'

    Returns 0 on success, 2 on error.
    """
    for entry in set_args or []:
        if "=" not in entry:
            print(f"--set expects KEY=VALUE or KEY=@FILE, got: {entry!r}", file=sys.stderr)
            return 2
        key, _, val = entry.partition("=")
        key = key.strip()
        if not key:
            print(f"--set missing key in: {entry!r}", file=sys.stderr)
            return 2
        if val.startswith("@"):
            path = val[1:]
            if not path:
                print(f"--set {key}=@ requires a file path", file=sys.stderr)
                return 2
            try:
                spec[key] = Path(path).read_text(encoding="utf-8")
            except OSError as e:
                print(f"--set {key}=@{path}: {e}", file=sys.stderr)
                return 2
        else:
            spec[key] = val
    return 0


def cmd_build(args) -> int:
    name = args.template
    if name not in REGISTRY:
        print(f"unknown template: {name}", file=sys.stderr)
        return 2

    # Spec is optional when every required field can be supplied via --set.
    if args.spec == "-":
        raw_text = sys.stdin.read()
    elif args.spec:
        raw_text = Path(args.spec).read_text(encoding="utf-8")
    else:
        raw_text = ""

    if raw_text.strip():
        try:
            spec = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"spec is not valid JSON: {e}", file=sys.stderr)
            return 2
        if not isinstance(spec, dict):
            print("spec must be a JSON object (dict)", file=sys.stderr)
            return 2
    else:
        spec = {}

    rc = _apply_set(spec, args.set or [])
    if rc != 0:
        return rc

    if not spec:
        print("empty spec (no --spec content and no --set entries)", file=sys.stderr)
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
    pb.add_argument("--spec", "-s", default=None,
                    help="Path to JSON spec, or '-' for stdin. Optional if every "
                         "required field is supplied via --set.")
    pb.add_argument("--set", action="append", default=[],
                    metavar="KEY=VALUE",
                    help="Set or override a spec field. 'KEY=VALUE' assigns the "
                         "literal string; 'KEY=@FILE' loads the file contents. "
                         "Repeatable. Avoids JSON-string escaping for multi-line "
                         "HTML/CSS/JS (e.g. --set body_html=@body.html).")
    pb.add_argument("--out", "-o", default=None, help="Write HTML to this file (default: stdout).")
    pb.set_defaults(fn=cmd_build)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
