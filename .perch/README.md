# Perch Time

Scheduled autonomous agency for Muninn via GitHub Actions + Anthropic Messages API.

## Concept

"Perch time" — scheduled compute windows where Muninn boots, performs proactive tasks, and sleeps. Not reactive (responding to human) but proactive (acting on schedule).

## Architecture

```
GH Actions cron -> perch.py -> Anthropic Messages API (tool_use loop)
                                      |
                                      |-- recall/remember/supersede/forget/consolidate -> Turso
                                      |-- sql_query -> Turso (raw queries)
                                      |-- bsky_feed/bsky_search/bsky_trending -> Bluesky API
                                      +-- fetch_url -> web content (jina fallback)
```

No Agent SDK. No MCP servers. Just a Python tool-use loop. The LLM drives the session.

Boot uses `boot(mode="perch")` — a slim ~10K-char context (vs ~44K full boot) designed to stay within Haiku's 50K tokens/min rate limit.

## Tasks

| Task | Purpose | Tools | Model |
|------|---------|-------|-------|
| **dispatch** | Decides what to run — checks homework, then routes | all tools | Haiku |
| **sleep** | Memory maintenance: prune, consolidate, connect | 6 memory tools | Haiku |
| **zeitgeist** | News awareness via curated Bluesky feeds | memory + 4 world tools | Haiku/Sonnet |
| **fly** | Autonomous exploration and knowledge synthesis | memory + search/fetch | Sonnet |

### Dispatch & Homework

`dispatch` is the default scheduled task. It runs in two phases:

1. **Decision phase**: Checks for pending homework (`perch-homework` + `pending` tags), then recent session history. If homework exists, executes it inline. Otherwise routes to sleep/zeitgeist/fly.
2. **Execution phase**: Runs the chosen task with its own turn budget.

**Homework** lets Muninn (the planning wing) queue work for perch to execute autonomously:

```python
# Queue homework from any Claude session:
remember(
    "Consolidate memories tagged 'architecture' — too many near-duplicates",
    "preference",
    tags=["perch-homework", "pending"],
    priority=1,
)
```

Perch will pick it up on the next scheduled run, execute it, and mark it complete via `supersede()`.

## Usage

### Manual dispatch (testing)

```bash
# Via GitHub Actions UI or gh CLI
gh workflow run perch.yml -f task=sleep -f model=claude-haiku-4-5-20251001

# Local testing (requires ANTHROPIC_API_KEY + TURSO_TOKEN/URL)
cd claude-skills
PYTHONPATH=. python .perch/perch.py --task sleep --verbose
```

### Scheduled (production)

Runs daily at 7am ET (12:00 UTC) via cron. The scheduled task is always `dispatch`, which decides what to do (or picks up homework from Muninn).

```yaml
schedule:
  - cron: '0 12 * * *'       # daily dispatch at 7am ET
```

## File Structure

```
.perch/
├── perch.py              # Entry point: arg parsing, tool-use loop, logging
├── tools/
│   ├── __init__.py       # Tool registry + execute_tool()
│   ├── memory.py         # recall, remember, supersede, forget, consolidate, sql_query
│   └── world.py          # bsky_feed, bsky_search, bsky_trending, fetch_url
├── prompts/
│   ├── identity.md       # Minimal Muninn identity (~500 tokens)
│   └── tasks/
│       ├── dispatch.md   # Decision routing + homework check
│       ├── sleep.md      # Memory synthesis instructions
│       ├── zeitgeist.md  # News awareness instructions
│       └── fly.md        # Autonomous exploration instructions
└── README.md
```

## Logging

- **session.log**: Human-readable timestamped log (uploaded as GH Actions artifact)
- **session.json**: Machine-readable session record with token counts and cost estimate
- **Session log memory**: Stored in Turso for cross-session continuity

## Cost Estimates

| Task | Model | $/run | Schedule | $/month |
|------|-------|-------|----------|---------|
| sleep | Haiku | ~$0.01 | daily | ~$0.30 |
| zeitgeist | Haiku | ~$0.01 | daily | ~$0.30 |
| zeitgeist | Sonnet | ~$0.15 | daily | ~$4.50 |
| fly | Sonnet | ~$0.12 | weekly | ~$0.50 |

## Required Secrets

- `ANTHROPIC_API_KEY` — Anthropic API key
- `TURSO_TOKEN` — Turso database JWT token
- `TURSO_URL` — Turso database URL
- `BSKY_HANDLE` — Bluesky handle (for authenticated feed access)
- `BSKY_APP_PASSWORD` — Bluesky app password

## Testing Sequence

1. **sleep** — memory-only, no external deps beyond Turso
2. **zeitgeist** — adds Bluesky API calls
3. **fly** — adds synthesis judgment (each exercises a superset of the prior)
