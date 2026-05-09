---
name: composing-html
description: Composes single-file HTML artifacts (PR review writeups, status reports, incident postmortems, slide decks, design systems, prototypes, flowcharts, module maps, feature explainers, kanban boards, prompt tuners) from a small JSON spec instead of hand-written HTML/CSS/JS. Use when the user asks to "compare options side-by-side", requests an HTML version of a report or review or deck, asks for a flowchart, status update, postmortem, design system reference, interactive prototype, custom editor — or explicitly says "HTML artifact", "single HTML file", "self-contained HTML". Skip for ad-hoc HTML snippets (forms, emails, embedded widgets) where there's no template fit.
metadata:
  version: 0.1.0
---

# composing-html

Produce single-file HTML artifacts by composing a small JSON spec, not by
hand-writing markup. Page chrome (head, design tokens, CSS, JS, masthead,
footer) lives in Python. Write only the parameters and the inner content.

## Workflow

```
1. python scripts/build.py list                    # see all templates
2. python scripts/build.py describe <template>     # required keys + JSON skeleton
3. write spec.json                                  # only your content + parameters
4. python scripts/build.py build <template> --spec spec.json --out artifact.html
```

`describe` prints a valid-JSON starter skeleton you can edit in place. For
worked examples, see `references/templates.md` — but only after picking a
template; reading it cold wastes context.

## Templates

Run `python scripts/build.py list` for the full list with one-line summaries.
There are 21, grouped into 9 categories plus a `freeform` escape hatch:

- `exploration.*` — comparison_grid, design_directions, implementation_plan
- `review.*`      — pr_review, code_walkthrough, module_map
- `design.*`      — design_system, component_variants
- `prototype.*`   — animation_sandbox, click_flow
- `diagram.*`     — svg_figure_sheet, flowchart
- `deck.*`        — slide_deck (arrow-key + space navigation)
- `research.*`    — feature_explainer, concept_explainer
- `report.*`      — status_report, incident_report
- `editor.*`      — triage_board, flag_editor, prompt_tuner
- `freeform`      — anything else: page shell + caller-supplied inner HTML

## Output rules

These exist to keep your output tokens spent on **content**, not chrome:

1. **Never write `<html>`, `<head>`, `<style>`, `<script>`, or `<link>`.** The
   composer adds all of them. If you find yourself writing a complete page,
   you missed the skill.
2. **Don't restate design tokens.** `var(--clay)`, `var(--ivory)`, `.card`,
   `.badge--warn`, `.bullets`, etc. are already loaded via inline CSS. Reuse
   them — see `references/palette.md` for the full inventory.
3. **For templated outputs, write only the parameters.** A `report.status_report`
   spec is metrics + items; a `deck.slide_deck` spec is the slide list.
4. **Reach for `freeform` only when no other template fits.** Templates encode
   layout decisions you'd otherwise re-derive every time.
5. **One artifact per build.** Don't fold ten unrelated views into one file —
   browser tabs are free.

## What you still write yourself

For templates with prose-heavy slots, a few keys take raw HTML — they end with
`_html` (e.g. `body_html`, `summary_html`, `intro_html`, `details_html`). For
these, write `<p>`, `<ul class="bullets">`, `<h2>`, etc. directly. The chrome
and design tokens are what's amortized; the prose is still yours. **Anything
in an `_html` field is inserted verbatim — escape user-supplied content
yourself.** All other string values are HTML-escaped automatically.

## Iteration

Edit the spec, re-run `build`, open in a browser. If a layout decision can't
be expressed in the spec, the template needs a new parameter — grow the
template, don't sprinkle inline CSS overrides into the artifact.

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
