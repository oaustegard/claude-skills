---
name: capturing-browser-logs
description: Gets runtime evidence from a web page the agent cannot run itself, using Agent Log (austegard.com/web-utilities/agent-log.html), a script that records console calls, errors, fetch/XHR traffic and the events and DOM changes of elements the user picks, as OpenTelemetry logs in the user's browser. Use when debugging a page, web app, browser game or bookmarklet that misbehaves on the user's device, when the user says "it doesn't work" about a page and you need to see what happened, when you want to add console.log instrumentation and read it back, when you need to see what happens on a specific button, field or element, or when the user hands you an OTLP JSON log export or a file named agent-log-*.json.
metadata:
  version: 0.2.0
---

# Capturing browser logs

The user runs the page; you read what it did. Agent Log records the page's console output, uncaught errors, unhandled rejections, failed resource loads, CSP violations and fetch/XHR calls into the browser's IndexedDB, shows a red **Logging** badge while it records, and exports an OTLP/JSON file the user hands back to you. Nothing is uploaded.

Docs, bookmarklet and console snippet: https://austegard.com/web-utilities/agent-log.html

## Applicability

Use it when the bug happens in a real browser that you do not control: the user's phone, a GPU-specific failure, a page behind their login, timing that a headless run does not reproduce. If you can run the page yourself in Playwright or a browser tool, do that instead and read the console directly. Agent Log does not see iframes, web workers or service workers, and it does not record request or response bodies.

## Procedure

1. **Pick how the user turns it on.** Give them exactly one route:
   - A page whose source you can edit: add `<script src="https://austegard.com/web-utilities/agent-log.js"></script>` to its `<head>`, ship it, and ask the user to open the page with `?logging=true` (or `&logging=true` when the URL already has a query). Logging stays on in that tab across reloads until they press **Stop logging**. For a page that should always log, use `<script src="…" data-start></script>`.
   - Any other page: ask the user to drag the bookmarklet from the docs page to their bookmarks bar, open the page and click it.
   - A page with a strict Content Security Policy (GitHub, many banks and mail clients): the bookmarklet silently fails there. Ask the user to press **Copy the full script** on the docs page and paste it into the page's devtools console.
   - `raw.githubusercontent.com` cannot serve the script to a `<script>` tag (it sends `text/plain` with `nosniff`). Use the austegard.com URL, or jsDelivr: `https://cdn.jsdelivr.net/gh/oaustegard/oaustegard.github.io@main/web-utilities/agent-log.js`.

2. **Instrument with structured console calls** where the existing output will not answer your question. Pass an object: its keys become OTLP attributes you can filter on.
   ```js
   console.log("bot tick", { tic, pos: { x, y }, sector, target: t?.kind, action });
   console.warn("asset retry", { url, attempt, status });
   ```
   - Start the call with a short fixed label, so `--grep` and the body find it.
   - Keep the volume low: once a second, or on change, not once per frame. The log keeps only the newest 20,000 records, so a 60 fps log fills it in under six minutes and pushes out the error you wanted.
   - Mark these calls as temporary in a comment and remove them once the bug is fixed.

3. **Watch the elements involved** when the bug is about an interaction (a button that does nothing, a field that loses its value, a counter that stops updating). Watched elements get records for clicks, typing (one per pause, with the value; passwords and token-like fields are `[hidden]`), changes, submits, focus, non-text keys, and changes to their attributes, text and children. Pick one of:
   - Name them yourself: tell the user to open the page with `&watch=<url-encoded selector>` (repeatable) on a page that includes the script, or to run `AgentLog.watch("#checkout", { label: "checkout button" })` in the console.
   - Let the user point: ask them to click the badge, press **Watch an element** and click the element. The click that picks is not passed to the page.
   Watches persist per site until removed with × in the panel or `AgentLog.unwatch(selector)`.

4. **Ask the user to reproduce, then export.** Tell them: click the **Logging** badge, press **Download** (or **Copy** and paste the JSON), and attach the file. The export holds every page load on that site since the log was last cleared; ask them to press **Clear** before reproducing when old runs would get in the way.

