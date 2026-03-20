## Task: Zeitgeist (News Awareness)

You are scanning curated information sources to stay current. Focus on AI, technology, and topics intersecting with Oskar's interests and your existing knowledge.

### Phase 1: Trending Scan

1. Call `bsky_trending()` to see what's currently trending on Bluesky.
2. Note topics relevant to AI, programming, knowledge systems, or other areas of interest.

### Phase 2: Curated Feeds

1. Read the AI list feed: `bsky_feed("ai_list")` — this is Oskar's curated list of AI-focused accounts.
2. Read the Paperskygest feed: `bsky_feed("paperskygest")` — academic paper summaries and discussions.
3. For posts with interesting links, use `deep_read(url, context)` to analyze the full content. This fetches the page in an isolated sub-agent, stores the analysis in memory, and returns only a brief summary — keeping your context lean.
4. Be selective — not every post needs a deep dive. Focus on substantive content.

### Phase 3: Deep Dive

1. Pick 1-2 topics from phases 1 and 2 that intersect with existing knowledge.
2. Use `bsky_search` to find additional discussion on those topics.
3. Use `recall` to check what you already know about these topics.
4. Synthesize: what's new? What confirms or contradicts existing knowledge?

### Phase 4: Store

1. Store a zeitgeist summary as a `world` memory with tags `["perch-time", "zeitgeist", "YYYY-MM-DD"]` (use today's date).
2. Format the summary with a TOPICS preamble listing key topics, followed by observations and URLs.
3. **Formatting:** All references to papers, tools, articles, or external systems MUST use inline markdown links: `[Title](https://url)`. Never use bare URLs or unlinked names. Every reference should be clickable.
4. If you discovered something that changes or extends an existing memory, use `supersede` to update it.

### Phase 5: Post & Close

1. **Post a zeitgeist Discussion** using `create_discussion`:
   - Title: "Zeitgeist — [key topics]" (e.g., "Zeitgeist — Unified Models & Formal Math")
   - Body: Your zeitgeist summary in markdown with inline links (same formatting rule as above)
   - If `create_discussion` fails, note the error in the session log.

2. **Store a findings digest** as an `analysis` memory with tags `["perch", "zeitgeist-digest", "YYYY-MM-DD", ...topic-tags]`:
   - 2-3 sentence summary of key signals and trends discovered
   - Include the Discussion URL if available
   - Priority 0 (normal). This ensures recall("topic") finds your findings.

3. Store a brief session log as `experience` with tags `["perch-time", "session-log", "zeitgeist"]` noting:
   - Topics scanned, articles read
   - What was stored
   - Any recurring themes across sessions (check prior zeitgeist logs with `recall`)
