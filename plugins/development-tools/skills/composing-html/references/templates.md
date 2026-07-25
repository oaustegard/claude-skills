# Template reference

Detailed parameter spec for each template. Read **only the section you need**;
each template's `describe` output covers the same ground in CLI form.

For all templates: spec keys ending in `_html` are inserted verbatim — escape
your own content there if it contains user input. All other string values are
HTML-escaped automatically.

---

## exploration.comparison_grid

```json
{
  "title": "Three caching approaches",
  "subtitle": "Tradeoffs across latency, memory, complexity",
  "eyebrow": "EXPLORATION",
  "recommendation": "In-memory LRU",
  "options": [
    {
      "name": "In-memory LRU",
      "verdict": "Simplest, lowest latency",
      "summary": "Per-process bounded cache.",
      "pros": ["Sub-µs hits", "No external dep"],
      "cons": ["Per-process duplication", "Cold on restart"],
      "tags": ["latency:fast", "cost:low"]
    }
  ]
}
```

`recommendation` (optional): exact `name` of the option to highlight with a
double border + clay accent + `RECOMMENDED` badge. Up to 3 options render
side-by-side; more wrap to additional rows.

---

## exploration.design_directions

```json
{
  "title": "Brand directions",
  "directions": [
    {
      "name": "Stoneware",
      "vibe": "Warm, grounded, hand-thrown",
      "palette": ["#FAF9F5", "#D97757", "#3D3D3A", "#788C5D"],
      "typography": {"display": "Aa", "body": "The quick brown fox..."},
      "notes": "Pairs with serif display + sans body."
    }
  ]
}
```

Each direction renders as a card with palette swatches, a sample type block,
and notes.

---

## exploration.implementation_plan

```json
{
  "title": "Search v2 rollout",
  "summary_html": "<p>Cutover from BM25 to hybrid.</p>",
  "data_flow": ["Query", "Embed", "Hybrid score", "Rerank", "Response"],
  "milestones": [
    {"name": "Embedding pipeline", "when": "Wk 1", "owner": "alex",
     "deliverables": ["Tokenizer", "Batcher"], "status": "done"},
    {"name": "Hybrid scorer", "when": "Wk 2", "deliverables": ["RRF fusion"], "status": "active"}
  ],
  "risks": [
    {"risk": "Latency spike", "likelihood": "med", "impact": "high",
     "mitigation": "Pre-warm + canary."}
  ]
}
```

`status`: `done | active | next | later` controls the dot color in the
timeline. `data_flow` is a simple list of step names rendered as
arrow-connected boxes.

---

## review.pr_review

```json
{
  "title": "PR #247 — Caching layer",
  "pr": {"repo": "octo/svc", "number": 247, "branch": "feat/cache",
         "author": "@jess", "additions": 312, "deletions": 48},
  "verdict": "Approve with minor follow-ups",
  "summary_html": "<p>Adds in-memory LRU on the search hot path.</p>",
  "findings": [
    {
      "file": "src/search/cache.py",
      "line": 42,
      "severity": "warn",
      "title": "LRU max size hardcoded",
      "body_html": "<p>Pull from config to allow per-env tuning.</p>",
      "snippet": "CACHE_MAX = 1024",
      "snippet_lang": "python"
    }
  ]
}
```

`severity`: `info | nit | warn | block`.

---

## review.code_walkthrough

```json
{
  "title": "How retrieval works",
  "intro_html": "<p>The retrieval path is three stages.</p>",
  "steps": [
    {"heading": "Tokenize", "body_html": "<p>Whitespace + lowercasing.</p>",
     "code": "tokens = text.lower().split()", "lang": "python"}
  ]
}
```

Steps are rendered as numbered (01, 02, …) two-column rows. Narrow page width.

---

## review.module_map

```json
{
  "title": "Service map",
  "intro_html": "<p>Top-level packages.</p>",
  "nodes": [
    {"id": "api", "label": "api", "description": "HTTP handlers", "kind": "core"},
    {"id": "engine", "label": "engine", "description": "ranking", "kind": "core"},
    {"id": "cache", "label": "cache", "description": "LRU", "kind": "util"},
    {"id": "db", "label": "postgres", "description": "index store", "kind": "external"}
  ],
  "edges": [
    {"from": "api", "to": "engine"},
    {"from": "engine", "to": "cache", "label": "hot path"}
  ],
  "legend": [{"label": "core", "kind": "core"}, {"label": "util", "kind": "util"}]
}
```

`kind`: `core | util | external` controls fill/border. `x` and `y` are
optional — auto-laid in a 3-column grid if omitted.

---

## design.design_system

```json
{
  "title": "Birchline design tokens",
  "colors": {
    "Brand": [{"name": "Clay", "hex": "#D97757", "token": "--clay"}],
    "Neutral": [{"name": "Slate", "hex": "#141413", "token": "--slate"}]
  },
  "typography": [
    {"name": "Display", "font_family": "var(--serif)", "size": "48px", "weight": "500", "line_height": "1.1"},
    {"name": "Body", "font_family": "var(--sans)", "size": "16px", "weight": "430"}
  ],
  "spacing": [{"name": "xs", "px": 4}, {"name": "sm", "px": 8}, {"name": "md", "px": 16}],
  "radii": [{"name": "sm", "px": 4}, {"name": "md", "px": 10}, {"name": "lg", "px": 16}]
}
```

