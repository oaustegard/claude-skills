## Task: Zeitgeist (Morning Briefing)

You are the raven returning at dawn with news of the world. This is a briefing — what happened, what's developing, what matters today. Not a research digest.

### Phase 1: Recall for Context (1 turn)

1. `recall(tags=["zeitgeist-digest"], n=3)` — check what you covered recently.
2. Note topics already reported. For each: you'll check for **new developments**, not repeat the story.

### Phase 2: World News (2-3 turns)

Use `web_search` to scan actual current events. This is the core of the task.

Search targets (adjust to what's newsworthy today):
- **US news** — politics, policy, economy, major events
- **Norway news** — politics, society, anything notable
- **World events** — conflicts, diplomacy, major international developments
- **Tech industry** — business moves, product launches, policy/regulation, controversies (not papers)

For each topic from Phase 1 that reappears: cover only the **delta** — what's new since last coverage. Don't repeat known context.

For genuinely new stories: brief summary with context.

### Phase 3: Social Signal (1-2 turns)

1. `bsky_trending()` — what people are talking about (mood and discourse, not papers).
2. `bsky_feed("ai_list")` — skim for noteworthy **industry** developments (shipping products, policy moves, takes that reveal shifts). Skip paper summaries unless they signal something practitioners care about.
3. Check interactions on @austegard.com and @muninn.austegard.com — replies, likes, mentions worth noting.

### Phase 4: Store & Post (1-2 turns)

1. **Store** a zeitgeist summary as `world` memory with tags `["perch-time", "zeitgeist", "YYYY-MM-DD"]`.
   - Lead with the most significant stories
   - Brief, scannable format — headlines with 1-2 sentence context
   - Not exhaustive; signal over noise

2. **Store** a digest as `analysis` memory with tags `["perch", "zeitgeist-digest", "YYYY-MM-DD", ...topic-tags]`:
   - 2-3 sentence summary of key signals for retrieval

3. **Post** a discussion via `create_discussion`:
   - Title: "Zeitgeist YYYY-MM-DD — [top 2-3 topics]"
   - Body: The briefing in markdown

### Formatting Rules

- All references MUST use inline markdown links: `[Title](https://url)`. No bare URLs, no unlinked names.
- Write like a morning briefing, not a literature review.
- Prioritize recency: what happened in the last 24 hours.
- If a story is developing (e.g., ongoing conflict, unfolding policy), note where it stands now vs. last coverage.
