#!/usr/bin/env python3
"""
docmap — tree-sitter for documents.

Maps a PDF's structure and semantics into navigable artifacts:
  {stem}_MAP.md          Progressive-disclosure document map
  {stem}.symbols.json    Symbol/term index with definition locations
  {stem}.anchors.json    Page+quote references for every extracted claim

Usage:
    python docmap.py paper.pdf                    # auto-detect genre
    python docmap.py paper.pdf --genre paper      # academic paper
    python docmap.py paper.pdf --structure-only   # skip LLM pass
    python docmap.py paper.pdf --out docs/        # output directory
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber


# ---------------------------------------------------------------------------
# 1. STRUCTURAL LAYER (deterministic, no LLM)
# ---------------------------------------------------------------------------

@dataclass
class Section:
    """A document section detected from font/layout signals."""
    id: str                         # e.g. "1", "4.3", "abstract"
    title: str
    level: int                      # 0=title, 1=§, 2=§§, 3=§§§
    page_start: int                 # 1-indexed
    page_end: int = 0
    text: str = ""
    children: list = field(default_factory=list)
    equations: list = field(default_factory=list)
    figures: list = field(default_factory=list)
    tables: list = field(default_factory=list)


def _line_groups(page):
    """Group characters into lines by y-position (within 2pt tolerance)."""
    if not page.chars:
        return []
    lines = []
    current_y = None
    current_chars = []
    for c in sorted(page.chars, key=lambda c: (round(c['top'], 0), c['x0'])):
        y = round(c['top'], 0)
        if current_y is None or abs(y - current_y) <= 2:
            current_chars.append(c)
            current_y = y if current_y is None else current_y
        else:
            lines.append(current_chars)
            current_chars = [c]
            current_y = y
    if current_chars:
        lines.append(current_chars)
    return lines


def _clean_heading_text(raw_chars):
    """Re-insert spaces using character x-position gaps from PDF extraction."""
    if not raw_chars:
        return ""
    chars = sorted(raw_chars, key=lambda c: c['x0'])
    parts = []
    prev_x1 = None
    for c in chars:
        ch = c['text']
        if not ch:
            continue
        if prev_x1 is not None:
            gap = c['x0'] - prev_x1
            if gap > c['size'] * 0.25:
                parts.append(' ')
        parts.append(ch)
        prev_x1 = c['x1']
    return ''.join(parts).strip()


def _detect_headings(page, page_num, font_profile):
    """Detect headings on a page using font characteristics."""
    headings = []
    lines = _line_groups(page)
    for chars in lines:
        raw_text = ''.join(c['text'] for c in chars).strip()
        if not raw_text or len(raw_text) < 2:
            continue
        content_chars = [c for c in chars if c['text'].strip()]
        if not content_chars:
            continue
        sizes = [c['size'] for c in content_chars]
        fonts = [c['fontname'] for c in content_chars]
        avg_size = sum(sizes) / len(sizes)
        is_bold = any('BX' in f or 'Bold' in f or 'bold' in f for f in fonts)
        y_top = min(c['top'] for c in content_chars)

        level = None
        if avg_size >= font_profile['title_size'] * 0.9:
            level = 0
        elif is_bold and avg_size >= font_profile['section_size'] * 0.9:
            level = 1
        elif is_bold and avg_size >= font_profile['subsection_size'] * 0.9:
            level = 2
        elif is_bold and avg_size >= font_profile['body_size'] * 0.95:
            level = 3

        if level is not None:
            text = _clean_heading_text(content_chars)
            # Filter false positives
            if len(text) > 80 and level >= 2:
                continue
            if level >= 3 and len(text) > 40 and any(
                    p in text.lower() for p in [' is ', ' are ', ' the ', ', and ', '. ']):
                continue

            headings.append({
                'text': text,
                'level': level,
                'page': page_num,
                'y_top': y_top,
                'size': avg_size,
                'bold': is_bold,
            })
    return headings


def _detect_font_profile(pdf):
    """Auto-detect font size thresholds from the first few pages."""
    size_counts = {}
    for page in pdf.pages[:min(8, len(pdf.pages))]:
        for c in page.chars:
            if not c['text'].strip():
                continue
            sz = round(c['size'], 1)
            size_counts[sz] = size_counts.get(sz, 0) + 1

    body_size = max(size_counts, key=size_counts.get)
    heading_sizes = sorted([s for s in size_counts if s > body_size * 1.1], reverse=True)

    return {
        'body_size': body_size,
        'title_size': heading_sizes[0] if heading_sizes else body_size * 1.8,
        'section_size': (heading_sizes[1] if len(heading_sizes) > 1
                         else heading_sizes[0] if heading_sizes else body_size * 1.4),
        'subsection_size': (heading_sizes[2] if len(heading_sizes) > 2
                            else heading_sizes[1] if len(heading_sizes) > 1
                            else body_size * 1.2),
    }


def _extract_section_id(title, level=None):
    """Extract section number from title, e.g. '1 Introduction' → '1'."""
    m = re.match(r'^(\d+(?:\.\d+)*)\s+', title)
    if m:
        return m.group(1)
    if level == 0:
        return 'title'
    lower = title.lower().strip()
    for name in ['abstract', 'summary paragraph', 'summary', 'significance',
                 'references', 'acknowledgments', 'acknowledgements', 'appendix',
                 'supplementary', 'data availability', 'ai use']:
        if lower.startswith(name):
            return name.replace(' ', '-')
    return re.sub(r'[^a-z0-9]+', '-', lower)[:30].strip('-')


def _extract_page_text_by_y(page, y_start=0, y_end=None):
    """Extract text from a page between two y-positions."""
    if not page.chars:
        return ""
    if y_end is None:
        y_end = float('inf')

    # Filter chars within y range, then use pdfplumber's own text extraction
    # on a cropped region for proper line ordering
    page_height = float(page.height)
    top = max(0, y_start - 2)
    bottom = min(page_height, y_end + 2) if y_end != float('inf') else page_height

    try:
        cropped = page.crop((0, top, float(page.width), bottom))
        return cropped.extract_text() or ""
    except Exception:
        # Fallback: manual char assembly
        chars = [c for c in page.chars
                 if c['top'] >= top and c['top'] < bottom]
        return ''.join(c['text'] for c in sorted(chars, key=lambda c: (c['top'], c['x0'])))


def _extract_labeled_items(text, page_num):
    """Find equations, figures, tables with labels in section text."""
    equations, figures, tables = [], [], []
    for m in re.finditer(r'\((\d+[a-z]?)\)', text):
        label = m.group(1)
        if label.isdigit() or (len(label) <= 3 and label[:-1].isdigit()):
            equations.append((label, page_num))
    for m in re.finditer(r'(?:Figure|Fig\.?)\s+(\d+)', text, re.IGNORECASE):
        figures.append((m.group(1), '', page_num))
    for m in re.finditer(r'Table\s+(\d+)', text, re.IGNORECASE):
        tables.append((m.group(1), '', page_num))
    return equations, figures, tables


def parse_structure(pdf_path: str) -> tuple[list[Section], dict]:
    """Parse a PDF into a flat list of sections with text content."""
    pdf = pdfplumber.open(pdf_path)
    font_profile = _detect_font_profile(pdf)

    # Pass 1: collect all headings
    all_headings = []
    for i, page in enumerate(pdf.pages):
        all_headings.extend(_detect_headings(page, i + 1, font_profile))

    # Filter figure pages (>5 "headings" = likely a diagram)
    page_counts = {}
    for h in all_headings:
        page_counts[h['page']] = page_counts.get(h['page'], 0) + 1
    figure_pages = {p for p, c in page_counts.items() if c > 5}
    all_headings = [h for h in all_headings if h['page'] not in figure_pages]

    # Filter short non-keyword headings
    all_headings = [h for h in all_headings
                    if len(h['text']) >= 3 or re.match(r'^\d', h['text'])]

    # Pass 2: assign text to sections using y-positions for same-page splits
    sections = []
    metadata = {
        'file': os.path.basename(pdf_path),
        'pages': len(pdf.pages),
        'font_profile': font_profile,
    }

    for idx, h in enumerate(all_headings):
        next_h = all_headings[idx + 1] if idx + 1 < len(all_headings) else None

        if next_h is None:
            # Last section: runs to end of document
            page_end = len(pdf.pages)
            y_end_on_last = None
        elif next_h['page'] == h['page']:
            # Next heading on same page: split by y-position
            page_end = h['page']
            y_end_on_last = next_h['y_top']
        else:
            # Next heading on a later page
            page_end = next_h['page']
            y_end_on_last = next_h['y_top']

        # Assemble text
        text_parts = []
        for p_num in range(h['page'], page_end + 1):
            page = pdf.pages[p_num - 1]
            if p_num == h['page'] and p_num == page_end:
                # Single-page section: heading y to next heading y (or page end)
                text_parts.append(_extract_page_text_by_y(page, h['y_top'], y_end_on_last))
            elif p_num == h['page']:
                # First page: from heading y to bottom
                text_parts.append(_extract_page_text_by_y(page, h['y_top']))
            elif p_num == page_end:
                # Last page: from top to next heading y
                text_parts.append(_extract_page_text_by_y(page, 0, y_end_on_last))
            else:
                # Full middle page
                text_parts.append(page.extract_text() or "")

        section_text = '\n'.join(text_parts)
        sec_id = _extract_section_id(h['text'], level=h['level'])
        equations, figures, tables = _extract_labeled_items(section_text, h['page'])

        sections.append(Section(
            id=sec_id,
            title=h['text'],
            level=h['level'],
            page_start=h['page'],
            page_end=page_end if next_h and next_h['page'] > h['page'] else h['page'],
            text=section_text,
            equations=equations,
            figures=figures,
            tables=tables,
        ))

    for s in sections:
        if s.level == 0:
            metadata['title'] = s.title
            break

    pdf.close()
    return sections, metadata


# ---------------------------------------------------------------------------
# 2. SEMANTIC LAYER (LLM-powered, anchored to structure)
# ---------------------------------------------------------------------------

GENRE_PROMPTS = {
    'paper': """You are extracting a semantic map from an academic paper section.

