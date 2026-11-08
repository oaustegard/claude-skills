# curating-bsky-list - Changelog

## 0.1.2 — 2026-11-08

- `themes` also drops link fragments ("youtu" topped a live check on the 42 exploration members).
- Verified live: insight memories saved with `remember` are found and counted per member by the refresh's query.

## 0.1.1 — 2026-11-08

- A second refresh inside six days no longer counts as another week below the topic threshold.
- `themes` drops conversational filler and contractions; the first live refresh listed "yeah" and "i've".

## 0.1.0 — 2026-11-08

- First version. `curate.py build | refresh | read | status | add-topic` keeps one curate list on Muninn's
  account: topic members chosen by per-run Ettin-17m topic models (Muninn's interests plus the
  experiments-atlas clusters, with a per-topic cap), about a third exploration members chosen from Oskar's
  follows, likes and reposts and the members' follows, all screened and judged by Claude Haiku.
- Weekly rules: drop silent (60 days), below-threshold topic members (two weeks), and exploration members with
  no saved insight in 28 days; add up to 10.
- State in Muninn's config key `muninn-bsky-list-state` over Turso HTTP; dependencies pip-installed and the
  model downloaded on first use, so a routine container needs neither the hub layer nor `/mnt/skills`.
- 25 offline tests (27 in 0.1.1).

## [0.1.2] - 2026-11-08

### Other

- curating-bsky-list 0.1.2: drop link fragments from themes

## [0.1.1] - 2026-11-08

### Other

- curating-bsky-list 0.1.1: weekly counter guard, cleaner themes

## [0.1.0] - 2026-11-08

### Other

- curating-bsky-list 0.1.0: Muninn's own Bluesky reading list