---
name: composing-html
description: Compose self-contained, single-file HTML artifacts (PR reviews, status reports, slide decks, design systems, prototypes, flowcharts, explainers, custom editors) by writing a small JSON spec instead of raw HTML/CSS/JS. Use when the user asks for an HTML artifact, an HTML version of a report/review/deck/explainer, an interactive prototype, a design system reference, a flowchart, a status/incident report, or an "HTML file" instead of a Markdown answer. Also triggers on: "HTML artifact", "self-contained HTML", "single HTML file", "interactive HTML", "slide deck", "design system", "flowchart", "module map", "PR review writeup", "status report", "incident report", "prompt tuner", "feature flag editor", "triage board".
metadata:
  version: 0.1.0
---

# composing-html

Produce single-file HTML artifacts by composing a small JSON spec, not by
hand-writing markup. Page chrome (head, design tokens, CSS, JS, masthead,
footer) lives in Python. You write only the parameters and the inner content.

## When to reach for this skill

Use HTML over Markdown when the answer benefits from any of:

- Side-by-side layouts, grids, columns
- SVG diagrams, flowcharts, swatches, timelines
- Interactive elements: tabs, collapsibles, sliders, drag-and-drop, key-nav decks
- Annotated code with margin notes
- Tables that exceed five columns
- Anything you'd otherwise simulate with ASCII art, unicode block characters,
  or "imagine this rendered as…"

If the user explicitly says "HTML", "artifact", "single file", "self-contained",
"interactive", or names one of the artifact kinds in this skill's `description`,
this skill is the right tool.

If the answer is ten lines of prose, just write Markdown.

## The workflow

```
1. List         python scripts/build.py list
2. Describe     python scripts/build.py describe <template>
3. Compose      write a JSON spec containing only your content + parameters
4. Build        python scripts/build.py build <template> --spec spec.json --out artifact.html
```

Steps 1 and 2 are progressive-disclosure cheaper than reading
`references/templates.md`. Read the reference only when picking among many
templates or when the spec for one template needs more than the `describe`
output gives you.

## Templates

| Template | When to use |
|---|---|
| `exploration.comparison_grid` | 2–4 options to weigh: pros/cons/tags side-by-side. |
| `exploration.design_directions` | Visual direction options with palette + type samples. |
| `exploration.implementation_plan` | Milestones + risks + a small flow sketch. |
| `review.pr_review` | PR review writeup with per-file findings + severity. |
| `review.code_walkthrough` | Numbered walkthrough of code with snippets and prose. |
| `review.module_map` | SVG box-and-arrow map of modules / dependencies. |
| `design.design_system` | Color, typography, spacing, radius reference. |
| `design.component_variants` | Grid of component states by axis (size × intent etc). |
| `prototype.animation_sandbox` | Live-tunable parameters driving a CSS-var preview. |
| `prototype.click_flow` | Sequence of mockup screens connected by arrows. |
| `diagram.svg_figure_sheet` | Page of standalone SVG figures with captions. |
| `diagram.flowchart` | Vertical/horizontal flowchart with labelled branches. |
| `deck.slide_deck` | Single-file deck, arrow-key + space navigation, snap-scroll. |
| `research.feature_explainer` | TOC + sections + tabbed code samples per section. |
| `research.concept_explainer` | Concept doc with collapsibles + glossary. |
| `report.status_report` | KPIs + shipped / in-flight / blocked. |
| `report.incident_report` | Severity header + minute-by-minute timeline + follow-ups. |
| `editor.triage_board` | Drag-and-drop kanban for items across columns. |
| `editor.flag_editor` | Toggle editor for boolean flags with dependency warnings. |
| `editor.prompt_tuner` | Edit `{{variable}}` values, see live-rendered prompt. |
| `freeform` | Anything else: page shell + your own inner HTML. |

For full per-template parameter specs, see `references/templates.md`.
For the design tokens you can reference inside any custom HTML
(`var(--clay)`, `.badge--ok`, etc.), see `references/palette.md`.

## Progressive-disclosure rules

These exist to keep your output tokens spent on **content**, not chrome:

1. **Never write `<html>`, `<head>`, `<style>`, `<script>`, or `<link>`
   yourself.** The composer adds them. If you find yourself writing a
   complete page, you missed the skill.
2. **Don't restate design tokens.** `--clay`, `--ivory`, `--slate`,
   `.card`, `.badge--warn`, etc. are already loaded. Reuse them.
3. **Use `freeform` only when no other template fits.** Templates are
   parameterized for a reason — they encode dozens of layout decisions
   you'd otherwise re-derive every time.
4. **For templated outputs, write only the parameters.** A
   `report.status_report` spec is metrics + items; a `deck.slide_deck`
   spec is just the slide list.
5. **One artifact per build.** Don't try to fold ten unrelated views
   into one HTML file — the user can tab between two browser windows.

## Iteration

Iterate by editing the spec and re-running `build`. Open the file with
`xdg-open` / `open` to preview. Adjust the spec; re-render. Don't dive into
the generated HTML; if a layout decision can't be expressed in the spec,
the template needs to grow a parameter (worth doing) — not the artifact
needs to grow inline overrides.

## What the composer guarantees

Every artifact ends up with:

- A consistent design system: ivory/clay palette, serif headlines, sans
  body, mono accents — matching Thariq's HTML-effectiveness reference.
- Inline base CSS + JS — no network, no fonts to load, no broken offline.
- A semantic masthead (eyebrow + h1 + subtitle) and a small colophon.
- Working defaults for tabs, collapsible `<details>`, copy-to-clipboard
  on `<pre>`, drag-to-reorder lists, deck arrow-key nav, and live
  parameter bindings via `[data-bind]` / `[data-out]`.
- HTML escaping on every value the spec passes through `c.esc()` — keys
  named `_html` (e.g. `body_html`, `summary_html`) are passed through
  verbatim and are your responsibility.

## Output location

By default, write artifacts to `/home/claude/` (or `/tmp/` if that
doesn't exist). On Claude Code on the Web, paths under
`/mnt/user-data/outputs/` are surfaced to the user as downloadable links.

```bash
python scripts/build.py build report.status_report \
  --spec spec.json \
  --out /mnt/user-data/outputs/status-may-9.html
```

## Acknowledgement

Inspired by Thariq Shihipar's
[The unreasonable effectiveness of HTML](https://thariqs.github.io/html-effectiveness/),
which argues that HTML is the right output format for many tasks where
agents currently default to Markdown. Thariq specifically said he didn't
want a `/html` skill written. This skill exists anyway, and tries to
honor the spirit of his argument: keep the friction low, the chrome out
of your way, and your tokens spent on content — not boilerplate.
