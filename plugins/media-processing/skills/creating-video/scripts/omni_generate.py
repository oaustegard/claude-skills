#!/usr/bin/env python3
"""
omni_generate.py — generate video clips with Gemini Omni Flash via the
Cloudflare AI Gateway (Interactions API).

Facts this script encodes (verified 2026-07-20):
  - Endpoint: POST {gateway}/google-ai-studio/v1beta/interactions — the CF AI
    Gateway BYOK path proxies it; both the call and file downloads route
    through the gateway.
  - Model: gemini-omni-flash-preview (preview; re-check the docs when it 404s).
  - The call is SYNCHRONOUS — no operation polling. A clip takes ~30s-3min of
    held-open HTTP. bash_tool caps at ~50s, so RUN THIS SCRIPT DETACHED
    (setsid ... &) and adaptive-wait on the DONE sentinel.
  - THERE IS NO DRY RUN. Even input:"" returns 200 and bills a full
    generation (~58k video output tokens). Every request costs money.
  - No negativePrompt parameter (unsupported, unlike Veo). Fold negatives
    into the prompt text: "Do not include: X".
  - Videos >4MB need response_format delivery:"uri" -> poll files/{id} until
    ACTIVE -> download via {gateway}/.../files/{id}:download?alt=media.
    This script always uses uri delivery; inline base64 is the fallback.
  - Stateful editing: pass previous_interaction_id + an instruction to edit a
    prior generation in place. results.json stores each scene's interaction
    id for exactly this purpose (requires store=true, the default).
  - Reference images go inline in the input list; bind roles in the prompt
    with <FIRST_FRAME> / <IMAGE_REF_N> tags (refs start at 0).
  - Egress proxy 503s on cold start; retry with backoff.

Usage:
  python3 omni_generate.py prompts.json --out omni/ \
      [--model gemini-omni-flash-preview] [--aspect 16:9] \
      [--negative "on-screen text, watermark"] [--max-concurrent 3]
  python3 omni_generate.py --edit <interaction_id> "Make the hat red. Keep everything else the same." --out omni/scene_2_v2.mp4

prompts.json: {"1": "prompt text", ...} or
              {"1": {"text": "...", "images": ["ref0.png", "first.png"]}, ...}
Writes <out>/scene_<n>.mp4 per scene, plus <out>/results.json
({scene: {path, interaction_id}}) and <out>/DONE.
"""
import os, sys, json, time, base64, argparse, mimetypes
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests --break-system-packages -q")
    import requests

BASE = "https://gateway.ai.cloudflare.com/v1"
DEFAULT_MODEL = "gemini-omni-flash-preview"
_PROXY_PATHS = [Path("/mnt/project/proxy.env"), Path("proxy.env"),
                Path.home() / "proxy.env"]


