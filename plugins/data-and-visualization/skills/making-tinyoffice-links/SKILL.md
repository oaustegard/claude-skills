---
name: making-tinyoffice-links
description: Makes small documents as shareable Tiny Little Office links, where the URL itself is the document. Covers slide decks, posters, zines, spreadsheets, charts and small-business models, letters, résumés, invoices, outlines, diagrams (mind map, org chart, family tree, swimlanes, timeline, Venn, seating, network), drawings, pixel art, animations, calendars, Gantt schedules, trip maps and a calculator that shows its working. Use when someone wants such a document as a link they can open, edit and pass on rather than a file, or names tinylittleoffice / TLO.
metadata:
  version: 0.2.0
  upstream: https://github.com/aboard-io/tinylittleoffice/tree/main/skill/tinyoffice
---

# Making Tiny Little Office links

Tiny Little Office (tinylittleoffice.com) keeps a whole document in its URL fragment, after the `#`, which browsers never send to a server. You write the document as TLO text (Markdown plus a few additions), percent-encode it into a link and hand the link over. Whoever opens it gets an editor on their own copy, and the address bar updates after each edit to hold the new version.

## Procedure

1. **Pick the app** from the table below. Read only that app's reference file. It holds the shapes the app reads and one or two worked examples.
2. **Write the TLO** to a file in your scratchpad. Copy an example from the reference and change it rather than starting from nothing.
3. **Build the link** with the script, which packs the text the way the site does and runs the offline lint:
   ```bash
   python3 scripts/tlo.py link deck talk.tlo --title "My talk" --by "Muninn"
   ```
   It prints the URL on stdout, and findings and length warnings on stderr.
4. **Fix every finding** and rebuild. `python3 scripts/tlo.py read <url>` gives back the text any link holds, packed or plain, so you can edit a link you were sent.
5. **Deliver.** If the link is under 2,000 characters, give it as a Markdown link with a plain description. If it is longer, put the bare URL alone in a fenced code block. Chat renderers and some apps break or truncate long links, and the code block keeps it whole for copying. Say that the link is the document: an edit produces a new link, and anyone holding the link can read it.

The script makes the **packed form** the site itself shares: `#/v1/<app>/<flag><payload>`, the TLO deflated against TLO's frozen word dictionary, base64url with `~` for 62 and a `+` every 300 characters so messaging apps don't break it. It runs 35–50% shorter than the readable form. `--title` and `--by` go into the document's head. `--plain` gives the readable `/<app>/#title=…&doc=…` form instead, which the site also opens and packs on arrival.

## Apps

| App | Reference | For |
|---|---|---|
| `write` | [references/write.md](references/write.md) | Letters, memos, résumés, invoices, contracts, a table that adds up |
| `outline` | [references/outline.md](references/outline.md) | Nested ideas; the same tree can open as slides, a mind map or an org chart |
| `deck` | [references/deck.md](references/deck.md) | Slides, plus `format:` poster / zine / booklet / brochure / comic / badges |
| `sheet` | [references/sheet.md](references/sheet.md) | Tables with formulas, bar/line/pie/sankey charts, named-cell models |
| `calc` | [references/calc.md](references/calc.md) | Sums with names, unit conversion, y = f(x) graphs |
| `draw` | [references/draw.md](references/draw.md) | Boxes and arrows on an 8px grid; pixel art |
| `diagram` | [references/diagram.md](references/diagram.md) | `kind:` mind, org, family, lanes, timeline, venn, seating, net |
| `anim` | [references/anim.md](references/anim.md) | A drawing with keyframes |
| `cal` | [references/cal.md](references/cal.md) | Events, repeats, time zones; `view: gantt` for schedules |
| `trip` | [references/trip.md](references/trip.md) | Stops with lat/lon and notes on a map |

Load these only when needed. [references/api.md](references/api.md) covers file downloads (`view=pdf|pptx|xlsx|…`), encrypted short links, the JS API and npm CLI, password-sealed links and the official lint's full finding list. [references/editors.md](references/editors.md) lists keyboard shortcuts for driving the editors in a browser.

Routing: numbers go in `sheet`, quick arithmetic in `calc`, prose in `write`, a tree of notes in `outline`, anything presented in `deck`. A diagram lays itself out, so prefer `diagram` over `draw` whenever one of its kinds fits. Tasks over weeks go in `cal` with `view: gantt`.

## The URL

```
https://tinylittleoffice.com/<app>/#title=<title>&doc=<TLO, percent-encoded>
```

- Parameters go after `#`, never after `?`.
- Optional parameters: `by=` (who made it, an unverified claim), `view=` (`pdf`, `png`, `html`, `md`, `tlo`, the app's own formats such as `pptx`, `xlsx` or `ics`; `embed` for an iframe; `show` to open a deck presenting).
- A head line `app: sheet` lets `https://tinylittleoffice.com/#doc=…` work without the app in the path.
- Length: QR codes hold 2,953 characters. Encrypted short links hold up to 12,272 (see api.md). Past 2,000, some chat apps cut the link.

## TLO in one table

Write ordinary Markdown: headings, paragraphs, `- ` and `1. ` lists nested by **two spaces**, `- [ ]` tasks, `> ` quotes, pipe tables, `**bold**`, `*italic*`, `` `code` ``, `[words](url)`, and footnotes as `^[note]`. TLO adds the following:

| Write | Means |
|---|---|
| `---` / `key: value` / `---` at the top | The head: `title`, `by`, `theme`, `chart`, `kind`, `zone`, `format`… |
| `{#id .class key=value}` at line end | Attributes: `{.title}`, `{.two}`, `{due=2027-03-01}`, `{color=green every=week}` |
| `Price:money` in a table header | Typed column: `text number money percent date time check url rich long icon name option` |
| `~ A -> B: label` | A connection (`->`, `<-`, `<->`, `--`) |
| ```` ```sheet ```` … ```` ``` ```` | Another app's document embedded here (any of the ten ids) |
| `==hi==`, `++under++`, `:rocket:` | Highlight, underline, Lucide icon by name |

A `---` between blocks starts the next slide, page or card. Any table is a live spreadsheet. Nothing is fetched from the web: `![img](url)` renders as a plain link.

## Rules agents break

1. **Whitespace is content.** Nesting is two spaces per level, and a dropped space flattens the tree. Never hard-wrap a paragraph, because each line break is kept.
2. **One thing per slide.** A slide with a fence (chart, diagram, table) shows only that fence under its headline, and bullets on the same slide are dropped. Put the commentary in `> ` notes or on its own slide. A `{.title}` slide takes a line or two, not a list.
3. **Commas split lists.** In Venn and seating lists, "2,000 cases" becomes two things. Write 2000.
4. **Diagram things are short names.** Two to four words each. Connection ends must match a listed name exactly (the text before ` | `).
5. **Embed, don't link.** Put another document inside as a fence rather than linking to a second TLO URL.
6. **A link is a copy.** There is no shared live document. For a sign-up sheet or a form, tell people to send their edited link back. A short link is frozen once made.

## Verifying

`scripts/tlo.py lint` is an offline subset of the official checks: `fence-bullets`, `title-long`, `title-list`, `body-over`, `edge-end`, `edge-unused`, `net-colon`, `comma-number`, `label-long`, `doc-link` and `length`. It is fast and needs no network. It does not measure rendered text or evaluate formulas. When Node is available and running third-party npm code is acceptable, `npx tinylittleoffice lint <link>` and `measure` run the real layout code and also catch `formula-error`, `label-over` and exact overflow (see api.md).

If a finding persists, the fix is in the TLO, not the URL. Re-read the app's reference rule for that shape.
