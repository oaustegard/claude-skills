<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# deck: slides

A slide between each `---`. The headline is `## :icon-name: Headline`, its layout an attribute: `{.title}` (a title slide), `{.two}` (two columns, a paragraph `|` between them) or `{.icon}` (bullets beside one big icon). The words are `- ` bullets nested by two spaces; `> ` lines are speaker notes; a `^[footnote]` is shown at the foot of its slide; `` `code` `` between backticks is set in a monospace face (a command, a file's name). A fence named by any app's id (```` ```anim ````, `diagram`, `draw`, `trip`, `cal`, `sheet`, the lot) puts that document on the slide, drawn by its app: an animation moves, a sheet with `chart: bar` in its head is a chart. The head may hold `theme:` (`boardroom`, `ivory`, `midnight`, `graphite`; for fun `confetti`, `sunset`, `ocean`, `bubblegum`, `arcade`, `chalkboard`; plain otherwise) and `transition:` (`cut`, `slide`, `zoom`; a fade otherwise).

The rules, before they are broken: a slide with a fence (a chart, a diagram, a table) is the fence's, drawn alone under the headline: bullets on it are not drawn, so put them in the notes (`> ` lines) or on a slide of their own. A headline is a few words; a long one is set smaller, then cut after two lines. Bullets are set as large as they fit, down to 14px; more than that runs off the slide, so split it. Presenting reveals one bullet, or one item of a fenced document, per step; the notes show with N or the Notes button, and start hidden under a finger.

`format:` in the head makes the deck a thing to print and fold, a page between each `---`: `poster` (one page, as big as the page allows), `zine` (8 pages), `booklet` (8 to 20), `brochure` (6 panels), `comic` (a panel per bullet, `- :icon-name: What is said | caption`) or `badges` (a page per person, the name as the headline).

Status update:

```
---
theme: boardroom
---
## :calendar: Acme Inc. site: status {.title}

- Week of November 2, 2026 · Harbor Studio

---

## This week and next {.two}

- Done: the six pages sketched and agreed
- Done: words for home, about and contact
- Done: hosting set up, the old address kept

|

- Next: words for work, prices and news
- Next: photographs on Thursday morning, weather allowing
- Next: first build shown on Friday, November 13

> Left, what shipped; right, what is planned. Keep it to the facts.

---

## :warning: Risks

- The price list is still being decided by Acme: the prices page waits on it
- Thursday may rain: Saturday is the fallback for photographs

---

## :help: Asks

- Dee Okafor to send the final prices by Wednesday, November 11
- Someone from Acme at the Friday read-through, an hour
```

Poster:

```
---
format: poster
---
## :music: Open mic night {.title}

- Friday, November 13, 8 pm
- The Anchor, 14 Quay Street
- Free. Bring a song, a poem, or just your ears.
```

Templates: A talk, Status update, A proposal, A pitch, A lesson, Conference talk, Quarterly review, Workshop agenda, Product launch, Town-hall notice, Trivia night, Wedding slideshow, Zine, Recipe zine, Booklet, Concert program, Brochure, Farm brochure, Comic, Comic: the umbrella, Poster, Lost cat poster, Name badges, Conference badges. Its own files: `.pptx`, `.html`, `.zip`, `.gif`, `.webm`.
