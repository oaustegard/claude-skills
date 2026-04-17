---
name: mapping-documents
description: Generate navigable semantic maps from PDF documents. Extracts section structure via font analysis, then runs LLM extraction per section for claims, symbols, and dependencies — all page-anchored. Produces _MAP.md (progressive disclosure), .symbols.json (definition index), and .anchors.json (claim references). Use when analyzing papers, specs, or legal docs; when asked to "map this document", "index this PDF", "what does this paper say"; or when a coding agent needs grounded reference material from a PDF source. Analogous to mapping-codebases but for prose documents.
metadata:
  version: 0.1.0
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

# With explicit API key
python /mnt/skills/user/mapping-documents/scripts/docmap.py paper.pdf \
  --api-key "$ANTHROPIC_API_KEY" --out docs/
```

API key resolution: `--api-key` flag > `ANTHROPIC_API_KEY` env > `API_KEY` env.

## Output Artifacts

| File | Purpose | Consumer |
|------|---------|----------|
| `{stem}_MAP.md` | Progressive-disclosure document map. TOC with summaries, then per-section detail with typed claims, defined symbols, and dependencies. | Human reader or LLM context window |
| `{stem}.symbols.json` | Flat index of all symbols/terms with definition locations and cross-references. | Programmatic lookup: "where is X defined?" |
| `{stem}.anchors.json` | Every extracted claim with section ID, type, text, and page number. | Fact-checking, citation generation |

### _MAP.md structure

```
# Document Title
*N pages*

## Contents           ← TOC with one-line summaries
  - §1 Introduction (p.4–6) — summary...
    - §1.1 Background (p.4–5) — summary...

---

## Sections           ← Per-section detail
### §1 Introduction (p.4–6)
summary

**Key points:**
- [result] Claim text (p.5)
- [definition] Claim text (p.4)

**Defines:**
- `symbol` — meaning (p.4)

*Depends on: §concepts, §prior-work*
*Equations: (1), (2)*
```

## Navigate Via Maps

After generating maps, use them for navigation — read `_MAP.md`, not the raw PDF.

**Workflow:**
1. Read top-level TOC for document structure and section summaries
2. Drill into relevant sections for typed claims and symbol definitions
3. Use `.symbols.json` for "where is X defined?" lookups
4. Use `.anchors.json` to verify specific claims against page numbers
5. Read the raw PDF only when exact wording or figures are needed

## Genre Support

Genre controls the claim taxonomy used in semantic extraction.

| Genre | Claim types | Best for |
|-------|-------------|----------|
| `paper` (default) | definition, result, method, claim, caveat, open-question | Academic papers, arXiv preprints |
| `spec` | requirement, definition, constraint, example, note | RFCs, API specs, technical standards |
| `legal` | definition, obligation, right, exception, condition, reference | Contracts, policy documents, regulations |

Auto-detection is not yet implemented. Use `--genre` explicitly.

## How It Works

**Structural layer** (deterministic, no LLM):
- Auto-detects font size profile from first 8 pages (body, section, subsection, title thresholds)
- Identifies headings by font size + boldness
- Filters false positives: figure pages (>5 "headings"), body-text bold, length heuristics
- Recovers proper heading text spacing from character x-position gaps
- Splits page text between same-page sections using character y-positions

**Semantic layer** (LLM-powered, parallel):
- Sends each section's text to Claude with a genre-specific extraction prompt
- Extracts claims (typed + page-anchored), symbols (defined vs referenced), dependencies
- Deduplicates symbols with Unicode normalization (→/->  −/- etc.)
- Runs sections in parallel (default 4 workers)

## Limitations (v0.1.0)

- **PDF-only.** No DOCX, HTML, or plain text input yet.
- **Single-column layout assumed.** Two-column papers may mis-order text within sections. The structural parser works (headings are still detected) but section text may interleave columns.
- **No caching.** Re-running re-extracts everything. Section content hashing for cache is planned.
- **No citation extraction.** References section is skipped. Inline citation cross-referencing is not yet implemented.
- **Genre must be specified.** Auto-detection from section naming patterns is planned.
- **Equation extraction is heuristic.** Detects `(N)` patterns in text; does not parse LaTeX or MathML.
- **Semantic extraction can hallucinate.** Every claim is page-anchored, but the page number comes from the LLM, not from positional matching. Verify critical claims against the source.

## CLI Reference

```
usage: docmap.py [-h] [--genre {paper,spec,legal}] [--structure-only]
                 [--out OUT] [--api-key API_KEY] [--model MODEL]
                 [--workers WORKERS] [-v]
                 pdf

positional arguments:
  pdf                   Path to PDF file

options:
  --genre               Document genre (default: paper)
  --structure-only      Skip LLM semantic extraction
  --out                 Output directory (default: .)
  --api-key             Anthropic API key
  --model               Model for extraction (default: claude-sonnet-4-6)
  --workers             Parallel workers (default: 4)
  -v, --verbose         Show section details during parsing
```
