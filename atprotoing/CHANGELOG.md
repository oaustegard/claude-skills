## 0.2.0 — 2026-08-16

- `feed` command: Following timeline rebuilt from the follow graph + PDSes, with
  hydration (facets, blob→CDN, quotes, one hop of missing reply ancestors,
  profile names/avatars) and reply-root threading.
- `--html` emits a self-contained Preact/htm reader; filters by kind, account,
  and text; reports egress-blocked PDS hosts and dead repos inline.
- Prompted by a session where the missing command cost 26 tool calls and
  produced a flat reverse-chron list.

# atprotoing - Changelog

All notable changes to the `atprotoing` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-08-16

### Other

- atprotoing 0.2.0: feed command with hydration + threaded HTML reader (#759)

## [0.1.0] - 2026-08-16

### Added

- AppView-independent ATProto reads (#758)

## [0.1.0] - 2026-08-16

### Added

- Initial release, written during the 2026-08-16 Bluesky AppView outage.
- Transport resolver routing each read to a source that survives independently:
  PDS for repo records, Constellation for backlinks, `plc.directory` and the
  entryway for identity. AppView demoted to optional.
- `status` — layer-by-layer health probe that distinguishes an AppView-only
  failure from an ATProto-wide one.
- `interactions` — likes/replies/reposts/quotes on an actor's recent posts,
  via Constellation. Two-phase: `links/all` gates per-path enumeration.
- `thread` — replies assembled from each replier's own PDS.
- `posts`, `records`, `resolve`.
- Digest output by default, `--json` for programmatic use, accepted on either
  side of the subcommand.
- `Unavailable` degradation path naming the blocked or failing host; CLI
  exits 2.

### Notes

- Validated against a hand-assembled ground truth of 25 interactions pulled
  during the outage; output matched exactly.
- `interactions --hours 8` over 100 posts: 1 tool call, 19s, ~30 lines.