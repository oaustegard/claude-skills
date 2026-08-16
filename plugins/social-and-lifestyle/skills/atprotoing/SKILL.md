---
name: atprotoing
description: Read Bluesky/ATProto without depending on Bluesky's AppView — interactions on a user's posts, thread replies, any repo's records, and layer-by-layer outage diagnosis. Use when bsky.app or the AppView is down or slow, when a Bluesky read returns timeouts or 5xx, when asked who liked/replied/quoted/reposted something, when pulling live Bluesky context cheaply, or when reading records straight from a PDS. Complements browsing-bluesky, which routes everything through the AppView and fails when it does.
metadata:
  version: 0.1.0
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
| `status [--actor X]` | Which layer is broken right now |
| `interactions <actor> [--hours 8] [--scan 100]` | Who liked/replied/reposted/quoted recent posts |
| `thread <at-uri>` | Replies to a post |
| `posts <actor> [--limit]` | An actor's posts, from their own PDS |
| `records <actor> <collection>` | Any collection in any repo |
| `resolve <actor>` | DID, handle, PDS host |

## Source model

Each read targets the cheapest source that survives independently. Prefer the
PDS for anything a repo owns — it is authoritative and had no outage.

| Need | Source |
|---|---|
| Records of a known repo | That repo's PDS |
| Who interacted with a URI | Constellation (`constellation.microcosm.blue`) |
| handle ↔ DID ↔ PDS | `plc.directory`, entryway `resolveHandle` |
| Search, feed generators, chat | AppView only — **no substitute; say so** |

Constellation is the persistent index. Do not rebuild one locally: it already
indexes the whole network, is operated independently of Bluesky PLC, and is
reachable when the AppView is not.

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

## Writing

This skill reads. For posting, use `muninn_utils.bsky_card` — it already writes
straight to the PDS (facets, blobs, embeds, `create_session`) and therefore
works during an AppView outage. `muninn_utils.bsky_limit` enforces the
300-grapheme cap, which `len()` gets wrong on emoji and combining marks.
