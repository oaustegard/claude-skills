---
name: atprotoing
description: Read Bluesky/ATProto without depending on Bluesky's AppView — interactions on a user's posts, thread replies, any repo's records, network-wide backlinks across every lexicon, an account's handle and PDS history, which collections are active network-wide, and layer-by-layer outage diagnosis. Use when bsky.app or the AppView is down or slow, when a Bluesky read returns timeouts or 5xx, when asked who liked/replied/quoted/reposted something, when pulling live Bluesky context cheaply, when reading records straight from a PDS, when asked who references a record or account anywhere on the network, whether an account has changed handle or migrated servers, or which lexicons and non-Bluesky apps are active on atproto. Complements browsing-bluesky, which routes everything through the AppView and fails when it does.
metadata:
  version: 0.3.0
---

# ATProtoing

Reads the atmosphere from sources that stay up when Bluesky PLC's AppView does
not. On 2026-08-16 the AppView timed out and Jetstream returned 503 while PDSes
and Constellation served every request — this skill is built around that split.

## Invoke

```bash
python3 <skill>/scripts/atproto.py <command> [--json]
```

Digest output is the default and is what belongs in a transcript. Reach for
`--json` only when the result will be transformed programmatically; raw records
are large and re-reading them into context defeats the purpose.

| Command | Answers |
|---|---|
| `feed [actor] [--hours 3] [--html PATH]` | The Following timeline, threaded |
| `status [--actor X]` | Which layer is broken right now |
| `interactions <actor> [--hours 8] [--scan 100]` | Who liked/replied/reposted/quoted recent posts |
| `thread <at-uri>` | Replies to a post |
| `posts <actor> [--limit]` | An actor's posts, from their own PDS |
| `records <actor> <collection>` | Any collection in any repo |
| `resolve <actor>` | DID, handle, PDS host |
| `backlinks <target> [--collection C --path P]` | What references a record or account, in ANY lexicon |
| `identity <actor>` | Handle renames and PDS migrations, from the PLC audit log |
| `lexicons [query] [--hours N] [--others] [--schema NSID]` | Which collections are active network-wide |

## Source model

Each read targets the cheapest source that survives independently. Prefer the
PDS for anything a repo owns — it is authoritative and had no outage.

| Need | Source |
|---|---|
| Records of a known repo | That repo's PDS |
| Who interacted with a URI | Constellation (`constellation.microcosm.blue`) |
| handle ↔ DID ↔ PDS, and its history | `plc.directory`, entryway `resolveHandle` |
| Which collections are active network-wide | UFOs (`ufos-api.microcosm.blue`) |
| Search, feed generators, chat | AppView only — **no substitute; say so** |

`feed` is the one composite read: there is no AppView-free `getTimeline`, so it
rebuilds the Following timeline from follows → PLC → each followee's PDS, then
hydrates what the AppView would have inlined — facet byte-ranges to character
ranges, blob CIDs to `cdn.bsky.app` URLs, quote and parent URIs to fetched
records — and threads the result by reply root. `--html` writes a self-contained
Preact reader (same components as `austegard.com/bsky/thread-reader.html`), so a
feed request is **one call**, not a fan-out the caller re-derives by hand.
Ranking, mutes, and blocks live in the AppView and are absent by construction:
this is the raw follow graph.

Constellation is the persistent index. Do not rebuild one locally: it already
indexes the whole network, is operated independently of Bluesky PLC, and is
reachable when the AppView is not.

`interactions` walks the five Bluesky paths in `LINK_PATHS`. `backlinks` walks
whatever Constellation has indexed — tangled issues, vouches, list membership,
lexicons nobody here has heard of — so reach for it when the question is "who
references this, anywhere" rather than "who liked this post". Both are
two-phase for the same reason: `links/all` reports which sources are non-empty,
and only then does enumeration cost anything.

`lexicons` answers a different question from `sample_firehose` in
`browsing-bluesky`: UFOs consumes Jetstream and rolls it up per NSID, so a
single call reports what is running across the whole network without sampling
anything here. `--others` drops `app.bsky.`, `chat.bsky.` and `com.atproto.`,
which is what turns the leaderboard from "Bluesky is large" into a list of the
other apps. `--schema NSID` fetches the published lexicon document from the
publisher's own repo, deriving the publisher by the reverse-DNS convention
(`com.whtwnd.blog.entry` → `whtwnd.com`); publishing that record is optional and
plenty of busy collections skip it, so a miss is a fact about the publisher, not
a failure.

## Cost shape

State is a `/tmp` SQLite scratch (`ATPROTO_CACHE` to relocate), session-scoped
by design. Cold start is the only start, and that is fine because **wall-clock
and token cost are decoupled** — the script absorbs the HTTP fan-out and returns
a digest. Measured: `interactions --hours 8` over 100 posts ≈ 18s and ~30 output
lines, against ~15 tool calls doing it by hand.

`interactions` is two-phase on purpose: one cheap `links/all` per post reports
which link paths are non-empty, so per-path enumeration only runs where
something exists. Preserve that when extending.

## Handling failure

`Unavailable` is raised for egress blocks, 4xx, and exhausted retries; the CLI
exits 2 with the reason on stderr. Report which layer failed rather than
retrying blindly — "the AppView is down" and "atproto is down" are different
facts and the distinction is usually the answer the user wants.

Two known limits worth stating plainly when they bite:

- **Third-party PDSes may be egress-blocked.** ~3% of a typical follow graph
  self-hosts (eurosky.social, blacksky.app, personal PDSes). Those reads fail
  with a clear allowlist message; add the host to project egress settings.
- **Times come from TIDs**, decoded from the record key rather than fetched.
  Client-generated, so treat them as approximate ordering, not attestation.

## Overlap with the Atmosphere MCP

`aturi.to/api/mcp` (hosted, keyless, read-only, beta) covers the same three
areas and about 30 more. It was measured on 2026-08-28 at 38 tools / ~8.6k
tokens of schema resident per session, returning pretty-printed JSON rather
than digests, with every read routed through one host. These commands go
straight to plc.directory, Constellation and UFOs, which is the point of this
skill — the 2026-08-16 split is exactly the case a single upstream reintroduces.
Use the MCP for what it alone has: the waypoint catalog and the atproto docs
search. Do not route these three through it.

## Writing

This skill reads. For posting, use `muninn_utils.bsky_card` — it already writes
straight to the PDS (facets, blobs, embeds, `create_session`) and therefore
works during an AppView outage. `muninn_utils.bsky_limit` enforces the
300-grapheme cap, which `len()` gets wrong on emoji and combining marks.
