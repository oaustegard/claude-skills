# composing-html

Compose single-file HTML artifacts without hand-writing page chrome. The composer supplies `<!DOCTYPE>`, `<head>`, inlined CSS, `base.js`, design tokens, masthead, and colophon. You supply the body.

The artifact is one file, no CDN, no build step, no server — the agent hands it over and it just opens.

## Inspiration

Thariq Shihipar's [*The Unreasonable Effectiveness of HTML*](https://claude.com/blog/using-claude-code-the-unreasonable-effectiveness-of-html) on the Anthropic blog argues HTML is the better artifact format than markdown for agent output: it carries tables, CSS, SVG, embedded code, live interactions, spatial layout, and images, and a single file is shareable and interactive in ways a markdown plan isn't. People will open and read an HTML file they wouldn't read as a hundred-line markdown plan.

The worry near the end of that piece is real, though: ask an agent for HTML and you tend to get either tasteful but generic Claude-aesthetic boilerplate, or an over-engineered SPA. This skill is the narrow defense — a fixed, opinionated chrome (typography, color tokens, layout primitives, base interactions) so the agent spends its output budget on the *content*, not on re-deriving what a card or a badge looks like for the hundredth time.

See [`SKILL.md`](SKILL.md) for the full inventory and workflow. See [`CHANGELOG.md`](CHANGELOG.md) for version history.

## Two workflows

### freeform — the default

Most artifacts. One slot — `body_html` — for the page body. Use `--set body_html=@body.html` so multi-line HTML, quotes, and `&`/`<` characters don't fight JSON-string escaping:

```sh
python scripts/build.py build freeform \
  --set title='My Page' \
  --set body_html=@body.html \
  --out artifact.html
```

`--set KEY=VALUE` assigns a literal string; `--set KEY=@FILE` loads file contents verbatim. Repeatable across all spec fields.

### templates — when the shape repeats

Twenty-one templates for recurring artifact shapes: PR reviews, status reports, incident postmortems, slide decks, design systems, flowcharts, kanban boards, prompt tuners, and more. Each has typed slots the template reasons over (`pr_review.findings[].severity`, `slide_deck.slides[].kind`).

```sh
python scripts/build.py list                                   # all templates
python scripts/build.py describe pr_review                     # required keys + JSON skeleton
python scripts/build.py build pr_review --spec spec.json --out review.html
```

Reach for a template only when the same artifact shape recurs across artifacts (same status report week after week, PR reviews across many PRs). For one-offs, `freeform` is less friction.

## What you get for free

| Layer | What it covers |
|---|---|
| **Tokens** | Color (`--clay`, `--slate`, `--ivory`, `--ok/warn/err/info`, gray ramp), typography (`--serif`, `--sans`, `--mono`), geometry (radii, borders, shadows) |
| **Layout** | `.page` / `.page--wide` / `.page--narrow`, `.grid--2|3|4`, `.stack`, `.row`, `.card`, `.rule` |
| **Components** | `.eyebrow`, `.badge--{ok,warn,err,info,clay}`, `.kbd`, `.bullets`, styled `<code>` / `<pre><code>` / `<details>` |
| **Interactions** | Tabs, drag-to-reorder (with cross-zone drops), live parameter bindings (`--bind-*` CSS variables driven by `<input>` + `data-bind`), auto copy buttons on every code block |
| **Chrome** | DOCTYPE, head, masthead (`eyebrow` + `<h1>` + subtitle), inlined CSS + JS, colophon |

Everything is inlined into the output file. Nothing fetches at view time.

## When to reach for it

- "Compare options side-by-side" → `exploration.comparison_grid`
- HTML version of a report or review → `report.status_report` or `review.pr_review`
- "Make me a deck" → `deck.slide_deck` (arrow-key + space navigation)
- Flowchart, module map, design system reference → `diagram.*`, `review.module_map`, `design.design_system`
- Prototype with live-tunable parameters → `prototype.animation_sandbox`
- "An HTML artifact" / "a single self-contained HTML file" → `freeform`

## When to skip

Ad-hoc HTML snippets that don't need page chrome — forms emailed inline, widgets embedded in someone else's page, three-line examples in a chat reply. The skill is the chrome; if you don't need the chrome, you don't need the skill.

## Pitfall to avoid

Inlining multi-line HTML into a JSON heredoc:

```sh
# ❌ This produces invalid JSON — strings can't contain raw newlines or unescaped quotes
cat > spec.json <<EOF
{ "body_html": "<section>
  <h2>Multi-line</h2>
</section>" }
EOF
```

Use `--set body_html=@body.html` instead, or assemble the spec in Python with `json.dump(spec, f)` so escaping is automatic.

## Tests

```sh
python tests/test_smoke.py            # no pytest required
python -m pytest tests -q             # with pytest
```

Covers every template with a representative spec plus explicit security regressions (HTML escaping, script-tag breakout, attribute injection, CSS-color injection, spec mutation) and the `--set` CLI paths.
