#!/usr/bin/env python3
"""
extract_cards.py — read every tile produced by prep_cards.py by sending it to
Haiku with the distilled prompt in prompts/haiku_extract.md, parse the JSON each
call returns, dedupe across overlapping tiles, and write one CSV.

This is the cheap path: instead of a large model reading 1,000 tiles in one
conversation, the script fans the tiles out to Haiku (temperature 0) in parallel.
Haiku only has to follow an explicit schema, which the prompt + examples lock in.

Usage:
    python3 scripts/extract_cards.py --work /home/claude/cards_work \
        --out /mnt/user-data/outputs/cards.csv

    --work    the --out dir you gave prep_cards.py (must contain manifest.json)
    --out     CSV path (default /mnt/user-data/outputs/cards.csv)
    --workers parallel API calls (default 6)
    --limit   only process the first N tiles (smoke test)
    --model   model id (default claude-haiku-4-5-20251001)
"""
import argparse, base64, csv, json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://api.anthropic.com/v1/messages"
FIELDS = ["name", "title", "company", "phone", "email", "website", "address", "confidence"]
HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(os.path.dirname(HERE), "prompts", "haiku_extract.md")


def load_api_key():
    key = os.environ.get("API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    # fall back to the project env file
    for p in ("/mnt/project/claude.env", os.path.expanduser("~/claude.env")):
        if os.path.exists(p):
            for line in open(p):
                if line.strip().startswith("API_KEY="):
                    return line.strip().split("=", 1)[1]
    sys.exit("No API key. Set API_KEY env var or provide /mnt/project/claude.env")


def call_haiku(api_key, system_prompt, img_b64, model, max_retries=4):
    body = json.dumps({
        "model": model,
        "max_tokens": 1500,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": "image/png", "data": img_b64}},
            {"type": "text", "text": "Transcribe this tile. Output JSON only."},
        ]}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            return "".join(b.get("text", "") for b in data.get("content", [])
                            if b.get("type") == "text")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def parse_cards(text):
    """Pull the JSON object out of Haiku's reply, tolerating stray fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1:
        raise ValueError("no JSON object in reply")
    obj = json.loads(t[s:e + 1])
    return obj.get("cards", [])


def process_tile(rec, api_key, system_prompt, model):
    with open(rec["tile"], "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    raw = call_haiku(api_key, system_prompt, img_b64, model)
    try:
        cards = parse_cards(raw)
    except Exception:
        # one reparse attempt already covered by structure; on failure flag it
        return [{"sheet": rec["sheet"], "tile": os.path.basename(rec["tile"]),
                 "name": "", "title": "", "company": "", "phone": "", "email": "",
                 "website": "", "address": "", "confidence": "parse-error"}]
    rows = []
    for c in cards:
        row = {"sheet": rec["sheet"], "tile": os.path.basename(rec["tile"])}
        for k in FIELDS:
            row[k] = str(c.get(k, "")).strip()
        rows.append(row)
    return rows


def dedupe(rows):
    """Overlap shows some cards in two tiles. Keep one per (name, company),
    preferring the higher-confidence reading."""
    rank = {"high": 2, "low": 1, "": 0, "parse-error": -1}
    best = {}
    passthrough = []
    for r in rows:
        name, comp = r["name"].lower().strip(), r["company"].lower().strip()
        if not name and not comp:
            passthrough.append(r)          # unkeyed (e.g. parse-error) — keep as-is
            continue
        key = (name, comp)
        if key not in best or rank.get(r["confidence"], 0) > rank.get(best[key]["confidence"], 0):
            best[key] = r
    return list(best.values()) + passthrough


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="prep_cards.py output dir (has manifest.json)")
    ap.add_argument("--out", default="/mnt/user-data/outputs/cards.csv")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = ap.parse_args()

    manifest_path = os.path.join(args.work, "manifest.json")
    if not os.path.exists(manifest_path):
        sys.exit(f"No manifest.json in {args.work} — run prep_cards.py first.")
    tiles = json.load(open(manifest_path))
    if "tile" not in (tiles[0] if tiles else {}):
        sys.exit("manifest has no tiles — run prep_cards.py in (default) tile mode.")
    if args.limit:
        tiles = tiles[:args.limit]

    api_key = load_api_key()
    system_prompt = open(PROMPT_PATH).read()

    all_rows, done, errors = [], 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_tile, t, api_key, system_prompt, args.model): t
                for t in tiles}
        for fut in as_completed(futs):
            try:
                rows = fut.result()
            except Exception as e:
                errors += 1
                print(f"  ! tile failed: {e}", file=sys.stderr)
                rows = []
            all_rows.extend(rows)
            done += 1
            if done % 10 == 0 or done == len(tiles):
                print(f"  {done}/{len(tiles)} tiles, {len(all_rows)} raw cards")

    deduped = dedupe(all_rows)
    deduped.sort(key=lambda r: (r["sheet"], r["company"].lower(), r["name"].lower()))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sheet", "tile"] + FIELDS)
        w.writeheader()
        w.writerows(deduped)

    lows = sum(1 for r in deduped if r["confidence"] == "low")
    perr = sum(1 for r in deduped if r["confidence"] == "parse-error")
    print(f"\n{len(all_rows)} raw -> {len(deduped)} unique cards "
          f"({lows} low-confidence, {perr} parse-errors, {errors} tile errors)")
    print(f"CSV: {args.out}")
    print("Re-read low-confidence cards with a larger model if the rate is high.")


if __name__ == "__main__":
    main()
