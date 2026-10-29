#!/usr/bin/env python3
"""Download Google Fonts woff2 files (latin subset) into public/fonts.

The render browser does not trust this container's egress-proxy CA, so
@remotion/google-fonts fails at render time with ERR_CERT_AUTHORITY_INVALID.
curl does trust it, so fetch the files here and load them with staticFile().

Usage: vendor_fonts.py "Instrument Serif:ital@0;1" "DM Sans:wght@400;700" [--out public/fonts]
Prints the loadFont() calls to paste into the project.
"""
import argparse, re, subprocess, sys, urllib.parse
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("families", nargs="+")
    ap.add_argument("--out", default="public/fonts")
    ap.add_argument("--subset", default="latin")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    seen = {}
    for fam in a.families:
        url = "https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(fam.replace(" ", "+"), safe="+:;@,") + "&display=block"
        css = subprocess.run(["curl", "-sf", "-A", UA, url], capture_output=True, text=True).stdout
        if not css:
            sys.exit(f"no CSS for {fam!r} (check the family spec at fonts.google.com)")
        for sub, block in re.findall(r"/\* (\S+) \*/\s*@font-face \{(.*?)\}", css, re.S):
            if sub != a.subset:
                continue
            name = re.search(r"font-family: '([^']+)'", block).group(1)
            style = re.search(r"font-style: (\w+)", block).group(1)
            weight = re.search(r"font-weight: ([\d ]+);", block).group(1)
            src = re.search(r"url\((\S+?)\)", block).group(1)
            # variable fonts serve one file for every weight; download it once
            if src in seen:
                seen[src][2].append(weight)
                continue
            fn = f"{name.replace(' ', '')}-{style}-{len(seen)}.woff2"
            subprocess.run(["curl", "-sf", "-o", str(out / fn), src], check=True)
            seen[src] = [name, style, [weight], fn]
    print('import { loadFont } from "@remotion/fonts";\nimport { staticFile } from "remotion";')
    for name, style, weights, fn in seen.values():
        ws = sorted({int(w) for ww in weights for w in ww.split()})
        w = str(ws[0]) if len(ws) == 1 else f"{ws[0]} {ws[-1]}"
        print(f'loadFont({{ family: "{name}", url: staticFile("fonts/{fn}"), weight: "{w}", style: "{style}" }});')

if __name__ == "__main__":
    main()
