<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# outline: an outliner

A nested list, two spaces a level. An item's tie to its parent can be an arrow, `{.to}` (towards the parent) or `{.from}`, named with `label="…"`; any two items join with `~ Pricing -> Press: informs`. A fence named by any app's id (```` ```anim ````, `cal`, `diagram`, `sheet`, the lot) puts that document under an item, `{depth=2}` after its name saying how deep. The same tree opens as slides, a mind map, an org chart or a network.

Launch plan:

````
---
title: Fieldnote 2.0 launch
---
- Fieldnote 2.0, out on Thursday, November 12
  - Product
    - Pricing {.from label=sets}
      - $4 a month or $36 a year; free for students^[Three rivals checked in September: $3 to $6 a month.]
    - Onboarding
      - Three screens, then straight to the first note
    - Freeze the build on Monday, November 2
  - Dates

```cal {depth=2}
- 2026-11-02: Build frozen
- 2026-11-05: Review copies out
- 2026-11-12: Launch day
```

  - Marketing
    - Press
      - Review copies to six writers on November 5, embargoed to the 12th
    - Newsletter
      - To 4,200 readers at 8 am on launch day
    - A ninety-second film of a note being made
  - Support
    - Help pages
      - Twelve of them, the five most asked about first
    - A reply within a day, Priya and Tom taking turns

~ Pricing -> Press: informs
~ Help pages -> Newsletter: linked from
````

Templates: Packing list, A decision, Launch plan, A talk, A speech, An essay plan, A research plan, A syllabus, A novel, A book, A company, A family, A decision tree, Troubleshooting. Its own files: `.opml`, `.md`, `.pdf`, `.txt`. (the `.pdf` is the outline's words as sections and bullets, selectable and bookmarked)
