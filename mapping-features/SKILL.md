---
name: mapping-features
description: Generate behavioral/feature documentation for brownfield web apps. Captures screenshots, accessibility trees, and behavioral invariants via browser automation, then synthesizes into _FEATURES.md. Companion to mapping-codebases. Use when documenting app behavior, creating feature inventories, generating behavioral ground truth for agents, or before modifying UI code. Triggers on "map features", "document app behavior", "feature inventory", "what does this app do".
metadata:
  version: 0.1.0
---

# Mapping Features

Generate `_FEATURES.md` files documenting what a web app *does* from the outside in — screens, flows, states, behavioral invariants. Companion to `mapping-codebases` which documents code *structure*.

## Prerequisites

1. **mapping-codebases** must have run first (`_MAP.md` files exist)
2. **webctl** installed and configured (see `using-webctl` skill)
3. **Claude API key** available (via `api-credentials` skill or `ANTHROPIC_API_KEY` env var)
4. A running instance of the target app (local dev server or deployed URL)

## Installation

```bash
pip install webctl --break-system-packages
webctl setup
# Apply proxy patch per using-webctl skill if in Claude.ai container
```

## Usage

```bash
python /mnt/skills/user/mapping-features/scripts/featuremap.py \
  --app-url https://example.com \
  --codebase /path/to/repo \
  --output /path/to/repo/_FEATURES.md
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--app-url` | required | Base URL of the running app |
| `--codebase` | required | Path to repo root (must contain `_MAP.md` files) |
| `--output` | `<codebase>/_FEATURES.md` | Output path for features doc |
| `--max-pages` | `20` | Cap on pages to discover before prompting |
| `--viewport` | `1280x720` | Screenshot viewport (WxH) |
| `--skip-describe` | `false` | Capture only, skip Claude vision step |
| `--incremental` | `false` | Only re-capture pages with changed screenshots |
| `--screenshots-dir` | `<codebase>/screenshots` | Where to store PNGs |

## Execution Phases

### Phase 1: DISCOVER
Reads `_MAP.md` + navigates app entry point via webctl. Crawls accessible routes by extracting nav links from accessibility snapshots. Builds a sitemap of reachable pages.

### Phase 2: CAPTURE
For each discovered page: takes a screenshot, captures the accessibility tree (interactive elements), and hashes the screenshot for staleness detection.

### Phase 3: DESCRIBE
Sends each screenshot + accessibility tree + relevant `_MAP.md` excerpts to Claude API (vision). Generates prose descriptions, interaction inventories, and behavioral invariants linked back to code.

### Phase 4: ASSEMBLE
Compiles all page descriptions into `_FEATURES.md` with screenshot references, code links, and a summary section suitable for CLAUDE.md injection.

## Auth / Gated Pages

Pages requiring authentication are marked `GATED` during Phase 1. The skill generates step-by-step instructions for manual capture:

```
GATED PAGES — Manual Capture Required:
1. Navigate to https://app.example.com/login
2. Sign in with your credentials
3. Navigate to /dashboard
4. Run: webctl screenshot --path screenshots/dashboard.png
5. Run: webctl snapshot --interactive-only > captures/dashboard-a11y.txt
```

After manual capture, re-run with `--incremental` to describe the new pages.

## Staleness Detection

Each run stores screenshot hashes in `_FEATURES_MANIFEST.json`. On re-run with `--incremental`, unchanged pages skip re-description. Changed pages are re-captured and re-described.

## Output Format

```markdown
# _FEATURES.md — App Name
Generated: 2026-03-22T12:00:00-04:00
App URL: https://example.com

## Feature Inventory

### Page Name (`/route`)
![Screenshot](screenshots/route.png)

**What the user sees:** Prose description from Claude vision.

**Interactions:**
- Button "X" → does Y
- Link "Z" → navigates to /other

**Invariants:**
- Rule 1 the feature must satisfy
- Rule 2

**Code:** `src/components/Page.js` :1 | `src/utils.js` :42
```

## Relationship to CLAUDE.md

`_FEATURES.md` is the behavioral source of truth. Combined with `_MAP.md` (structural), these feed the behavioral sections of CLAUDE.md. Workflow:

1. `mapping-codebases` → `_MAP.md` (structural)
2. `mapping-features` → `_FEATURES.md` (behavioral)
3. Merge both into CLAUDE.md architecture/concepts sections

## Process Guardrails

- Do NOT bypass auth — use the human-in-the-loop pattern
- Do NOT describe code internals — that's `_MAP.md`'s job. Describe *behavior*, linked to code
- Do NOT hardcode app-specific logic — works for any web app with a running instance
- If webctl fails on a page, mark it `CAPTURE_FAILED` with the error — don't skip silently
- Store PNGs in `screenshots/` directory, not embedded as base64

## Limitations

- Requires a running app instance (no static analysis of UI)
- Claude API calls for vision cost tokens — use `--incremental` to minimize
- Single-page apps with client-side routing may need manual route hints
- Auth-gated pages require human intervention
