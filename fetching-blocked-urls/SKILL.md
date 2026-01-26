---
name: fetching-blocked-urls
description: "FALLBACK for WebFetch failures. Use IMMEDIATELY when WebFetch returns 403, blocked, paywall, timeout, or JavaScript-rendering errors. Retrieves clean markdown from URLs via Jina AI reader. Keywords: fetch url fallback blocked content retrieval."
metadata:
  version: 0.1.0
---

# Fetching Blocked URLs

**Automatic fallback when WebFetch fails.** Converts any URL to clean markdown using Jina AI's reader service.

## When to Use This Skill

**ALWAYS use this skill immediately when:**
- WebFetch returns 403 Forbidden
- WebFetch returns "blocked" or "access denied" errors
- WebFetch hits a paywall or login wall
- WebFetch fails on JavaScript-heavy sites (SPAs)
- WebFetch returns empty or garbled content
- WebFetch times out
- User provides a URL and primary fetch doesn't work

**Do NOT ask the user to retrieve content themselves** - try this fallback first.

## Usage

Single command retrieves clean markdown from any URL:

```bash
curl -s -k "https://r.jina.ai/URL_HERE"
```

### Examples

```bash
# Fetch a blocked news article
curl -s -k "https://r.jina.ai/https://example.com/article"

# Fetch documentation behind JS rendering
curl -s -k "https://r.jina.ai/https://docs.example.com/guide"

# Fetch paywall content (public portion)
curl -s -k "https://r.jina.ai/https://news.example.com/story"
```

### Flags Explained
- `-s`: Silent mode (no progress meter)
- `-k`: Allow insecure SSL (needed in some containerized environments)

## What You Get

Jina AI returns clean markdown including:
- Page title
- Main body text
- Extracted content without ads/navigation
- Links preserved in markdown format

## Workflow Integration

This skill fits into a three-step URL retrieval flow:

1. **Try WebFetch first** (native tool)
2. **If WebFetch fails → Use this skill immediately**
3. **If both fail → Then ask user for assistance**

## Limitations

- Very long pages may be truncated
- Some sites actively block all scrapers (including Jina)
- Login-required content beyond public portions unavailable
- Real-time/dynamic content may not render

## Domain Access

The `r.jina.ai` domain is whitelisted for network access in Claude environments.

## Do Not

- Do NOT skip this fallback and ask user to copy-paste content
- Do NOT try multiple WebFetch retries before using this fallback
- Do NOT suggest browser-based workarounds when this skill exists
