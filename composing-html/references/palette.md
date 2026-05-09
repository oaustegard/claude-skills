# Palette and primitives

The base CSS is inlined into every artifact. You can use these tokens and
classes inside any `*_html` field — including `freeform.body_html` — without
re-declaring them.

## Color tokens

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

## Type stacks

- `--serif` — display headings (h1, h2, big numerics).
- `--sans` — body text (default).
- `--mono` — code, eyebrows, badges, captions.

## Geometry

`--radius-sm` (6px) · `--radius` (10px) · `--radius-lg` (16px) ·
`--border` · `--border-soft` · `--shadow-card` · `--shadow-pop`.

## Layout primitives

- `.page` — main column (1080px max). Variants: `.page--wide` (1280px),
  `.page--narrow` (720px).
- `.masthead` — header strip with `.eyebrow` + `<h1>` + `.subtitle`.
- `.grid .grid--2|3|4|auto` — responsive CSS grid.
- `.stack`, `.row` — vertical / horizontal flex.
- `.card`, `.card--soft`, `.card--elev` — content containers.
- `.rule` — `<hr>` underline below `<h2>`.
- `.colophon` — footer strip (auto-added by composer).

## Components

- **Eyebrow**: `<div class="eyebrow">SECTION</div>` — small all-caps label
  with a leading clay rule.
- **Badge**: `<span class="badge badge--ok|warn|err|info|clay">v1.0</span>`.
- **Kbd**: `<span class="kbd">⌘K</span>`.
- **Bullets**: `<ul class="bullets"><li>…</li></ul>` — clay dots.
- **Code**: inline `<code>` and block `<pre><code>`. Block code gets a
  `copy` button automatically via `base.js`.
- **Details**: native `<details><summary>…</summary>…</details>` styled.

## Tabs

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

## Drag-to-reorder

```html
<div data-sortable="true">
  <div draggable="true">…</div>
  <div draggable="true">…</div>
</div>
```

Optional cross-zone drops: add `data-zone="<id>"` to each container.

## Live parameter bindings

```html
<input type="range" data-bind="size" min="0" max="100" value="50" data-format="number" data-unit="px">
<span data-out="size"></span>
<style>.box { width: var(--bind-size, 50px); }</style>
```

The CSS custom property `--bind-<name>` is updated on every input event,
and any `[data-out="<name>"]` element receives the formatted value.

## Helper functions (Python side)

If you're calling templates from a custom builder, `composer.py` exposes:

`esc`, `attrs`, `tag`, `void`, `eyebrow`, `badge`, `kbd`, `code_block`,
`inline_code`, `section`, `card`, `grid`, `stack`, `row`, `bullets`,
`kv_list`, `table`, `details`, `tabs`, `callout`, `slug`.

These all return HTML strings and accept plain Python data.
