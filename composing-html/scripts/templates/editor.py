"""Custom-editor templates — throwaway purpose-built tools.

  - editor.triage_board: Drag-and-drop kanban for items across columns.
  - editor.flag_editor: Boolean toggles with dependency warnings.
  - editor.prompt_tuner: Live variable substitution into a template prompt.
"""

from __future__ import annotations

import json
from . import register
import composer as c


# --------------------------------------------------------------------------- #
# triage_board                                                                #
# --------------------------------------------------------------------------- #

@register(
    "editor.triage_board",
    summary="Drag-and-drop board: columns of cards. Reorder within and across columns.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "columns": "List[{id, label, color?: 'clay|olive|info|err', items: [{id, title, body_html?, tags?: [str]}]}].",
    },
)
def triage_board(spec: dict) -> dict:
    color_map = {"clay":"var(--clay)","olive":"var(--olive)","info":"var(--info)","err":"var(--err)"}
    cols = []
    for col in spec.get("columns", []):
        accent = color_map.get(col.get("color","clay"), "var(--clay)")
        items = []
        for it in col.get("items", []):
            tags = "".join(c.badge(t) for t in (it.get("tags") or []))
            items.append(
                f'<div class="board-card" draggable="true" data-id="{c.esc(it.get("id"))}">'
                f'<div class="board-card-title">{c.esc(it.get("title"))}</div>'
                + (f'<div class="board-card-body">{it.get("body_html","")}</div>' if it.get("body_html") else "")
                + (f'<div class="row" style="margin-top:8px;">{tags}</div>' if tags else "")
                + '</div>'
            )
        cols.append(
            f'<div class="board-col">'
            f'<div class="board-col-head" style="border-bottom:2px solid {accent};">'
            f'<span>{c.esc(col.get("label"))}</span>'
            f'<span class="board-col-count">{len(col.get("items") or [])}</span></div>'
            f'<div class="board-col-body" data-sortable="true" data-zone="{c.esc(col.get("id"))}">{"".join(items)}</div>'
            f'</div>'
        )
    body = c.section(body=f'<div class="board">{"".join(cols)}</div>')
    extra_css = """
    .board { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; }
    .board-col { background: var(--g100); border: var(--border-soft); border-radius: var(--radius); display: flex; flex-direction: column; }
    .board-col-head { padding: 12px 14px; font-family: var(--mono); font-size: 12px; color: var(--g700);
                       text-transform: uppercase; letter-spacing: .06em; display: flex; justify-content: space-between; }
    .board-col-count { color: var(--g500); }
    .board-col-body { padding: 10px; display: flex; flex-direction: column; gap: 8px; min-height: 80px; }
    .board-card { background: var(--paper); border: var(--border-soft); border-radius: var(--radius-sm);
                  padding: 10px 12px; cursor: grab; }
    .board-card:active { cursor: grabbing; }
    .board-card-title { font-weight: 600; font-size: 14px; }
    .board-card-body { font-size: 13px; color: var(--g700); margin-top: 4px; }
    """
    return {
        "title": spec.get("title", "Triage board"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "EDITOR"),
        "body": body,
        "extra_css": extra_css,
        "page_class": "page page--wide",
    }


# --------------------------------------------------------------------------- #
# flag_editor                                                                 #
# --------------------------------------------------------------------------- #