Any group of colors is allowed — keys become section labels.

---

## design.component_variants

```json
{
  "title": "Button variants",
  "components": [
    {
      "name": "Button",
      "description": "Sizes × intents.",
      "axes": {
        "Size": ["sm", "md", "lg"],
        "Intent": ["default", "primary", "danger"]
      },
      "cells": [
        {"coords": {"Size": "sm", "Intent": "default"}, "html": "<button>Click</button>"},
        {"coords": {"Size": "md", "Intent": "primary"},
         "html": "<button style='background:var(--clay);color:white;border:none;padding:8px 16px;border-radius:6px;'>Click</button>"}
      ]
    }
  ]
}
```

With ≥2 axes, cells render in a labelled table. With 1 axis, cells render in
an auto grid of cards.

---

## prototype.animation_sandbox

```json
{
  "title": "Easing playground",
  "params": [
    {"name": "duration", "label": "Duration", "type": "range", "min": 100, "max": 2000, "step": 50, "default": 600, "unit": "ms", "format": "ms"},
    {"name": "easing", "label": "Easing", "type": "select", "options": ["ease", "ease-in-out", "linear", "cubic-bezier(.2,.8,.2,1)"], "default": "ease-in-out"}
  ],
  "preview_html": "<div id='ball' style='width:60px;height:60px;background:var(--clay);border-radius:50%;animation:bounce var(--bind-duration,600ms) var(--bind-easing,ease) infinite alternate;'></div><style>@keyframes bounce{from{transform:translateX(0)}to{transform:translateX(200px)}}</style>",
  "preview_height": "240px"
}
```

Each `param`'s value lands in the CSS custom property `--bind-<name>`
(append `unit` to the value) and is mirrored to any element with
`data-out="<name>"`.

---

## prototype.click_flow

```json
{
  "title": "Onboarding flow",
  "screens": [
    {"id": "welcome", "label": "Welcome", "html": "<h2>Welcome</h2><p>...</p>",
     "transitions": [{"label": "Get started →", "to_id": "signup"}]},
    {"id": "signup", "label": "Sign up", "html": "<form>...</form>",
     "transitions": [{"label": "Submit →", "to_id": "done"}]},
    {"id": "done", "label": "Done", "html": "<p>You're in.</p>"}
  ]
}
```

Transitions are anchor links; clicking jumps to the target screen.

---

## diagram.svg_figure_sheet

```json
{
  "title": "Architecture figures",
  "figures": [
    {"label": "Fig. 1", "caption": "Request flow",
     "svg": "<svg viewBox='0 0 200 100'>...</svg>",
     "span": 1}
  ]
}
```

`span: 2` makes a figure occupy the full row in the 2-column grid.

---

## diagram.flowchart

```json
{
  "title": "Deploy pipeline",
  "orientation": "vertical",
  "steps": [
    {"id": "build", "label": "Build", "kind": "start"},
    {"id": "test", "label": "Tests pass?", "kind": "decision",
     "branches": [{"label": "yes", "to_id": "stage"}, {"label": "no", "to_id": "fail"}]},
    {"id": "stage", "label": "Deploy staging", "kind": "process",
     "details_html": "<p>Blue/green swap.</p>"},
    {"id": "prod", "label": "Deploy prod", "kind": "end"},
    {"id": "fail", "label": "Notify", "kind": "end"}
  ]
}
```

`kind`: `start | process | decision | end`. Steps with `details_html` get
collapsible expanders below the diagram.

---

## deck.slide_deck

```json
{
  "title": "Q2 review",
  "slides": [
    {"kind": "title", "title": "Q2 Roundup", "subtitle": "What shipped",
     "eyebrow": "PLATFORM", "byline": "may 9 · alex"},
    {"kind": "section", "title": "Shipped", "eyebrow": "PART ONE", "invert": true},
    {"kind": "content", "title": "Search", "body_html": "<ul class='bullets'><li>...</li></ul>"},
    {"kind": "quote", "quote": "Ship to learn.", "attribution": "team retro"},
    {"kind": "code", "title": "API", "code": "client.search(...)", "lang": "python"},
    {"kind": "image", "src": "https://...", "alt": "...", "caption": "..."}
  ]
}
```

If no `kind: title` slide exists, one is auto-prepended from `title` /
`subtitle`. Navigation: arrow keys + space + Page Up/Down + Home/End.

---

## research.feature_explainer

```json
{
  "title": "Streaming responses",
  "intro_html": "<p>How tokens flow.</p>",
  "sections": [
    {
      "id": "transport", "heading": "Transport",
      "body_html": "<p>SSE over HTTP/2.</p>",
      "code_tabs": [
        {"label": "JS", "code": "const r = await fetch(url);", "lang": "javascript"},
        {"label": "Python", "code": "with httpx.stream(...): ...", "lang": "python"}
      ]
    }
  ]
}
```