For the section below, extract:

1. **claims**: Key assertions, findings, or arguments. Each:
   - A single sentence in your own words
   - Typed: "definition", "result", "method", "claim", "caveat", "open-question"
   - Page number where the evidence appears

2. **symbols**: Mathematical symbols or named concepts defined or used here:
   - symbol: the notation (e.g. "eml(x,y)", "K")
   - meaning: what it represents
   - defined_here: true if this section defines it
   - page: where it appears

3. **dependencies**: Section IDs or concept names this section depends on.

Respond ONLY with valid JSON, no markdown fences, no preamble:
{
  "summary": "1-2 sentence summary",
  "claims": [{"text": "...", "type": "...", "page": N}],
  "symbols": [{"symbol": "...", "meaning": "...", "defined_here": true, "page": N}],
  "dependencies": ["..."]
}""",

    'spec': """You are extracting a semantic map from a technical specification section.

For the section below, extract:

1. **claims**: Requirements, constraints, definitions, examples. Each:
   - A single sentence summary
   - Typed: "requirement", "definition", "constraint", "example", "note"
   - Page number

2. **symbols**: Parameters, endpoints, field names, types defined or used.

3. **dependencies**: Cross-references to other sections.

Respond ONLY with valid JSON (no fences):
{
  "summary": "...",
  "claims": [{"text": "...", "type": "...", "page": N}],
  "symbols": [{"symbol": "...", "meaning": "...", "defined_here": true, "page": N}],
  "dependencies": ["..."]
}""",

    'legal': """You are extracting a semantic map from a legal or policy document section.