@register(
    "editor.flag_editor",
    summary="Toggle editor for boolean flags with dependency warnings.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "flags": "List[{id, label, description?, default: bool, "
                 "requires?: [flag_id], conflicts_with?: [flag_id]}].",
    },
)
def flag_editor(spec: dict) -> dict:
    flags = spec.get("flags") or []
    rows = []
    for f in flags:
        rows.append(
            f'<div class="flag" data-id="{c.esc(f["id"])}" '
            f'data-requires=\'{json.dumps(f.get("requires") or [])}\' '
            f'data-conflicts=\'{json.dumps(f.get("conflicts_with") or [])}\'>'
            f'<div class="flag-meta">'
            f'<div style="font-family:var(--mono);font-size:13px;">{c.esc(f["id"])}</div>'
            f'<div style="font-weight:600;">{c.esc(f.get("label"))}</div>'
            + (f'<div style="font-size:13px;color:var(--g700);margin-top:2px;">{c.esc(f.get("description"))}</div>' if f.get("description") else "")
            + '</div>'
            f'<label class="switch">'
            f'<input type="checkbox" {"checked" if f.get("default") else ""}>'
            f'<span class="slider"></span></label>'
            f'<div class="flag-warn" hidden></div></div>'
        )
    body = c.section(body=f'<div class="flag-list">{"".join(rows)}</div>')
    extra_css = """
    .flag-list { display: flex; flex-direction: column; gap: 10px; }
    .flag { display: grid; grid-template-columns: 1fr auto; gap: 16px; align-items: center;
            background: var(--paper); border: var(--border); border-radius: var(--radius); padding: 14px 18px; position: relative; }
    .flag-meta { min-width: 0; }
    .flag-warn { grid-column: 1 / -1; padding: 10px 12px; border-left: 3px solid var(--warn); background: #F8ECCB; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; font-size: 13px; }
    .switch { position: relative; display: inline-block; width: 44px; height: 24px; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; inset: 0; background: var(--g300); border-radius: 24px; transition: .15s; }
    .slider::before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; top: 3px; background: white; border-radius: 50%; transition: .15s; }
    .switch input:checked + .slider { background: var(--clay); }
    .switch input:checked + .slider::before { transform: translateX(20px); }
    """
    extra_js = """
    (function(){
      function checked(id){
        var el = document.querySelector('.flag[data-id="'+id+'"] input[type=checkbox]');
        return !!(el && el.checked);
      }
      function setWarn(flagEl, msg){
        var w = flagEl.querySelector('.flag-warn');
        if (!w) return;
        if (msg) { w.textContent = msg; w.hidden = false; } else { w.hidden = true; w.textContent = ''; }
      }
      function recompute(){
        document.querySelectorAll('.flag').forEach(function(flag){
          if (!flag.querySelector('input[type=checkbox]').checked) { setWarn(flag, ''); return; }
          var requires = JSON.parse(flag.dataset.requires || '[]');
          var conflicts = JSON.parse(flag.dataset.conflicts || '[]');
          var missing = requires.filter(function(r){ return !checked(r); });
          var clashes = conflicts.filter(function(r){ return checked(r); });
          if (missing.length) setWarn(flag, 'Requires: ' + missing.join(', '));
          else if (clashes.length) setWarn(flag, 'Conflicts with: ' + clashes.join(', '));
          else setWarn(flag, '');
        });
      }
      document.querySelectorAll('.flag input[type=checkbox]').forEach(function(el){
        el.addEventListener('change', recompute);
      });
      recompute();
    })();
    """
    return {
        "title": spec.get("title", "Flag editor"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "EDITOR"),
        "body": body,
        "extra_css": extra_css,
        "extra_js": extra_js,
    }


# --------------------------------------------------------------------------- #
# prompt_tuner                                                                #
# --------------------------------------------------------------------------- #

@register(
    "editor.prompt_tuner",
    summary="Prompt template tuner: edit variables, see live-rendered final prompt.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "template": "Prompt template string. Use {{variable_name}} placeholders.",
        "variables": "List[{name, label?, default, type?: 'text|textarea|select', options?: [str]}].",
    },
)
def prompt_tuner(spec: dict) -> dict:
    template = spec.get("template", "")
    variables = spec.get("variables") or []
    inputs = []
    for v in variables:
        label = c.esc(v.get("label") or v["name"])
        if v.get("type") == "textarea":
            inputs.append(f'<label>{label}<textarea data-var="{c.esc(v["name"])}" rows="4">{c.esc(v.get("default",""))}</textarea></label>')
        elif v.get("type") == "select":
            opts = "".join(f'<option value="{c.esc(o)}" {"selected" if o==v.get("default") else ""}>{c.esc(o)}</option>' for o in (v.get("options") or []))
            inputs.append(f'<label>{label}<select data-var="{c.esc(v["name"])}">{opts}</select></label>')
        else:
            inputs.append(f'<label>{label}<input type="text" data-var="{c.esc(v["name"])}" value="{c.esc(v.get("default",""))}"></label>')
    body = c.section(body=(
        f'<div class="tuner">'
        f'<div class="tuner-vars">{"".join(inputs)}</div>'
        f'<div class="tuner-out">'
        f'<div class="tuner-out-label">RENDERED PROMPT</div>'
        f'<pre id="rendered"></pre></div>'
        f'</div>'
    ))
    template_json = json.dumps(template)
    extra_css = """
    .tuner { display: grid; grid-template-columns: 360px 1fr; gap: 24px; }
    @media (max-width: 880px) { .tuner { grid-template-columns: 1fr; } }
    .tuner-vars { display: flex; flex-direction: column; gap: 14px; background: var(--g100); padding: 18px; border-radius: var(--radius); }
    .tuner-vars label { display: flex; flex-direction: column; gap: 6px; font-family: var(--mono); font-size: 12px; color: var(--g700); }
    .tuner-vars input, .tuner-vars textarea, .tuner-vars select {
      font-family: var(--mono); font-size: 13px; padding: 8px 10px;
      border: 1px solid var(--g300); border-radius: 6px; background: var(--paper); color: var(--slate);
    }
    .tuner-out-label { font-family: var(--mono); font-size: 11px; color: var(--g500); letter-spacing: .06em; margin-bottom: 8px; }
    .tuner-out pre { white-space: pre-wrap; word-break: break-word; }
    """
    extra_js = f"""
    (function(){{
      var tpl = {template_json};
      function render(){{
        var out = tpl;
        document.querySelectorAll('[data-var]').forEach(function(el){{
          var k = el.dataset.var;
          var v = el.value;
          out = out.replace(new RegExp('\\\\{{\\\\{{\\\\s*' + k.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + '\\\\s*\\\\}}\\\\}}', 'g'), v);
        }});
        document.getElementById('rendered').textContent = out;
      }}
      document.querySelectorAll('[data-var]').forEach(function(el){{ el.addEventListener('input', render); }});
      render();
    }})();
    """
    return {
        "title": spec.get("title", "Prompt tuner"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "EDITOR"),
        "body": body,
        "extra_css": extra_css,
        "extra_js": extra_js,
    }
