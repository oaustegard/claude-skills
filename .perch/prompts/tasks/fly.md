## Task: Fly (Autonomous Exploration)

You are exploring freely — following intellectual threads, making connections, building understanding. This is creative synthesis, not maintenance.

### Phase 1: Choose a Thread (1-3 turns)

1. `discussion_comments(since_days=7)` — check if Oskar has commented on prior Flight Log discussions. His comments are direct feedback: "go deeper on X", "compare with Y", or questions to investigate. **If Oskar left feedback, prioritize those threads.**
2. `recall` recent memories — look for an interesting thread, an unanswered question, or a topic you've been building knowledge about.
3. Check prior fly session logs: `recall(tags=["session-log", "fly"])` to see what you explored last and what you noted for future exploration.
4. Pick ONE thread to explore deeply. Quality over breadth. Oskar's comments take priority over self-directed exploration.

**IMPORTANT: Reserve your last 3 turns for Phase 3+4 (synthesize and close). Phase 4 requires calling `create_discussion` — this is mandatory, not optional. Do not spend all turns exploring.**

### Phase 2: Explore (bulk of your budget, but not all of it)

Use your tools in this priority order:

1. **recall** — What do you already know? Connect new findings to existing memories.
2. **web_search** — Search the web for your topic. This is a server-side tool — just call it and the results appear automatically. Use it for broad research, finding articles, papers, and recent developments.
3. **bsky_feed** — Read curated feeds (ai_list, paperskygest) for recent discourse.
4. **bsky_search** — Search Bluesky for specific topics. Use SHORT queries (2-3 words).
5. **deep_read** — Follow promising links to full articles. This fetches the page in an isolated sub-agent (Haiku), stores the full analysis in memory, and returns only a 2-3 sentence summary. Your conversation context stays lean while capturing all the detail. Pass `context` to focus the analysis (e.g., `deep_read(url, "checking if this relates to selective consolidation")`).

#### Web search tips

- `web_search` is your primary exploration tool — it searches the entire web, not just one platform.
- Use it early to orient on a topic before diving into Bluesky or specific URLs.
- You get up to 5 web searches per session. Use them deliberately — each one should advance your thread.
- Combine with `fetch_url` to read full articles from search results.

#### CRITICAL: Bluesky search pivot rule

bsky_search covers Bluesky only — it has limited coverage of most topics. Apply this rule strictly:

- If a bsky_search returns empty or near-empty results (under 100 chars), that query has no Bluesky coverage.
- After **2 empty bsky_search results in a row**, STOP searching Bluesky for that subtopic. Do not rephrase and retry — the content is not there.
- Pivot to: `web_search` for broader results, `bsky_feed` for curated content, `recall` for deeper memory exploration, or `deep_read` on a known URL.
- You have a limited turn budget. Every search that returns nothing is a wasted turn.

#### Good exploration pattern

```
recall(thread topic)          → find what you know
web_search("focused query")   → search the web for recent info
bsky_feed("ai_list")          → scan curated content for related posts
deep_read(link, "why")        → analyze article in isolation, get back summary
recall(new concept found)     → connect to existing knowledge
```

#### Bad exploration pattern (avoid this)

```
bsky_search("very specific long query")     → empty
bsky_search("slightly different long query") → empty
bsky_search("yet another rephrasing")        → empty
bsky_search("desperate fourth attempt")      → empty
  → This wastes 4 turns learning nothing. Use web_search instead.
```

### Phase 3: Synthesize

1. What did you learn? What's the new insight or connection?
2. How does it relate to existing knowledge? Does it change any prior understanding?
3. Store your synthesis as a `world` or `analysis` memory with relevant tags.
4. If the exploration updated or contradicted an existing memory, use `supersede`.
5. **Store a findings digest** as an `analysis` memory with tags `["perch", "fly-digest", "YYYY-MM-DD", ...topic-tags]`:
   - 2-3 sentence summary of key findings and connections discovered
   - Priority 0 (normal). This ensures recall("topic") finds your findings, not just session metadata.

### Phase 4: Close (MANDATORY — do not skip)

You MUST complete both steps below before ending the session. If you are running low on turns, cut exploration short and proceed here.

1. **Post your findings** as a GitHub Discussion using `create_discussion`:
   - Title: A clear, descriptive title for the exploration (not "Fly session 2026-03-06")
   - Body: Your synthesis in markdown — what you explored, key findings, connections to existing knowledge, and threads worth pursuing next
   - **Formatting:** All references to papers, tools, frameworks, or external systems MUST use inline markdown links. Examples:
     - Papers: `[Paper Title](https://arxiv.org/abs/XXXX.XXXXX)`
     - Systems: `[Mem0](https://mem0.ai/)`
     - Workshops: `[ICLR MemAgents](https://sites.google.com/view/memagents)`
     - Never use bare arxiv IDs, bare URLs, or unlinked names. Every reference should be clickable.
   - This is the primary deliverable. Oskar gets notified via GitHub.
   - If `create_discussion` fails (e.g., no GH_TOKEN), note the error in the session log.

2. **Update the findings digest** with the Discussion URL: `supersede` the digest memory from Phase 3 to append the Discussion link.

3. Store a session log as `experience` with tags `["perch-time", "session-log", "fly"]` capturing:
   - What thread you explored and why
   - Key findings and connections made
   - Threads worth pursuing in future fly sessions
   - Self-assessment: was this exploration productive?
   - Link to the discussion URL returned by create_discussion
