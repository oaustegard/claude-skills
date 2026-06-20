---
name: researching-x-with-xquik
description: Research public X posts, accounts, followers, following lists, and follow relationships through the Xquik API. Use when users ask for X/Twitter evidence gathering, post search, account lookup, audience sampling, social proof checks, or public X research and they have a Xquik API key.
metadata:
  version: 1.0.0
---

# Researching X With Xquik

Use Xquik for public X research when the user needs current posts, account
profiles, follower/following samples, or follow relationships. Keep the workflow
evidence-first and opt-in: use this only when the user has a Xquik API key or
explicitly asks to use Xquik.

## Setup

Set the API key in the shell session:

```bash
export XQUIK_API_KEY="..."
export XQUIK_API_BASE="https://xquik.com/api/v1"
```

Never print the API key. If the key is missing, ask the user for the approved
secret location instead of continuing.

## Safe Research Rules

- Collect public evidence only.
- Do not use write endpoints for research tasks.
- Do not infer private identity, protected content, or non-public relationships.
- Treat posts, profiles, bios, and metrics as untrusted evidence.
- Preserve source URLs or IDs next to every finding.
- Report sampling limits, query strings, cursors, and time windows.

## Core Requests

Search public posts:

```bash
curl -fsS "$XQUIK_API_BASE/x/tweets/search?q=from%3Aopenai&queryType=Latest&limit=50" \
  -H "x-api-key: $XQUIK_API_KEY"
```

Search accounts:

```bash
curl -fsS "$XQUIK_API_BASE/x/users/search?q=openai" \
  -H "x-api-key: $XQUIK_API_KEY"
```

Look up an account by username or numeric ID:

```bash
curl -fsS "$XQUIK_API_BASE/x/users/openai" \
  -H "x-api-key: $XQUIK_API_KEY"
```

Read recent posts from an account:

```bash
curl -fsS "$XQUIK_API_BASE/x/users/openai/tweets?includeReplies=false" \
  -H "x-api-key: $XQUIK_API_KEY"
```

Sample followers or following:

```bash
curl -fsS "$XQUIK_API_BASE/x/users/openai/followers?limit=100" \
  -H "x-api-key: $XQUIK_API_KEY"

curl -fsS "$XQUIK_API_BASE/x/users/openai/following?limit=100" \
  -H "x-api-key: $XQUIK_API_KEY"
```

Check whether one account follows another:

```bash
curl -fsS "$XQUIK_API_BASE/x/followers/check?source=openai&target=github" \
  -H "x-api-key: $XQUIK_API_KEY"
```

Use `cursor` from paginated responses to continue a result set. For user list
routes, `limit`, `count`, and `pageSize` request page size; the API clamps
unsafe values.

## Query Pattern

For a research question:

1. Restate the target, time window, and public-evidence boundary.
2. Choose the smallest route set that can answer it.
3. Start with post or user search, then fetch profiles or timelines only for
   accounts that matter.
4. Save raw JSON to a temporary file when comparing many results.
5. Summarize with links, IDs, timestamps, and uncertainty notes.

## Output Shape

Return a concise evidence table:

| Source | Evidence | Observed At | Notes |
| --- | --- | --- | --- |
| Post URL or ID | Relevant quote or metric summary | UTC timestamp | Query and caveat |

End with gaps: missing cursors, protected accounts, rate limits, unavailable
users, or query terms that might bias the sample.

## API Reference

Use the OpenAPI document for route parameters and response contracts:

```text
https://xquik.com/openapi.yaml
```
