"""Report templates.

  - report.status_report: Periodic status report — shipped/in-flight/blocked + metrics.
  - report.incident_report: Timeline-based incident postmortem.
"""

from __future__ import annotations

from . import register
import composer as c


# --------------------------------------------------------------------------- #
# status_report                                                               #
# --------------------------------------------------------------------------- #

@register(
    "report.status_report",
    summary="Status report: header metrics, shipped/in-flight/blocked sections, optional charts (SVG).",
    spec_keys={
        "title": "Page title (e.g. 'Platform Eng — Week of Mar 10').",
        "subtitle": "Optional sub-headline.",
        "metrics": "List[{label, value, delta?, kind?: 'ok|warn|err|info'}]. Rendered as KPI strip.",
        "shipped": "List[{title, owner?, body_html?}].",
        "in_flight": "List[{title, owner?, body_html?, progress?: 0..1}].",
        "blocked": "List[{title, owner?, body_html?}].",
        "extra_html": "Optional extra HTML appended at the end (e.g. a chart).",
    },
)
def status_report(spec: dict) -> dict:
    parts = []

    metrics = spec.get("metrics") or []
    if metrics:
        cells = []
        for m in metrics:
            kind = m.get("kind", "info")
            color = {"ok":"var(--ok)","warn":"var(--warn)","err":"var(--err)","info":"var(--info)"}.get(kind,"var(--info)")
            delta = ""
            if m.get("delta"):
                delta = f'<div style="font-family:var(--mono);font-size:12px;color:{color};margin-top:4px;">{c.esc(m["delta"])}</div>'
            cells.append(
                f'<div style="border-left:3px solid {color};padding:14px 18px;background:var(--paper);border-radius:0 var(--radius-sm) var(--radius-sm) 0;">'
                f'<div style="font-family:var(--mono);font-size:11px;color:var(--g500);text-transform:uppercase;letter-spacing:.06em;">{c.esc(m.get("label"))}</div>'
                f'<div style="font-family:var(--serif);font-size:32px;line-height:1;margin-top:6px;">{c.esc(m.get("value"))}</div>'
                f'{delta}</div>'
            )
        parts.append(c.section(body=c.grid(cells, cols=min(4, max(1, len(cells))))))

    def _items_section(label: str, items: list, status_kind: str | None = None) -> str:
        if not items: return ""
        rows = []
        for it in items:
            head = (f'<div class="row" style="justify-content:space-between;">'
                    f'<h3>{c.esc(it.get("title"))}</h3>'
                    + (c.badge(it["owner"]) if it.get("owner") else "")
                    + '</div>')
            prog = ""
            if it.get("progress") is not None:
                pct = max(0, min(100, int(float(it["progress"]) * 100)))
                prog = (f'<div style="margin-top:10px;height:6px;background:var(--g200);border-radius:3px;overflow:hidden;">'
                        f'<div style="width:{pct}%;height:100%;background:var(--clay);"></div></div>'
                        f'<div style="font-family:var(--mono);font-size:11px;color:var(--g500);margin-top:4px;">{pct}%</div>')
            body = head + (it.get("body_html") or "") + prog
            rows.append(c.card(body))
        return c.section(label, body=c.stack(rows))

    parts.append(_items_section("Shipped",   spec.get("shipped")   or []))
    parts.append(_items_section("In flight", spec.get("in_flight") or []))
    parts.append(_items_section("Blocked",   spec.get("blocked")   or []))

    if spec.get("extra_html"):
        parts.append(c.section(body=spec["extra_html"]))

    return {
        "title": spec.get("title", "Status report"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "STATUS"),
        "body": "".join(parts),
    }


# --------------------------------------------------------------------------- #
# incident_report                                                             #
# --------------------------------------------------------------------------- #

@register(
    "report.incident_report",
    summary="Incident postmortem: header severity, summary, minute-by-minute timeline, follow-ups.",
    spec_keys={
        "title": "Page title (e.g. 'INC-1247 — Search outage').",
        "subtitle": "Optional sub-headline.",
        "severity": "'sev1|sev2|sev3|sev4'.",
        "duration": "Human duration string (e.g. '47m').",
        "impact_html": "HTML describing user impact.",
        "summary_html": "Optional executive summary HTML.",
        "timeline": "List[{at, event, kind?: 'detected|triage|mitigation|resolved|note'}].",
        "root_cause_html": "Optional root cause HTML.",
        "followups": "List[{title, owner?, due?, status?: 'open|done'}].",
    },
)
def incident_report(spec: dict) -> dict:
    sev = (spec.get("severity") or "sev3").upper()
    sev_kind = {"SEV1":"err","SEV2":"err","SEV3":"warn","SEV4":"info"}.get(sev, "warn")
    head = c.card(
        c.row([c.badge(sev, sev_kind),
               (c.badge(f'Duration {spec["duration"]}', "info") if spec.get("duration") else "")]) +
        (f'<div style="margin-top:14px;">{spec["impact_html"]}</div>' if spec.get("impact_html") else "")
    )
    summary = c.section("Summary", body=spec["summary_html"]) if spec.get("summary_html") else ""

    tl_kind_color = {"detected":"var(--err)","triage":"var(--warn)","mitigation":"var(--info)",
                     "resolved":"var(--ok)","note":"var(--g500)"}
    tl_rows = []
    for ev in spec.get("timeline", []):
        col = tl_kind_color.get(ev.get("kind","note"), "var(--g500)")
        tl_rows.append(
            f'<div style="display:grid;grid-template-columns:90px 14px 1fr;gap:18px;padding:10px 0;border-bottom:1px solid var(--g150);">'
            f'<div style="font-family:var(--mono);font-size:12px;color:var(--g500);">{c.esc(ev.get("at"))}</div>'
            f'<div><div style="width:10px;height:10px;border-radius:50%;background:{col};margin-top:6px;"></div></div>'
            f'<div>{c.esc(ev.get("event"))}</div></div>'
        )
    timeline = c.section("Timeline", body="".join(tl_rows)) if tl_rows else ""

    rc = c.section("Root cause", body=spec["root_cause_html"]) if spec.get("root_cause_html") else ""

    followups = ""
    if spec.get("followups"):
        rows = [[fu.get("title"),
                 fu.get("owner") or "",
                 fu.get("due") or "",
                 c.raw(c.badge((fu.get("status","open")).upper(),
                               "ok" if fu.get("status") == "done" else "warn"))]
                for fu in spec["followups"]]
        followups = c.section("Follow-ups", body=c.table(["Action", "Owner", "Due", "Status"], rows))

    body = head + summary + timeline + rc + followups
    return {
        "title": spec.get("title", "Incident"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "INCIDENT"),
        "body": body,
    }
