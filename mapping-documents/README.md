# mapping-documents

**Tree-sitter for documents.** Generate navigable semantic maps from PDFs.

Just as [`mapping-codebases`](../mapping-codebases/) parses source code into `_MAP.md` files via AST analysis, `mapping-documents` parses PDF documents into structured maps via font analysis + LLM extraction.

## The problem

A coding agent needs to stay faithful to a reference document — a paper, a spec, a contract. The raw PDF is too large to load on every invocation, and too unstructured for programmatic queries. Hand-curating a summary (like writing a `CLAUDE.md`) works but doesn't scale and drifts from the source.

## What this produces

Four artifacts, designed as a three-layer progressive-disclosure stack:

```
CLAUDE.md / project instructions     ← curated invariants (you write this)
    ↕ (usage snippet bridges the gap)
_MAP.md                              ← navigable section map (docmap generates this)
    ↕
raw PDF                              ← the source document
```

| File | What | Size (typical) | When to read |
|------|------|----------------|--------------|
| `{stem}_USAGE.md` | Snippet for pasting into CLAUDE.md or project instructions. Describes the three-layer reading order and shows how to query the JSON indexes. | ~1 KB | Once, at setup |
| `{stem}_MAP.md` | Section-by-section map: TOC with summaries, typed claims (result / definition / method / caveat / open-question), symbol definitions, dependency graph. All page-anchored. | 30–50 KB | When you need to know what the document says |
| `{stem}.symbols.json` | Flat index of every symbol/term: where it's defined, where it's used, what it means. | 5–15 KB | "Where is X defined?" |
| `{stem}.anchors.json` | Every extracted claim: section ID, type, text, page number. | 15–30 KB | "What caveats exist?" / "What results are claimed in §3?" |

### How the pieces fit together

**`_MAP.md`** is the primary artifact. A human or agent reads this to understand what the document covers, section by section. It replaces skimming the PDF.

**`.symbols.json`** and **`.anchors.json`** are queryable indexes *into* the map. They answer structured questions: `jq '.[] | select(.type == "caveat")' paper.anchors.json` returns every caveat with its page number. An agent can run these queries without loading the full map.

**`_USAGE.md`** is the glue. It's a short block you paste into your `CLAUDE.md`, `AGENTS.md`, or Claude.ai project knowledge file. It tells the agent:
1. The three-layer reading order exists
2. How to query the JSON files (with copy-pasteable commands)
3. When to fall back to the raw PDF

Without the usage snippet, the agent doesn't know the map exists or how to use it.

## Quick start

```bash
pip install pdfplumber anthropic --break-system-packages -q

# Generate all four artifacts
python scripts/docmap.py paper.pdf --out docs/ --genre paper

# Then paste docs/paper_USAGE.md into your CLAUDE.md
```

## Example output

Generated from [Odrzywolek 2026](https://arxiv.org/abs/2603.21852) ("All elementary functions from a single operator", 23 pages):

- 16 sections detected via font analysis
- 51 unique symbols indexed (with Unicode dedup)
- 103 typed claims extracted across 15 sections
- See the [eml-sr repo](https://github.com/oaustegard/eml-sr/tree/main/docs) for the actual output

## How it works

**Structural layer** (deterministic, free):
- Auto-detects font size profile from first 8 pages
- Identifies headings by font size + boldness
- Filters false positives: figure pages, bold body text, sentence-pattern heuristics
- Recovers heading spacing from character x-position gaps
- Splits same-page sections by character y-positions

**Semantic layer** (LLM, ~$0.02 per paper):
- Parallel Claude API calls per section (4 workers default)
- Genre-specific extraction prompts (paper / spec / legal)
- Typed claims with page anchors
- Symbol definition tracking (defined_here vs referenced)
- Unicode-normalized dedup

## Genres

| Genre | Claim taxonomy | Best for |
|-------|----------------|----------|
| `paper` | definition, result, method, claim, caveat, open-question | Academic papers, preprints |
| `spec` | requirement, definition, constraint, example, note | RFCs, API specs |
| `legal` | definition, obligation, right, exception, condition, reference | Contracts, regulations |

## Known limitations (v0.1.0)

- PDF-only input
- Single-column layout assumed (two-column text may interleave)
- No caching — re-run re-extracts
- No citation cross-referencing
- Page numbers in claims come from the LLM, not positional matching
- Genre must be specified manually

## CLI

```
python scripts/docmap.py paper.pdf [options]

Options:
  --genre {paper,spec,legal}   Claim taxonomy (default: paper)
  --structure-only             Skip LLM pass (free, fast, no claims/symbols)
  --out DIR                    Output directory (default: .)
  --api-key KEY                Anthropic API key (or set ANTHROPIC_API_KEY)
  --model MODEL                Model for extraction (default: claude-sonnet-4-6)
  --workers N                  Parallel workers (default: 4)
  --no-usage-snippet           Skip generating the _USAGE.md snippet
  -v                           Verbose structural parsing output
```