For the section below, extract:

1. **claims**: Definitions, obligations, rights, exceptions, conditions. Each:
   - A single sentence summary
   - Typed: "definition", "obligation", "right", "exception", "condition", "reference"
   - Page number

2. **symbols**: Defined terms, party names, referenced statutes/regulations.

3. **dependencies**: Cross-references to other sections or external sources.

Respond ONLY with valid JSON (no fences):
{
  "summary": "...",
  "claims": [{"text": "...", "type": "...", "page": N}],
  "symbols": [{"symbol": "...", "meaning": "...", "defined_here": true, "page": N}],
  "dependencies": ["..."]
}""",
}


def _semantic_extract(section: Section, genre: str, api_key: str,
                      model: str = "claude-sonnet-4-6") -> dict:
    """Call Claude API to extract semantic information from a section."""
    import anthropic

    if len(section.text.strip()) < 50:
        return {"summary": section.title, "claims": [], "symbols": [], "dependencies": []}

    prompt = GENRE_PROMPTS.get(genre, GENRE_PROMPTS['paper'])
    text = section.text[:15000] + ("\n[... truncated ...]" if len(section.text) > 15000 else "")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=prompt,
            messages=[{
                "role": "user",
                "content": (
                    f"SECTION: {section.id} — {section.title}\n"
                    f"PAGES: {section.page_start}–{section.page_end}\n\n"
                    f"TEXT:\n{text}"
                )
            }],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  ⚠ JSON parse failed for §{section.id}", file=sys.stderr)
        return {"summary": section.title, "claims": [], "symbols": [], "dependencies": []}
    except Exception as e:
        print(f"  ⚠ API error for §{section.id}: {e}", file=sys.stderr)
        return {"summary": section.title, "claims": [], "symbols": [], "dependencies": []}


def extract_semantics(sections: list[Section], genre: str, api_key: str,
                      max_workers: int = 4) -> dict[str, dict]:
    """Run semantic extraction on all sections in parallel."""
    results = {}
    targets = [s for s in sections
               if len(s.text.strip()) > 100 and s.id != 'references' and s.level <= 3]

    print(f"  Extracting semantics for {len(targets)} sections "
          f"({max_workers} workers)...", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_semantic_extract, s, genre, api_key): s for s in targets}
        for future in as_completed(futures):
            section = futures[future]
            result = future.result()
            results[section.id] = result
            print(f"    ✓ §{section.id} — {result.get('summary', '')[:60]}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# 3. OUTPUT GENERATION
# ---------------------------------------------------------------------------

def _normalize_symbol(s: str) -> str:
    """Normalize Unicode variants for symbol deduplication."""
    # Normalize Unicode (NFKC collapses compatibility chars)
    s = unicodedata.normalize('NFKC', s)
    # Normalize common arrow/dash variants
    s = s.replace('→', '->').replace('−', '-').replace('·', '*')
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def generate_map(sections: list[Section], semantics: dict, metadata: dict) -> str:
    """Generate _MAP.md — progressive disclosure document map."""
    lines = []
    title = metadata.get('title', metadata.get('file', 'Document'))
    lines.append(f"# {title}")
    lines.append(f"*{metadata.get('pages', '?')} pages*\n")

    # TOC
    lines.append("## Contents\n")
    for s in sections:
        if s.level > 3 or s.id == 'references':
            continue
        indent = "  " * s.level
        sem = semantics.get(s.id, {})
        summary = sem.get('summary', '')
        page_ref = f"p.{s.page_start}" + (f"–{s.page_end}" if s.page_end > s.page_start else "")
        if summary:
            lines.append(f"{indent}- **§{s.id}** {s.title} ({page_ref}) — {summary}")
        else:
            lines.append(f"{indent}- **§{s.id}** {s.title} ({page_ref})")

    # Detailed sections
    lines.append("\n---\n")
    lines.append("## Sections\n")

    for s in sections:
        if s.level > 3:
            continue
        sem = semantics.get(s.id, {})
        level_marker = "#" * min(s.level + 3, 6)
        page_ref = f"p.{s.page_start}" + (f"–{s.page_end}" if s.page_end > s.page_start else "")

        lines.append(f"{level_marker} §{s.id} {s.title} ({page_ref})\n")
        if sem.get('summary'):
            lines.append(f"{sem['summary']}\n")

        claims = sem.get('claims', [])
        if claims:
            lines.append("**Key points:**")
            for c in claims:
                lines.append(f"- [{c.get('type', 'claim')}] {c['text']} (p.{c.get('page', '?')})")
            lines.append("")

        symbols = [sym for sym in sem.get('symbols', []) if sym.get('defined_here')]
        if symbols:
            lines.append("**Defines:**")
            for sym in symbols:
                lines.append(f"- `{sym['symbol']}` — {sym['meaning']} (p.{sym.get('page', '?')})")
            lines.append("")

        deps = sem.get('dependencies', [])
        if deps:
            lines.append(f"*Depends on: {', '.join(deps)}*\n")

        if s.equations:
            lines.append(f"*Equations: ({'), ('.join(sorted(set(l for l, _ in s.equations)))})*")
        if s.figures:
            lines.append(f"*Figures: {', '.join(sorted(set(l for l, _, _ in s.figures)))}*")
        if s.tables:
            lines.append(f"*Tables: {', '.join(sorted(set(l for l, _, _ in s.tables)))}*")
        lines.append("")

    return '\n'.join(lines)


def generate_symbols(semantics: dict) -> list[dict]:
    """Generate symbols.json — flat index with deduplication."""
    seen = {}
    for sec_id, sem in semantics.items():
        for sym in sem.get('symbols', []):
            key = _normalize_symbol(sym['symbol'])
            if key not in seen:
                seen[key] = {
                    'symbol': sym['symbol'],
                    'meaning': sym['meaning'],
                    'defined_in': sec_id if sym.get('defined_here') else None,
                    'defined_at_page': sym.get('page') if sym.get('defined_here') else None,
                    'used_in': [sec_id],
                }
            else:
                if sec_id not in seen[key]['used_in']:
                    seen[key]['used_in'].append(sec_id)
                if sym.get('defined_here') and not seen[key]['defined_in']:
                    seen[key]['defined_in'] = sec_id
                    seen[key]['defined_at_page'] = sym.get('page')
    return sorted(seen.values(), key=lambda s: s['symbol'])


def generate_anchors(sections: list[Section], semantics: dict) -> list[dict]:
    """Generate anchors.json — every claim with its page reference."""
    anchors = []
    for sec_id, sem in semantics.items():
        for i, claim in enumerate(sem.get('claims', [])):
            anchors.append({
                'id': f"{sec_id}.c{i}",
                'section': sec_id,
                'type': claim.get('type', 'claim'),
                'text': claim['text'],
                'page': claim.get('page'),
            })
    return anchors


def generate_usage_snippet(stem: str, out_dir: str, metadata: dict,
                           semantics: dict) -> str:
    """Generate a snippet for CLAUDE.md / project instructions.

    This is the glue between the map and the agent's instruction file.
    Designed to be pasted into CLAUDE.md, AGENTS.md, or a Claude.ai
    project knowledge file.
    """
    title = metadata.get('title', stem)
    pages = metadata.get('pages', '?')
    n_symbols = len(generate_symbols(semantics)) if semantics else 0
    n_claims = sum(len(sem.get('claims', [])) for sem in semantics.values())

    # Use out_dir as the relative path prefix
    rel = out_dir.rstrip('/')

    lines = [
        f"## Reference: {title}",
        f"",
        f"Source document: `{rel}/{stem}.pdf` ({pages} pages)",
        f"",
        f"### How to use the document map",
        f"",
        f"A semantic map of this document is available at three levels of detail:",
        f"",
        f"1. **This file** — hand-curated invariants and guidance (you are here)",
        f"2. **`{rel}/{stem}_MAP.md`** — machine-generated section map with typed",
        f"   claims, symbol definitions, and dependencies. Read this for any question",
        f"   about what the document says. Replaces reading the raw PDF in most cases.",
        f"3. **`{rel}/{stem}.pdf`** — the original. Read only when you need exact",
        f"   wording, figures, or proofs.",
        f"",
    ]

    if n_symbols > 0 or n_claims > 0:
        lines.append(f"### Querying the indexes")
        lines.append(f"")
        lines.append(f"Two JSON indexes support programmatic lookup:")
        lines.append(f"")

    if n_symbols > 0:
        lines.extend([
            f"**Symbol lookup** (`{rel}/{stem}.symbols.json` — {n_symbols} symbols):",
            f"```bash",
            f"# Find where a symbol is defined",
            f"python3 -c \"import json; [print(f'Defined in §{{s[\\\"defined_in\\\"]}} p.{{s[\\\"defined_at_page\\\"]}}:  {{s[\\\"meaning\\\"]}}') for s in json.load(open('{rel}/{stem}.symbols.json')) if 'QUERY' in s['symbol']]\"",
            f"```",
            f"",
        ])

    if n_claims > 0:
        lines.extend([
            f"**Claim queries** (`{rel}/{stem}.anchors.json` — {n_claims} claims):",
            f"```bash",
            f"# List all caveats",
            f"python3 -c \"import json; [print(f'p.{{c[\\\"page\\\"]}} {{c[\\\"text\\\"]}}') for c in json.load(open('{rel}/{stem}.anchors.json')) if c['type'] == 'caveat']\"",
            f"",
            f"# All claims in a specific section",
            f"python3 -c \"import json; [print(f'[{{c[\\\"type\\\"]}}] {{c[\\\"text\\\"]}}') for c in json.load(open('{rel}/{stem}.anchors.json')) if c['section'] == 'SECTION_ID']\"",
            f"```",
            f"",
        ])

    lines.extend([
        f"<!-- Generated by mapping-documents v0.1.2 -->",
        f"<!-- Paste into CLAUDE.md, AGENTS.md, or Claude.ai project knowledge -->",
    ])

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# 4. CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="docmap — tree-sitter for documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('pdf', help='Path to PDF file')
    parser.add_argument('--genre', choices=list(GENRE_PROMPTS.keys()),
                        default='paper', help='Document genre (default: paper)')
    parser.add_argument('--structure-only', action='store_true',
                        help='Skip LLM semantic extraction')
    parser.add_argument('--out', default='.', help='Output directory')
    parser.add_argument('--api-key', help='Anthropic API key (or set ANTHROPIC_API_KEY / API_KEY)')
    parser.add_argument('--model', default='claude-sonnet-4-6',
                        help='Model for semantic extraction')
    parser.add_argument('--workers', type=int, default=4,
                        help='Parallel workers for semantic extraction')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--no-usage-snippet', action='store_true',
                        help='Skip generating the CLAUDE.md usage snippet')
    args = parser.parse_args()

    pdf_path = args.pdf
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found", file=sys.stderr)
        sys.exit(1)

    stem = Path(pdf_path).stem
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    map_path = out_dir / f"{stem}_MAP.md"
    symbols_path = out_dir / f"{stem}.symbols.json"
    anchors_path = out_dir / f"{stem}.anchors.json"

    # Pass 1: Structure
    print(f"Parsing structure: {pdf_path}", file=sys.stderr)
    sections, metadata = parse_structure(pdf_path)
    print(f"  Found {len(sections)} sections across {metadata['pages']} pages", file=sys.stderr)

    if args.verbose:
        for s in sections:
            print(f"  {'  ' * s.level}§{s.id} {s.title} "
                  f"(p.{s.page_start}–{s.page_end}, {len(s.text)} chars)", file=sys.stderr)

    # Pass 2: Semantics
    semantics = {}
    if not args.structure_only:
        api_key = (args.api_key
                   or os.environ.get('ANTHROPIC_API_KEY')
                   or os.environ.get('API_KEY'))
        if not api_key:
            print("Warning: no API key. Use --api-key or set ANTHROPIC_API_KEY. "
                  "Falling back to structure-only.", file=sys.stderr)
        else:
            semantics = extract_semantics(sections, args.genre, api_key,
                                          max_workers=args.workers)

    # Pass 3: Generate outputs
    print(f"Generating outputs in {out_dir}/", file=sys.stderr)

    map_content = generate_map(sections, semantics, metadata)
    map_path.write_text(map_content)
    print(f"  ✓ {map_path} ({len(map_content):,} chars)", file=sys.stderr)

    if semantics:
        symbols = generate_symbols(semantics)
        symbols_path.write_text(json.dumps(symbols, indent=2))
        print(f"  ✓ {symbols_path} ({len(symbols)} symbols)", file=sys.stderr)

        anchors = generate_anchors(sections, semantics)
        anchors_path.write_text(json.dumps(anchors, indent=2))
        print(f"  ✓ {anchors_path} ({len(anchors)} claims)", file=sys.stderr)

    # Pass 4: Usage snippet for CLAUDE.md / project instructions
    if not args.no_usage_snippet:
        snippet_path = out_dir / f"{stem}_USAGE.md"
        snippet = generate_usage_snippet(stem, str(args.out), metadata, semantics)
        snippet_path.write_text(snippet)
        print(f"  ✓ {snippet_path} (paste into CLAUDE.md or project instructions)",
              file=sys.stderr)

    print("Done.", file=sys.stderr)


if __name__ == '__main__':
    main()
