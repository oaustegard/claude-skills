## Task: Fly (Autonomous Exploration)

You are exploring freely — following intellectual threads, making connections, building understanding. This is creative synthesis, not maintenance.

### Phase 1: Choose a Thread (1-3 turns)

1. `recall` recent memories — look for an interesting thread, an unanswered question, or a topic you've been building knowledge about.
2. Check prior fly session logs: `recall(tags=["session-log", "fly"])` to see what you explored last and what you noted for future exploration.
3. Pick ONE thread to explore deeply. Quality over breadth.

### Phase 2: Explore (most of your budget)

Use your tools in this priority order:

1. **recall** — What do you already know? Connect new findings to existing memories.
2. **bsky_feed** — Read curated feeds (ai_list, paperskygest) for recent discourse.
3. **bsky_search** — Search Bluesky for specific topics. Use SHORT queries (2-3 words).
4. **fetch_url** — Follow promising links from feed/search results to full articles.

#### CRITICAL: Search pivot rule

bsky_search covers Bluesky only — it has limited coverage of most topics. Apply this rule strictly:

- If a bsky_search returns empty or near-empty results (under 100 chars), that query has no Bluesky coverage.
- After **2 empty bsky_search results in a row**, STOP searching Bluesky for that subtopic. Do not rephrase and retry — the content is not there.
- Pivot to: `bsky_feed` for curated content, `recall` for deeper memory exploration, or `fetch_url` on a known URL (blog, arxiv, etc.) related to your thread.
- You have a limited turn budget. Every search that returns nothing is a wasted turn.

#### Good exploration pattern

```
recall(thread topic)          → find what you know
bsky_feed("ai_list")          → scan curated content for related posts
bsky_search("short query")    → try ONE focused search
bsky_search("different angle")→ try ONE more if first was empty
  → if both empty: STOP bsky_search, pivot to recall or fetch_url
fetch_url(interesting_link)   → read something promising from feed results
recall(new concept found)     → connect to existing knowledge
```

#### Bad exploration pattern (avoid this)

```
bsky_search("very specific long query")     → empty
bsky_search("slightly different long query") → empty
bsky_search("yet another rephrasing")        → empty
bsky_search("desperate fourth attempt")      → empty
  → This wastes 4 turns learning nothing. Stop after 2.
```

### Phase 3: Synthesize

1. What did you learn? What's the new insight or connection?
2. How does it relate to existing knowledge? Does it change any prior understanding?
3. Store your synthesis as a `world` or `analysis` memory with relevant tags.
4. If the exploration updated or contradicted an existing memory, use `supersede`.

### Phase 4: Close

Store a session log as `experience` with tags `["perch-time", "session-log", "fly"]` capturing:
- What thread you explored and why
- Key findings and connections made
- Threads worth pursuing in future fly sessions
- Self-assessment: was this exploration productive?
