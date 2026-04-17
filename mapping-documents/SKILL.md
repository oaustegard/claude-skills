---
name: mapping-documents
description: Generate navigable semantic maps from PDF documents. Extracts section structure via font analysis, then runs LLM extraction per section for claims, symbols, and dependencies — all page-anchored. Produces _MAP.md (progressive disclosure), .symbols.json (definition index), .anchors.json (claim references), and a _USAGE.md snippet for CLAUDE.md. Use when analyzing papers, specs, or legal docs; when asked to "map this document", "index this PDF", "what does this paper say"; or when a coding agent needs grounded reference material from a PDF source. Analogous to mapping-codebases but for prose documents.
metadata:
  version: 0.1.2
---

# Mapping Documents

Generate `_MAP.md` files providing hierarchical document structure with semantic annotations. Maps show section summaries, typed claims (result/definition/method/caveat/open-question), symbol definitions, and cross-section dependencies — all anchored to page numbers.

The structural analog to `mapping-codebases`: tree-sitter parses code via grammar, docmap parses documents via font analysis + LLM extraction.

## Installation

```bash
pip install pdfplumber anthropic --break-system-packages -q
```

## Generate Maps

```bash
# Full run (structure + semantic extraction via Claude API)
python /mnt/skills/user/mapping-documents/scripts/docmap.py paper.pdf \
  --out docs/ --genre paper --workers 4

# Structure only (no API calls, no cost)
python /mnt/skills/user/mapping-documents/scripts/docmap.py paper.pdf \
  --out docs/ --structure-only
```

API key resolution: `--api-key` flag > `ANTHROPIC_API_KEY` env > `API_KEY` env.

## Output Artifacts

Four files, forming a three-layer progressive-disclosure stack:

```
CLAUDE.md / project instructions     ← curated invariants (you write this)
    ↕ (_USAGE.md bridges the gap)
_MAP.md + JSON indexes               ← navigable document map (docmap generates)
    ↕
raw PDF                              ← the source document
```

| File | Purpose | When to read |
|------|---------|--------------|
| `{stem}_USAGE.md` | Snippet for pasting into CLAUDE.md / AGENTS.md / project knowledge. Describes the reading order and JSON query patterns. | Once, at setup |
| `{stem}_MAP.md` | Section map: TOC with summaries, typed claims, defined symbols, dependencies. All page-anchored. | Any question about what the document says |
| `{stem}.symbols.json` | Flat symbol index: where defined, where used, what it means. | "Where is X defined?" |
| `{stem}.anchors.json` | Every claim: section ID, type, text, page number. | "What caveats exist?" / "What does §3 claim?" |

## After Generating: Wire It Up

Generating the map is step 1. Step 2 is telling the agent the map exists.

**For a code repo (CLAUDE.md / AGENTS.md):**
```bash
# Paste the generated usage snippet into your agent instructions
cat docs/paper_USAGE.md >> CLAUDE.md
```

**For Claude.ai project knowledge:**
Upload `_MAP.md` as a project knowledge file, or paste the `_USAGE.md` content into project instructions.

The `_USAGE.md` snippet includes copy-pasteable query commands for the JSON indexes. Replace `QUERY` and `SECTION_ID` placeholders with actual values.

## Navigate Via Maps

After generating and wiring up, use the map for navigation — read `_MAP.md`, not the raw PDF.

**Workflow:**
1. Read `_USAGE.md` block in CLAUDE.md for orientation
2. Read top-level TOC in `_MAP.md` for structure and section summaries
3. Drill into relevant sections for typed claims and symbol definitions
4. Query `.symbols.json` for "where is X defined?" lookups
5. Query `.anchors.json` for claim filtering by type or section
6. Read the raw PDF only when exact wording or figures are needed

**Querying the JSON indexes:**

```bash
# Symbol lookup
python3 -c "import json; [print(f'§{s[\"defined_in\"]} p.{s[\"defined_at_page\"]}') \
  for s in json.load(open('docs/paper.symbols.json')) if 'edl' in s['symbol']]"

# All caveats in the document
python3 -c "import json; [print(f'p.{c[\"page\"]} {c[\"text\"]}') \
  for c in json.load(open('docs/paper.anchors.json')) if c['type'] == 'caveat']"

# All claims in a section
python3 -c "import json; [print(f'[{c[\"type\"]}] {c[\"text\"]}') \
  for c in json.load(open('docs/paper.anchors.json')) if c['section'] == '4.3']"
```

## Genre Support

Genre controls the claim taxonomy used in semantic extraction.

| Genre | Claim types | Best for |
|-------|-------------|----------|
| `paper` (default) | definition, result, method, claim, caveat, open-question | Academic papers, arXiv preprints |
| `spec` | requirement, definition, constraint, example, note | RFCs, API specs, technical standards |
| `legal` | definition, obligation, right, exception, condition, reference | Contracts, policy documents, regulations |

## Limitations (v0.1.x)

- **PDF-only.** No DOCX, HTML, or plain text input yet.
- **Single-column layout assumed.** Two-column papers may mis-order text within sections.
- **No caching.** Re-running re-extracts everything.
- **No citation cross-referencing.**
- **Genre must be specified manually.**
- **Semantic extraction can hallucinate.** Every claim is page-anchored, but the page number comes from the LLM. Verify critical claims against the source.

## CLI Reference

```
python docmap.py paper.pdf [options]

Options:
  --genre {paper,spec,legal}   Claim taxonomy (default: paper)
  --structure-only             Skip LLM pass (free, fast)
  --out DIR                    Output directory (default: .)
  --api-key KEY                Anthropic API key
  --model MODEL                Model (default: claude-sonnet-4-6)
  --workers N                  Parallel workers (default: 4)
  --no-usage-snippet           Skip _USAGE.md generation
  -v                           Verbose structural parsing
```