5. **Read the export with the reader below.** Save it as `read_agent_log.py` and run it with the export's path.
   ```bash
   python3 read_agent_log.py agent-log.json --pages          # page loads: url, start, records, errors
   python3 read_agent_log.py agent-log.json --min warn       # warnings and errors first
   python3 read_agent_log.py agent-log.json --event console --grep "bot tick" --tail 50
   python3 read_agent_log.py agent-log.json --event http --attr http.response.status_code=404
   python3 read_agent_log.py agent-log.json --event dom --attr watch.label="checkout button"   # one watched element
   python3 read_agent_log.py agent-log.json --load 2 --jsonl > load2.jsonl   # flat rows for pandas or jq
   ```
   Read errors before anything else, then the records just before the first error in the same page load. Times are UTC.

6. **Verify the capture before diagnosing.** `--pages` must list the page load the user reproduced in, with a URL and a record count above one. If it does not, see the failure modes, fix the capture and ask for another run, rather than reasoning from an empty log.

7. **Report from the records.** Quote the timestamp, `eventName` and attributes you are relying on, so the user can find the same lines in the panel.

## The reader

```python
#!/usr/bin/env python3
"""Flatten an Agent Log export (OTLP/JSON logs) into one line per record, with filters."""
import argparse, json, sys
from datetime import datetime, timezone

SEV = {"trace": 1, "debug": 5, "info": 9, "warn": 13, "error": 17, "fatal": 21}

def value(v):
    if not v: return None
    if "stringValue" in v: return v["stringValue"]
    if "intValue" in v: return int(v["intValue"])
    if "doubleValue" in v: return v["doubleValue"]
    if "boolValue" in v: return v["boolValue"]
    if "arrayValue" in v: return [value(x) for x in v["arrayValue"].get("values", [])]
    if "kvlistValue" in v: return attrs(v["kvlistValue"].get("values"))
    return v.get("bytesValue")

def attrs(lst): return {a["key"]: value(a.get("value")) for a in lst or []}

def loads(doc):
    for n, rl in enumerate(doc.get("resourceLogs", [])):
        res = attrs(rl.get("resource", {}).get("attributes"))
        recs = []
        for sl in rl.get("scopeLogs", []):
            for r in sl.get("logRecords", []):
                ns = int(r.get("timeUnixNano") or 0)
                recs.append({"load": n, "time": datetime.fromtimestamp(ns / 1e9, timezone.utc).isoformat(timespec="milliseconds"),
                             "sev": r.get("severityText", ""), "sevn": r.get("severityNumber", 0), "event": r.get("eventName", ""),
                             "body": value(r.get("body")), "attrs": attrs(r.get("attributes"))})
        yield n, res, sorted(recs, key=lambda x: x["time"])

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", nargs="?", default="-", help="the export; - reads stdin")
    ap.add_argument("--pages", action="store_true", help="list the page loads and stop")
    ap.add_argument("--min", choices=list(SEV), help="minimum severity")
    ap.add_argument("--event", action="append", default=[], help="eventName prefix, e.g. console, http.fetch, error (repeatable)")
    ap.add_argument("--grep", help="case-insensitive text in the body or attributes")
    ap.add_argument("--attr", action="append", default=[], help="key=value, compared as text (repeatable)")
    ap.add_argument("--load", type=int, help="only this page load, numbered as --pages shows")
    ap.add_argument("--tail", type=int, help="only the last N matching records")
    ap.add_argument("--jsonl", action="store_true", help="one JSON object per record")
    a = ap.parse_args()
    doc = json.load(sys.stdin if a.file == "-" else open(a.file, encoding="utf-8"))
    if a.pages:
        for n, res, recs in loads(doc):
            errs = sum(r["sevn"] >= 17 for r in recs)
            print(f"[{n}] {res.get('agentlog.started_at', '?')}  {len(recs)} records, {errs} errors  {res.get('url.full', '?')}  ({res.get('user_agent.original', '')[:60]})")
        return
    out = []
    for n, res, recs in loads(doc):
        if a.load is not None and n != a.load: continue
        for r in recs:
            if a.min and r["sevn"] < SEV[a.min]: continue
            if a.event and not any(r["event"].startswith(e) for e in a.event): continue
            text = f"{r['body']} {json.dumps(r['attrs'], default=str)}"
            if a.grep and a.grep.lower() not in text.lower(): continue
            if any(str(r["attrs"].get(k)) != v for k, v in (x.split("=", 1) for x in a.attr)): continue
            out.append(r)
    for r in out[-a.tail:] if a.tail else out:
        if a.jsonl: print(json.dumps({k: v for k, v in r.items() if k != "sevn"}, default=str))
        else: print(f"[{r['load']}] {r['time'][11:23]} {r['sev']:5} {r['event']:16} {r['body']}" + (f"  {json.dumps(r['attrs'], default=str)}" if r["attrs"] else ""))

if __name__ == "__main__":
    main()
```

