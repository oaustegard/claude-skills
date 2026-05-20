---
name: composing-html
description: Composes single-file HTML artifacts (PR review writeups, status reports, incident postmortems, slide decks, design systems, prototypes, flowcharts, module maps, feature explainers, kanban boards, prompt tuners) from a small JSON spec instead of hand-written HTML/CSS/JS. Use when the user asks to "compare options side-by-side", requests an HTML version of a report or review or deck, asks for a flowchart, status update, postmortem, design system reference, interactive prototype, custom editor — or explicitly says "HTML artifact", "single HTML file", "self-contained HTML". Skip for ad-hoc HTML snippets (forms, emails, embedded widgets) where there's no template fit.
metadata:
  version: 0.3.0
---

# composing-html

Produce single-file HTML artifacts without hand-writing the page chrome. The
composer supplies `<!DOCTYPE>`, `<head>`, inlined CSS, `base.js`, design
tokens, masthead, and colophon. You supply a title and the body content.

The product is the **chrome and inventory below** — primitives you can drop
into any artifact without re-deriving what a card, badge, or eyebrow looks
like. Templates are shortcuts on top of this, useful when the same artifact
shape repeats; see [Templates](#templates-shortcuts-for-repeat-structure)
near the end.

## Default workflow: freeform

`freeform` gives you the whole chrome with one content slot — `body_html` —
for the page body. Reach for it first. Reach for a template only when the
structure repeats across artifacts (see [Templates](#templates-shortcuts-for-repeat-structure)
near the end).

There are two ways to invoke it. **Use the `--set` flow for anything with a
substantial body** — it sidesteps the JSON-string escaping that bites
heredoc-style spec writing (newlines, quotes, `<`/`&` inside multi-line
HTML).

### Recommended: HTML in a file, metadata via `--set`

```
1. Write the body to a .html file directly (no JSON, no escaping).
2. python scripts/build.py build freeform \
       --set title='My Page' \
       --set subtitle='Optional subhead' \
       --set body_html=@body.html \
       --out artifact.html
```

`--set KEY=VALUE` assigns a literal string; `--set KEY=@FILE` loads the file
contents verbatim into that spec field. Repeat for any field. Works for
`body_html`, `extra_css`, `extra_js`, `eyebrow`, `page_class`, and the same
`*_html` fields in any other template (`summary_html`, `intro_html`,
`details_html`, …).

### Spec-file workflow (best for structured templates)

```
1. python scripts/build.py describe <template>     # required keys + skeleton
2. write spec.json
3. python scripts/build.py build <template> --spec spec.json --out artifact.html
```

For templates with typed slots (`pr_review.findings[]`, `slide_deck.slides[]`,
`status_report.metrics[]`), the spec file is the right shape — the template
reasons over the structure. For `freeform`, the spec is mostly a thin config
wrapper around one HTML string; the `--set` flow above is usually less
friction.

You can mix both: small `spec.json` for metadata, `--set body_html=@body.html`
for the heavy bit. `--set` overrides any matching field from `--spec`.

### Pitfall: don't inline multi-line HTML into a JSON heredoc

`cat > spec.json <<EOF { "body_html": "<multi\nline>\n..." } EOF` does not
produce valid JSON — JSON strings can't contain raw newlines or unescaped
quotes. Either:
- use `--set body_html=@body.html` (recommended), or
- assemble the spec in Python with `json.dump(spec, f)` so escaping is automatic.

## Inventory

Everything in this section is loaded into every artifact via inlined CSS and
`base.js`. Use these tokens and classes inside `body_html` (or any
template's `*_html` field) without re-declaring them.

### Color tokens

| Token | Hex | Use |
|---|---|---|
| `--ivory` | `#FAF9F5` | Page background |
| `--paper` | `#FFFFFF` | Card background |
| `--slate` | `#141413` | Headings, inverted background |
| `--clay` | `#D97757` | Brand accent (lines, primary actions) |
| `--clay-d` | `#B85C3E` | Hover/dark variant |
| `--oat` | `#E3DACC` | Soft contrast surface |
| `--olive` | `#788C5D` | Success, secondary accent |
| `--rust` | `#B04A3F` | Errors, destructive |
| `--moss` | `#4A6B3A` | Success text |
| `--g100` … `--g700` | grays | Surfaces, borders, body text |

Semantic aliases: `--ok`, `--warn`, `--err`, `--info`.

### Type stacks

- `--serif` — display headings (h1, h2, big numerics).
- `--sans` — body text (default).
- `--mono` — code, eyebrows, badges, captions.

### Geometry

`--radius-sm` (6px) · `--radius` (10px) · `--radius-lg` (16px) ·
`--border` · `--border-soft` · `--shadow-card` · `--shadow-pop`.

### Layout primitives

- `.page` — main column (1080px max). Variants: `.page--wide` (1280px),
  `.page--narrow` (720px). Set via the `page_class` spec key.
- `.masthead` — header strip with `.eyebrow` + `<h1>` + `.subtitle`
  (auto-rendered from `title`/`subtitle`/`eyebrow` unless `show_masthead`
  is false).
- `.grid .grid--2|3|4|auto` — responsive CSS grid.
- `.stack`, `.row` — vertical / horizontal flex.
- `.card`, `.card--soft`, `.card--elev` — content containers.
- `.rule` — `<hr>` underline below `<h2>`.
- `.colophon` — footer strip (auto-added by composer).

### Components

- **Eyebrow**: `<div class="eyebrow">SECTION</div>` — small all-caps label
  with a leading clay rule.
- **Badge**: `<span class="badge badge--ok|warn|err|info|clay">v1.0</span>`.
- **Kbd**: `<span class="kbd">⌘K</span>`.
- **Bullets**: `<ul class="bullets"><li>…</li></ul>` — clay dots.
- **Code**: inline `<code>` and block `<pre><code>`. Block code gets a
  `copy` button automatically via `base.js`.
- **Details**: native `<details><summary>…</summary>…</details>` styled.

### Tabs

```html
<div class="tabgroup">
  <div class="tabs">
    <button data-target="a">Tab A</button>
    <button data-target="b">Tab B</button>
  </div>
  <div class="tab-panel" data-id="a">…</div>
  <div class="tab-panel" data-id="b">…</div>
</div>
```

`base.js` wires this automatically and selects the first tab by default.

### Drag-to-reorder

```html
<div data-sortable="true">
  <div draggable="true">…</div>
  <div draggable="true">…</div>
</div>
```

Optional cross-zone drops: add `data-zone="<id>"` to each container.

### Live parameter bindings

```html
<input type="range" data-bind="size" min="0" max="100" value="50" data-format="number" data-unit="px">
<span data-out="size"></span>
<style>.box { width: var(--bind-size, 50px); }</style>
```

The CSS custom property `--bind-<name>` is updated on every input event,
and any `[data-out="<name>"]` element receives the formatted value.

## Output rules

Spend output tokens on **content**, not chrome:

1. **Never write `<html>`, `<head>`, `<style>`, `<script>`, or `<link>`.** The
   composer adds all of them. If you find yourself writing a complete page,
   you missed the skill.
2. **Don't restate design tokens.** Reuse the inventory above — `var(--clay)`,
   `.card`, `.badge--warn`, `.bullets`, etc. are already loaded.
3. **`body_html` is HTML, not a JSON dialect.** Write `<section>`, `<h2>`,
   `<ul class="bullets">` directly. No translation layer.
4. **Anything in an `_html` field is inserted verbatim** — escape any
   user-supplied content yourself. All other string values are
   HTML-escaped automatically.
5. **One artifact per build.** Browser tabs are free.

## Iteration

Edit the spec, re-run `build`, open in a browser. If a layout pattern
repeats across multiple artifacts, that's when a template earns its
keep — otherwise stay in `freeform`.

## Templates: shortcuts for repeat structure

When the **same artifact shape** recurs (status reports week after week, PR
reviews across many PRs, slide decks with consistent navigation), a
template's fixed slot map is worth the translation cost. It enforces
cross-artifact consistency and skips the layout decisions you'd otherwise
re-derive each time.

Use a template only when:
1. You're producing the same artifact shape repeatedly.
2. The repeat structure justifies a fixed slot map.
3. Cross-artifact consistency matters more than per-artifact flexibility.

Otherwise: `freeform`.

```
1. python scripts/build.py list                    # all templates, one-line summaries
2. python scripts/build.py describe <template>     # required keys + JSON skeleton
3. write spec.json                                  # only your content + parameters
4. python scripts/build.py build <template> --spec spec.json --out artifact.html
```

`describe` prints a valid-JSON starter skeleton you can edit in place. For
worked examples, see `references/templates.md` — but only after picking a
template; reading it cold wastes context.

For templates with prose-heavy `*_html` slots (e.g. `summary_html`,
`intro_html`, `details_html`), the same `--set KEY=@FILE` mechanism from the
freeform workflow applies — load the prose from a `.html` file rather than
escaping it into the JSON spec.

There are 21 templates, grouped into 9 categories plus `freeform`:

- `report.*` — status_report, incident_report
- `review.*` — pr_review, code_walkthrough, module_map
- `editor.*` — triage_board, flag_editor, prompt_tuner
- `deck.*` — slide_deck (arrow-key + space navigation)
- `design.*` — design_system, component_variants
- `exploration.*` — comparison_grid, design_directions, implementation_plan
- `research.*` — feature_explainer, concept_explainer
- `diagram.*` — svg_figure_sheet, flowchart
- `prototype.*` — animation_sandbox, click_flow

Some templates with prose-heavy slots take raw HTML in keys ending with
`_html` (e.g. `summary_html`, `intro_html`, `details_html`). Same rules as
`freeform.body_html`: use the inventory above, escape user-supplied content.

## Tests

`tests/test_smoke.py` covers every template with a representative spec plus
explicit security regressions (table escaping, script-tag breakout in
`prompt_tuner`, attribute injection in `flag_editor`, CSS-color injection,
spec mutation in `module_map`). Run with:

```
python composing-html/tests/test_smoke.py        # no pytest required
python -m pytest composing-html/tests -q          # if pytest is available
```

When adding or changing a template, add a spec entry and any regression
asserts before merging.
