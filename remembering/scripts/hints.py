"""
Proactive memory surfacing via recall_hints().

v3.4.0: Added for issue #211 - helps surface relevant memories before mistakes happen.
v5.0.0: Removed local cache dependency. Uses Turso queries for matching.
"""

import re
import json
from typing import List, Dict, Optional, Set
from collections import defaultdict

from .config import config_get
from .turso import _exec


def recall_hints(context: str = None, *, terms: List[str] = None,
                 include_tags: bool = True, include_summaries: bool = True,
                 min_matches: int = 1) -> Dict:
    """Proactively surface relevant memories based on context or terms.

    Scans the provided context (or explicit terms) against memory tags and summaries,
    returning hints about what might be relevant WITHOUT loading full memory content.
    This is a lightweight "should I look deeper?" signal.

    Args:
        context: Text to scan for matching terms (e.g., current code, user message).
        terms: Explicit list of terms to match against (alternative to context).
        include_tags: If True (default), match against memory tags.
        include_summaries: If True (default), match against memory summaries.
        min_matches: Minimum term matches required to include a hint (default 1).

    Returns:
        Dict with hints, term_coverage, unmatched_terms, and optional warning.
    """
    result = {
        'hints': [],
        'term_coverage': defaultdict(list),
        'unmatched_terms': [],
        'warning': None
    }

    # Extract terms from context or use explicit terms
    if terms:
        search_terms = set(t.lower() for t in terms if t)
    elif context:
        search_terms = _extract_terms(context)
    else:
        result['warning'] = "No context or terms provided"
        return result

    if not search_terms:
        result['warning'] = "No searchable terms extracted from context"
        return result

    # Try Turso-based matching
    try:
        hints, term_coverage = _match_from_turso(
            search_terms,
            include_tags=include_tags,
            include_summaries=include_summaries,
            min_matches=min_matches
        )
        result['hints'] = hints
        result['term_coverage'] = dict(term_coverage)
        result['unmatched_terms'] = [t for t in search_terms if t not in term_coverage]
        return result
    except Exception as e:
        result['warning'] = f"Turso matching failed: {e}, falling back to config-based hints"

    # Fallback: Match against recall-triggers from config
    try:
        triggers_json = config_get("recall-triggers")
        if triggers_json:
            triggers = json.loads(triggers_json) if isinstance(triggers_json, str) else triggers_json
            trigger_set = set(t.lower() for t in triggers)

            matched_triggers = search_terms & trigger_set
            if matched_triggers:
                result['hints'].append({
                    'memory_id': None,
                    'type': 'hint',
                    'preview': f"Terms match known memory tags: {', '.join(sorted(matched_triggers))}",
                    'matched_terms': list(matched_triggers),
                    'matched_tags': list(matched_triggers),
                    'priority': 0,
                    'relevance_score': len(matched_triggers)
                })
                for term in matched_triggers:
                    result['term_coverage'][term].append('recall-triggers')

            result['unmatched_terms'] = [t for t in search_terms if t not in matched_triggers]

    except Exception as e:
        if not result['warning']:
            result['warning'] = f"Config-based matching failed: {e}"

    return result


def _extract_terms(text: str) -> Set[str]:
    """Extract searchable terms from text."""
    terms = set()

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", text)

    for word in words:
        word_lower = word.lower()
        if len(word_lower) >= 3 and word_lower not in STOP_WORDS:
            terms.add(word_lower)

        parts = re.split(r'_|(?<=[a-z])(?=[A-Z])', word)
        for part in parts:
            part_lower = part.lower()
            if len(part_lower) >= 3 and part_lower not in STOP_WORDS:
                terms.add(part_lower)

    quoted = re.findall(r'["\']([^"\']+)["\']', text)
    for q in quoted:
        if 3 <= len(q) <= 50:
            terms.add(q.lower())

    return terms


def _match_from_turso(terms: Set[str], *, include_tags: bool,
                      include_summaries: bool, min_matches: int) -> tuple:
    """Match terms against memories in Turso.

    Returns (hints, term_coverage) tuple.

    v5.0.0: Replaces _match_from_cache. Queries Turso directly.
    """
    hints = []
    term_coverage = defaultdict(list)
    memory_matches = defaultdict(lambda: {'terms': set(), 'tags': set()})

    for term in terms:
        # Match against tags
        if include_tags:
            rows = _exec(
                """SELECT id, type, summary, priority, tags FROM memories
                   WHERE deleted_at IS NULL AND tags LIKE ?
                   AND id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)
                   LIMIT 20""",
                [f'%"{term}"%']
            )
            for row in rows:
                mem_id = row['id']
                memory_matches[mem_id]['terms'].add(term)
                memory_matches[mem_id]['tags'].add(term)
                memory_matches[mem_id]['data'] = row
                term_coverage[term].append(mem_id)

        # Match against summaries
        if include_summaries:
            rows = _exec(
                """SELECT id, type, summary, priority, tags FROM memories
                   WHERE deleted_at IS NULL AND LOWER(summary) LIKE ?
                   AND id NOT IN (SELECT value FROM memories, json_each(refs) WHERE deleted_at IS NULL)
                   LIMIT 20""",
                [f'%{term}%']
            )
            for row in rows:
                mem_id = row['id']
                memory_matches[mem_id]['terms'].add(term)
                if 'data' not in memory_matches[mem_id]:
                    memory_matches[mem_id]['data'] = row
                term_coverage[term].append(mem_id)

    # Build hints for memories with enough matches
    for mem_id, match_info in memory_matches.items():
        if len(match_info['terms']) >= min_matches:
            data = match_info['data']
            summary = data.get('summary', '')
            preview = summary[:100] + '...' if len(summary) > 100 else summary

            hints.append({
                'memory_id': mem_id,
                'type': data.get('type'),
                'preview': preview,
                'matched_terms': list(match_info['terms']),
                'matched_tags': list(match_info['tags']),
                'priority': data.get('priority', 0),
                'relevance_score': len(match_info['terms']) + len(match_info['tags'])
            })

    hints.sort(key=lambda h: h['relevance_score'], reverse=True)

    return hints, term_coverage


# Common stop words to filter out
STOP_WORDS = {
    # Python keywords
    'and', 'not', 'for', 'with', 'from', 'import', 'class', 'def', 'return',
    'if', 'else', 'elif', 'try', 'except', 'finally', 'while', 'break',
    'continue', 'pass', 'raise', 'yield', 'lambda', 'None', 'True', 'False',
    'none', 'true', 'false', 'self', 'cls',

    # Common English
    'the', 'and', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was',
    'one', 'our', 'out', 'are', 'has', 'have', 'been', 'being', 'some',
    'than', 'then', 'them', 'this', 'that', 'these', 'those', 'what',
    'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'will',
    'with', 'would', 'could', 'should', 'each', 'other', 'into',

    # Common programming terms (too generic to be useful)
    'get', 'set', 'list', 'dict', 'str', 'int', 'bool', 'type', 'print',
    'len', 'range', 'open', 'read', 'write', 'file', 'path', 'name',
    'data', 'value', 'item', 'index', 'key', 'result', 'output', 'input',
}
