<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# cal: a calendar, or a schedule

A list item per thing: `- 2027-03-01: Launch`, `- 2027-03-01 to 2027-03-03: Offsite`, `- 2027-03-10 09:00-10:30: Retro`. Attributes give a color and a repeat: `{color=green every=week times=6}` (or `until=2027-06-01`). The head may hold a time zone, `zone: America/New_York`; without one the times are read in the reader's own zone. It may say what a color stands for: `green: Sam`. `view: gantt` in the head draws the same items as a schedule: an item nested under another is part of it, `{done=40%}` is how far along it is, `- [x]` that it is done.

Family calendar:

```
---
title: The Okafor family
green: Sam
orange: Ana
blue: Everyone
---
- 2026-11-03 16:30-17:15: Swim lesson, Sam {color=green every=week times=10}
- 2026-11-04: Trash and recycling out tonight {every=week}
- 2026-11-05 18:30-20:00: Parent-teacher night, bring the reading log {color=blue}
- 2026-11-07 10:00-11:30: Soccer, under-10s home game {color=green every=week until=2026-12-12}
- 2026-11-09: Ana's birthday {color=orange every=year}
- 2026-11-12 08:40-09:20: Dentist, Dr. Patel, both kids {color=blue}
- 2026-11-21 to 2026-11-22: Grandma visits from Philadelphia {color=blue}
- 2026-11-26: Thanksgiving at Aunt Jo's, bring the pies {color=blue every=year}
- 2026-12-03 19:30-22:00: Book club at Jo's {color=orange every=month}
- 2026-12-23 to 2027-01-01: Winter break {color=green}
```

Project plan:

```
---
title: A website for Hollow Pine Coffee
view: gantt
---
- 2026-09-28 to 2026-10-09: Discovery
  - [x] 2026-09-28 to 2026-09-30: Interviews with the staff and six regulars
  - [x] 2026-10-01 to 2026-10-02: Analytics review
  - 2026-10-05 to 2026-10-09: Content audit {done=80%}
- 2026-10-12 to 2026-10-30: Design
  - 2026-10-12 to 2026-10-16: Wireframes
  - 2026-10-16: The logo chosen {color=red}
  - 2026-10-19 to 2026-10-30: Visual design
- 2026-11-02 to 2026-11-20: Build
  - 2026-11-02 to 2026-11-13: Pages and the menu {color=blue}
  - 2026-11-09 to 2026-11-13: Ordering ahead {color=blue}
  - 2026-11-16 to 2026-11-20: Testing on phones {color=blue}
- 2026-11-24: Launch {color=red}
```

Templates: Family calendar, School term, Bills and renewals, Volunteer schedule, Vacation planner, League schedule, Garden calendar, Content schedule, Editorial calendar, Training plan, Project plan, Conference agenda, Festival weekend. Its own files: `.ics`, `.csv`.
