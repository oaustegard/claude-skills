# atprotoing

Read Bluesky/ATProto without depending on Bluesky's AppView.

## Why

On 2026-08-16 the Bluesky AppView (`public.api.bsky.app`) timed out and
Jetstream returned 503 or went silent, while PDSes, `plc.directory`, and
Constellation served every request. Measured during the outage:

```
ok   PDS entryway                   283ms
ok   PDS cordyceps.us-west...       665ms
ok   PLC directory                   58ms
ok   Constellation                 2690ms
DOWN AppView                      12627ms  TimeoutError
```

ATProto is decentralized in protocol but centralized in deployment — one relay
of consequence, essentially one AppView. Anything routed through the AppView
inherits that single point of failure. `browsing-bluesky` hardcodes
`BASE = "https://api.bsky.app/xrpc"` and was unusable for the duration.

This skill treats the AppView as one source among several rather than the only
one. It is a backup for outages, a cheap way to pull live context the rest of
the time, and a demonstration that the federated layer holds when the
centralized layer does not.

## Source model

Every read declares *what* it needs; the resolver picks a *source* that
survives independently.

| Need | Source | Notes |
|---|---|---|
| Records of a known repo | That repo's PDS | Authoritative; no outage observed |
| Who liked/replied/quoted/reposted a URI | Constellation | Network-wide backlink index |
| handle ↔ DID ↔ PDS location | `plc.directory`, entryway `resolveHandle` | No DNS dependency |
| Search, feed generators, chat | AppView | **No substitute — the tool says so** |

Constellation (`constellation.microcosm.blue`) is the persistent index. Building
a local one was the wrong instinct: it already indexes the whole network, is
operated independently of Bluesky PLC, and is up when the AppView is not.

## Usage

```bash
python3 scripts/atproto.py <command> [--json]
```

Digest output is the default. `--json` emits raw structures and is for
programmatic transformation — putting raw records back into a transcript
defeats the purpose.

### Commands

```bash
# Which layer is actually broken
atproto.py status --actor austegard.com

# Who interacted with my recent posts
atproto.py interactions austegard.com --hours 8 --scan 100

# Replies to a post, assembled from each replier's own PDS
atproto.py thread at://did:plc:.../app.bsky.feed.post/3mt74kftcvc22

# An actor's posts, read from their PDS
atproto.py posts ayourtch.bsky.social --limit 5

# Any collection in any repo
atproto.py records austegard.com app.bsky.graph.follow --json

# DID, handle, PDS host
atproto.py resolve austegard.com
```

### Library

```python
from atprotoing import interactions, records, resolve, status, thread, Unavailable

me = resolve("austegard.com")            # {did, handle, pds}
posts = records(me["did"], "app.bsky.feed.post", limit=25)
rows = interactions("austegard.com", since_hours=8)
```

## Cost shape

State is a `/tmp` SQLite scratch (relocate with `ATPROTO_CACHE`), session-scoped
by design. Cold start is the only start, and that is fine: **wall-clock cost and
token cost are decoupled.** The script absorbs the HTTP fan-out and returns a
digest.

Measured — `interactions --hours 8` over 100 posts:

| | tool calls | wall clock | output |
|---|---|---|---|
| By hand | ~15 | — | thousands of tokens of intermediate JSON |
| This skill | 1 | 19s | ~30 lines |

`interactions` is two-phase deliberately: one cheap `links/all` per post reports
which link paths are non-empty, so the expensive per-path enumeration runs only
where something exists. Preserve that when extending.

## Network requirements

Core stack, all required:

- `https://bsky.social` — entryway; handle resolution, health
- `https://*.host.bsky.network` — PDSes (97.1% of a measured 854-account follow graph)
- `https://plc.directory` — DID documents
- `https://constellation.microcosm.blue` — backlink index
- `https://public.api.bsky.app` — AppView; optional, `status` only

Third-party PDSes host the remaining ~2.9% and are **not** covered by a
wildcard. Measured across one follow graph: `eurosky.social` (12),
`blacksky.app` (2), `atproto.brid.gy` (2), plus eight personal PDSes. Reads
against an unlisted host fail with the host named:

```
unavailable: egress blocked: pds.nicoritschel.com
```

Add such hosts to your environment's egress settings. This list grows as
federation succeeds, so treat it as maintenance rather than one-time setup.

## Known limits

- **`--scan` bounds the window.** Only the N most recent posts are checked for
  interactions. Fine for hours; raise it for longer spans.
- **Times come from TIDs**, decoded from the record key rather than fetched.
  TIDs are client-generated: good for ordering, not attestation.
- **Constellation freshness is unverifiable from outside.** It ingests from the
  relay, so during a relay outage an empty result may mean "no interactions" or
  "not yet indexed." The tool cannot distinguish these.
- **No search, feed generators, or chat.** These are AppView-native and have no
  federated substitute today.

## Writing

This skill reads. For posting, `muninn_utils.bsky_card` writes straight to the
PDS (facets, blobs, embeds, sessions) and therefore works during an AppView
outage; `muninn_utils.bsky_limit` enforces the 300-grapheme cap, which `len()`
gets wrong on emoji and combining marks.

## Related skills

- `browsing-bluesky` — richer reads (search, feeds, trending, firehose
  sampling), all via the AppView. Use it when the AppView is healthy and you
  need what only it provides; use this when it is not.
- `categorizing-bsky-accounts` — account analysis over follow graphs.

## Version

0.1.0
