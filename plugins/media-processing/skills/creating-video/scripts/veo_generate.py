#!/usr/bin/env python3
"""
veo_generate.py — generate video clips with Google Veo via the Cloudflare AI Gateway.

Encodes the hard-won facts (all diagnosed 2026-07-18):
  - Model strings are NOT stable. ENUMERATE, never hardcode: --list.
  - Auth is CF AI Gateway BYOK (proxy.env); the Google key lives inside the
    gateway, so both the generate call AND the file download route through it.
  - Veo is predictLongRunning: fire -> poll operation -> download file URI.
  - personGeneration:"allow_adult" -> HTTP 400 (unsupported). Omit it.
  - ~5 concurrent operations max; the 6th returns 429. Fire in waves, refill
    slots as ops complete.
  - The egress proxy 503s on cold start; retry with backoff.
  - bash_tool has a ~50s wall-clock ceiling. Veo takes 1-3 min/clip. RUN THIS
    SCRIPT DETACHED (setsid ... &) and adaptive-wait on its DONE sentinel;
    do not block a single bash call on generation.

Usage:
  python3 veo_generate.py --list                       # enumerate video models
  python3 veo_generate.py prompts.json --out veo/ \
      [--model veo-3.1-fast-generate-preview] \
      [--aspect 16:9] [--negative "large paper, on-screen text"] \
      [--max-concurrent 5]

prompts.json: {"1": "prompt text", "2": "prompt text", ...}
Writes veo/scene_<n>.mp4 for each, plus veo/DONE and veo/results.json on finish.
"""
import os, sys, json, time, argparse
from pathlib import Path

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests --break-system-packages -q")
    import requests

BASE = "https://gateway.ai.cloudflare.com/v1"
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
    """HTTP with backoff on proxy 503 / 429 / non-JSON cold-start noise."""
    delay = 0.5
    for i in range(tries):
        try:
            r = requests.request(method, url, headers=hdr, timeout=kw.pop("timeout", 120), **kw)
            if r.status_code >= 500 or r.status_code == 429:
                raise RuntimeError(f"HTTP {r.status_code}: {(r.text or '')[:120]}")
            return r
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(delay); delay *= 2


def list_video_models():
    g, hdr = gateway()
    r = _req("GET", f"{g}/models?pageSize=1000", hdr)
    out = []
    for m in r.json().get("models", []):
        name = m.get("name", "")
        methods = m.get("supportedGenerationMethods", [])
        if "predictLongRunning" in methods or any(t in name.lower() for t in ("veo", "video")):
            out.append((name, ",".join(methods)))
    return out


def _fire(g, hdr, model, prompt, aspect, negative):
    body = {"instances": [{"prompt": prompt}], "parameters": {"aspectRatio": aspect}}
    if negative:
        body["parameters"]["negativePrompt"] = negative
    # NOTE: do NOT add personGeneration:"allow_adult" -> 400.
    r = _req("POST", f"{g}/models/{model}:predictLongRunning", hdr, json=body, timeout=90)
    if r.status_code == 200:
        return r.json().get("name")
    if r.status_code == 429:
        return "__RATELIMIT__"
    raise RuntimeError(f"fire failed {r.status_code}: {r.text[:160]}")


def _poll(g, hdr, op):
    return _req("GET", f"{g}/{op}", hdr, timeout=60).json()


def _download(g, hdr, uri, path):
    fid = "files/" + uri.split("/files/")[1].split(":")[0]
    r = _req("GET", f"{g}/{fid}:download?alt=media", hdr, timeout=180)
    if r.status_code == 200 and len(r.content) > 1000:
        Path(path).write_bytes(r.content)
        return True
    return False


def generate(prompts, out_dir, model=None, aspect="16:9", negative=None,
             max_concurrent=5, poll_interval=12, budget_s=780, log=print):
    """
    prompts: dict {scene_id: prompt}. Fires with a concurrency cap, refilling
    slots as ops finish, polling until all done or budget exhausted.
    Returns {scene_id: path|None}.
    """
    g, hdr = gateway()
    if not model:
        vids = [n for n, _ in list_video_models()]
        model = next((n.split("/")[-1] for n in vids if "fast" in n),
                     vids[0].split("/")[-1] if vids else None)
        if not model:
            raise SystemExit("No video model available on this key.")
        log(f"model: {model}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    pending = list(prompts.items())          # not yet fired
    live = {}                                # scene_id -> op
    done = {}                                # scene_id -> path|None
    deadline = time.time() + budget_s
    while (pending or live) and time.time() < deadline:
        # refill concurrency slots
        while pending and len(live) < max_concurrent:
            sid, prompt = pending[0]
            op = _fire(g, hdr, model, prompt, aspect, negative)
            if op == "__RATELIMIT__":
                break                         # slots full at provider; wait
            pending.pop(0)
            live[sid] = op
            log(f"fired {sid} -> {op}")
        # poll live ops
        for sid in list(live):
            try:
                d = _poll(g, hdr, live[sid])
            except Exception as e:
                log(f"poll {sid} err {e}"); continue
            if d.get("done"):
                try:
                    uri = d["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
                    path = f"{out_dir}/scene_{sid}.mp4"
                    done[sid] = path if _download(g, hdr, uri, path) else None
                    log(f"{sid} {'DONE '+path if done[sid] else 'DOWNLOAD FAILED'}")
                except Exception as e:
                    done[sid] = None
                    log(f"{sid} done but no video: {json.dumps(d)[:160]} ({e})")
                del live[sid]
        if pending or live:
            time.sleep(poll_interval)

    for sid, _ in prompts.items():
        done.setdefault(sid, None)
    Path(out_dir, "results.json").write_text(json.dumps(done, indent=2))
    Path(out_dir, "DONE").write_text("ok")
    return done


def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompts", nargs="?", help="JSON file: {scene_id: prompt}")
    ap.add_argument("--out", default="veo")
    ap.add_argument("--model", default=None)
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--negative", default=None)
    ap.add_argument("--max-concurrent", type=int, default=5)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for n, m in list_video_models():
            print(f"{n}  |  {m}")
        return
    if not a.prompts:
        ap.error("provide a prompts JSON file or --list")
    prompts = json.loads(Path(a.prompts).read_text())
    logf = open(Path(a.out) / "generate.log", "a") if Path(a.out).exists() or True else None
    Path(a.out).mkdir(parents=True, exist_ok=True)
    logf = open(Path(a.out) / "generate.log", "a")

    def log(m):
        print(m); logf.write(str(m) + "\n"); logf.flush()

    res = generate(prompts, a.out, model=a.model, aspect=a.aspect,
                   negative=a.negative, max_concurrent=a.max_concurrent, log=log)
    log(f"FINISHED: {sorted(k for k,v in res.items() if v)} "
        f"(failed: {sorted(k for k,v in res.items() if not v)})")


if __name__ == "__main__":
    _main()