def gateway():
    """Load CF AI Gateway creds and return (base_url, headers)."""
    creds = {}
    for p in _PROXY_PATHS:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    creds[k.strip()] = v.strip().strip('"').strip("'")
            break
    for k in ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN"):
        creds.setdefault(k, os.environ.get(k, ""))
    missing = [k for k in ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN") if not creds.get(k)]
    if missing:
        raise SystemExit(f"Missing gateway creds: {missing}. Provide proxy.env.")
    g = f"{BASE}/{creds['CF_ACCOUNT_ID']}/{creds['CF_GATEWAY_ID']}/google-ai-studio/v1beta"
    hdr = {"Content-Type": "application/json",
           "cf-aig-authorization": f"Bearer {creds['CF_API_TOKEN']}"}
    return g, hdr


def _req(method, url, hdr, tries=4, **kw):
    """HTTP with backoff on proxy 503 / 429 / cold-start noise."""
    delay = 1.0
    for i in range(tries):
        try:
            r = requests.request(method, url, headers=hdr, timeout=kw.pop("timeout", 300), **kw)
            if r.status_code >= 500 or r.status_code == 429:
                raise RuntimeError(f"HTTP {r.status_code}: {(r.text or '')[:120]}")
            return r
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(delay); delay *= 2


def _build_input(spec, negative):
    """spec: str or {"text":..., "images":[paths]}. Returns Interactions input."""
    if isinstance(spec, str):
        text, images = spec, []
    else:
        text, images = spec["text"], spec.get("images", [])
    if negative:
        text = f"{text} Do not include: {negative}."
    if not images:
        return text
    parts = []
    for p in images:
        mime = mimetypes.guess_type(p)[0] or "image/png"
        parts.append({"type": "image", "mime_type": mime,
                      "data": base64.b64encode(Path(p).read_bytes()).decode()})
    parts.append({"type": "text", "text": text})
    return parts


def _extract_video(j):
    """Return (uri, b64_data) from a completed interaction JSON (either may be None)."""
    ov = j.get("output_video") or {}
    uri, data = ov.get("uri"), ov.get("data")
    if not (uri or data):
        for step in j.get("steps", []):
            if step.get("type") == "model_output":
                for c in step.get("content", []):
                    if c.get("type") == "video":
                        uri, data = c.get("uri"), c.get("data")
    return uri, data


def _download_uri(g, hdr, uri, path, log, poll_interval=5, budget_s=300):
    """Poll files/{id} until ACTIVE, then download via the gateway."""
    fid = uri.split("/files/")[1].split(":")[0].split("?")[0]
    deadline = time.time() + budget_s
    while time.time() < deadline:
        st = _req("GET", f"{g}/files/{fid}", hdr, timeout=30).json().get("state", "")
        if st == "ACTIVE":
            break
        if st == "FAILED":
            log(f"file {fid} FAILED"); return False
        time.sleep(poll_interval)
    r = _req("GET", f"{g}/files/{fid}:download?alt=media", hdr, timeout=300)
    if r.status_code == 200 and len(r.content) > 1000:
        Path(path).write_bytes(r.content)
        return True
    return False


def _generate_one(g, hdr, model, sid, spec, aspect, negative, out_dir, log,
                  previous_id=None):
    body = {"model": model,
            "input": spec if previous_id else _build_input(spec, negative),
            "response_format": {"type": "video", "aspect_ratio": aspect,
                                "delivery": "uri"}}
    if previous_id:
        body["previous_interaction_id"] = previous_id
    r = _req("POST", f"{g}/interactions", hdr, json=body, timeout=600)
    if r.status_code != 200:
        log(f"{sid} failed {r.status_code}: {r.text[:160]}")
        return sid, None, None
    j = r.json()
    iid = j.get("id")
    uri, data = _extract_video(j)
    path = str(Path(out_dir) / f"scene_{sid}.mp4")
    ok = False
    if uri:
        ok = _download_uri(g, hdr, uri, path, log)
    if not ok and data:
        Path(path).write_bytes(base64.b64decode(data)); ok = True
    log(f"{sid} {'DONE ' + path if ok else 'NO VIDEO'} (interaction {iid})")
    return sid, path if ok else None, iid


def generate(prompts, out_dir, model=DEFAULT_MODEL, aspect="16:9",
             negative=None, max_concurrent=3, log=print):
    """prompts: {scene_id: str|dict}. Returns {scene_id: {path, interaction_id}}."""
    g, hdr = gateway()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    done = {}
    with ThreadPoolExecutor(max_workers=max_concurrent) as ex:
        futs = {ex.submit(_generate_one, g, hdr, model, sid, spec, aspect,
                          negative, out_dir, log): sid
                for sid, spec in prompts.items()}
        for f in as_completed(futs):
            sid, path, iid = f.result()
            done[sid] = {"path": path, "interaction_id": iid}
    Path(out_dir, "results.json").write_text(json.dumps(done, indent=2))
    Path(out_dir, "DONE").write_text("ok")
    return done


def edit(previous_id, instruction, out_path, model=DEFAULT_MODEL, log=print):
    """One conversational edit turn on a stored interaction."""
    g, hdr = gateway()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sid = Path(out_path).stem
    _, path, iid = _generate_one(g, hdr, model, sid, instruction, "16:9", None,
                                 Path(out_path).parent, log, previous_id=previous_id)
    if path and path != str(out_path):
        Path(path).rename(out_path)
    return str(out_path) if path else None, iid


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompts", nargs="?", help="JSON file: {scene_id: prompt|{text,images}}")
    ap.add_argument("--out", default="omni")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    ap.add_argument("--negative", default=None,
                    help="folded into prompt text; Omni has no negativePrompt param")
    ap.add_argument("--max-concurrent", type=int, default=3)
    ap.add_argument("--edit", nargs=2, metavar=("INTERACTION_ID", "INSTRUCTION"))
    a = ap.parse_args()

    if a.edit:
        pid, instr = a.edit
        out = a.out if a.out.endswith(".mp4") else f"{a.out}/edit.mp4"
        path, iid = edit(pid, instr, out)
        print(f"{'DONE ' + path if path else 'FAILED'} (interaction {iid})")
        return

    if not a.prompts:
        ap.error("provide a prompts JSON file or --edit")
    prompts = json.loads(Path(a.prompts).read_text())
    Path(a.out).mkdir(parents=True, exist_ok=True)
    logf = open(Path(a.out) / "generate.log", "a")

    def log(m):
        print(m); logf.write(str(m) + "\n"); logf.flush()

    res = generate(prompts, a.out, model=a.model, aspect=a.aspect,
                   negative=a.negative, max_concurrent=a.max_concurrent, log=log)
    ok = sorted(k for k, v in res.items() if v["path"])
    log(f"FINISHED: {ok} (failed: {sorted(k for k in res if k not in ok)})")


if __name__ == "__main__":
    _main()