A sticky TOC links to each section by `id`. Tabs let you compare code samples
across languages without scroll.

---

## research.concept_explainer

```json
{
  "title": "Vector embeddings",
  "body_html": "<p>An embedding is...</p><h2>Distance</h2><p>Cosine similarity...</p>",
  "demo_html": "<div>...interactive demo region...</div>",
  "glossary": [
    {"term": "Cosine sim.", "definition_html": "<code>1 - cos(θ)</code>"}
  ]
}
```

Narrow page width. The `demo_html` slot is rendered inside an elevated card.

---

## report.status_report

```json
{
  "title": "Platform — Week of May 4",
  "subtitle": "Search GA, queue migration in flight",
  "metrics": [
    {"label": "Deploys", "value": "42", "delta": "+12 vs prev", "kind": "ok"},
    {"label": "P95", "value": "180ms", "delta": "-40ms", "kind": "ok"},
    {"label": "Open Sev2s", "value": "3", "delta": "+1", "kind": "warn"}
  ],
  "shipped":  [{"title": "Search GA", "owner": "alex", "body_html": "<p>Public launch.</p>"}],
  "in_flight":[{"title": "Queue migration", "owner": "jess", "progress": 0.6, "body_html": "<p>Cutover Friday.</p>"}],
  "blocked":  [{"title": "OAuth review", "owner": "sec-team", "body_html": "<p>Awaiting compliance.</p>"}]
}
```

`progress` is 0–1; rendered as a clay-filled bar with a percentage label.

---

## report.incident_report

```json
{
  "title": "INC-1247 — Search outage",
  "severity": "sev2",
  "duration": "47m",
  "impact_html": "<p>~12% of searches returned empty results.</p>",
  "summary_html": "<p>Index shard rebalance starved the read pool.</p>",
  "timeline": [
    {"at": "14:02", "event": "Spike in 5xx on /search", "kind": "detected"},
    {"at": "14:08", "event": "Paged on-call", "kind": "triage"},
    {"at": "14:32", "event": "Rolled back rebalance", "kind": "mitigation"},
    {"at": "14:49", "event": "Error rate normal", "kind": "resolved"}
  ],
  "root_cause_html": "<p>The rebalance scheduler had no concurrency cap.</p>",
  "followups": [
    {"title": "Cap rebalance concurrency", "owner": "platform", "due": "May 16", "status": "open"}
  ]
}
```

`severity`: `sev1 | sev2 | sev3 | sev4`.

---

## editor.triage_board

```json
{
  "title": "Triage",
  "columns": [
    {"id": "todo", "label": "To do", "color": "info",
     "items": [{"id": "i1", "title": "Fix auth bug", "tags": ["P1", "bug"]}]},
    {"id": "doing", "label": "Doing", "color": "clay",
     "items": [{"id": "i2", "title": "Refactor cache", "tags": ["P2"]}]},
    {"id": "done", "label": "Done", "color": "olive",
     "items": [{"id": "i3", "title": "Deploy v0.4"}]}
  ]
}
```

Cards are draggable within and across columns. `color`: `clay | olive | info | err`.

---

## editor.flag_editor

```json
{
  "title": "Feature flags",
  "flags": [
    {"id": "new_search", "label": "New search",
     "description": "Vector + BM25 hybrid.", "default": true},
    {"id": "reranker", "label": "Cross-encoder reranker",
     "description": "Cost: ~30ms.", "default": false,
     "requires": ["new_search"]},
    {"id": "legacy_search", "label": "Legacy search",
     "default": false, "conflicts_with": ["new_search"]}
  ]
}
```

When a flag is toggled on, missing `requires` and conflicting
`conflicts_with` flags surface as inline warnings.

---

## editor.prompt_tuner

```json
{
  "title": "Email subject tuner",
  "template": "Hi {{name}}, your {{item}} is {{status}}.",
  "variables": [
    {"name": "name", "label": "Recipient", "default": "Alex"},
    {"name": "item", "label": "Item", "type": "textarea", "default": "order #1234"},
    {"name": "status", "type": "select",
     "options": ["shipped", "delayed", "delivered"], "default": "shipped"}
  ]
}
```

Edit any variable; the rendered prompt updates live. `type`: `text` (default)
| `textarea` | `select`.

---

## freeform

```json
{
  "title": "Refactor proposal",
  "subtitle": "Extract OAuth into its own module",
  "eyebrow": "ARCHITECTURE",
  "body_html": "<section><h2>Why</h2><hr class='rule'><p>...</p></section>",
  "page_class": "page",
  "show_masthead": true
}
```

`page_class`: `page` | `page page--wide` | `page page--narrow`.

`extra_css` and `extra_js` accept raw strings appended after base styles.

`body_attrs`: dict on `<body>` (e.g. `{"data-deck": "true"}` to enable
arrow-key deck navigation on a custom layout).