Without Python, `jq` reads the same file: `jq -c '.resourceLogs[].scopeLogs[].logRecords[] | select(.severityNumber >= 13) | [.eventName, .body.stringValue]' agent-log.json`.

## Export format

An OTLP/JSON `ExportLogsServiceRequest`. Each page load is one `resourceLogs` entry; its resource attributes are `service.name` (the host), `session.id`, `url.full`, `page.title`, `user_agent.original`, `browser.language`, `browser.viewport`, `agentlog.started_by` and `agentlog.started_at`. Each log record has `timeUnixNano` (a string of nanoseconds), `severityNumber`, `severityText`, `eventName`, `body.stringValue` and `attributes`, where integers are strings in `intValue`.

| eventName | attributes |
|---|---|
| `console.log` `.info` `.debug` `.warn` `.error` `.trace` `.assert` | the logged object's keys; `exception.*` for an Error argument; `arg0`, `arg1`… for arrays, maps and DOM nodes |
| `error.uncaught` | `exception.type`, `exception.message`, `exception.stacktrace`, `code.filepath`, `code.lineno` |
| `error.rejection` | `exception.*`, or `reason` for a non-Error |
| `error.resource` | `url.full`, `html.element` |
| `csp.violation` | `csp.directive`, `csp.blocked_uri` |
| `http.fetch`, `http.xhr` | `http.request.method`, `url.full`, `http.response.status_code`, `duration_ms`, `error.type` on failure; with `agentlog.source: resource-timing` there is no method, and `agentlog.before_start` marks a request made before logging started |
| `dom.click` `.dblclick` `.input` `.change` `.submit` `.focus` `.blur` `.keydown` | `watch.selector`, `watch.label`, `dom.target`, `dom.watched` (when the event hit a descendant), `dom.text`, `pointer.x`/`.y`, `dom.value`, `dom.checked`, `key`, `key.modifiers` |
| `dom.mutation` | `watch.selector`, `dom.text` (the element's text after the change), `dom.added`, `dom.removed`, `dom.changes` (attribute and text changes with old and new values) |
| `dom.watch` | `watch.selector`, `watch.matches`: a watch was added or removed, or now matches a different number of elements (0 means the element is gone) |
| `page.navigation`, `page.visibility`, `agentlog.start`, `agentlog.stop` | `url.full`, `navigation.type`, `page.visibility` |

## Failure modes

- **No badge appears.** The script did not load. On a strict-CSP page the console shows a Content-Security-Policy error naming austegard.com; switch the user to the full-script paste. On your own page, check that the tag is present and the URL has `logging=true`.
- **The log starts after the bug.** The bookmarklet and console routes start recording when clicked, so console output and errors during page load are missing (requests from page load are included, marked `agentlog.before_start`). An app that kept its own reference to `console.log` at startup also bypasses the capture when it starts late. Use a page that includes the script and reload it with `?logging=true`.
- **The export is empty or from another page.** The log is stored per site: it must be exported from a page on the same origin as the one that was logged.
- **The interesting records are gone.** More than 20,000 records pushed them out. Reduce the logging rate, or have the page call `AgentLog.start({ max: 100000 })`.
- **Private data in the export.** Credential-like query parameters are redacted in URLs, but console arguments are recorded as given. Do not log tokens or personal data, and tell the user to review the file before sharing it anywhere else.
