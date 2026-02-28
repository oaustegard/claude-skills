"""
MemoryResult - Type-safe wrapper for memory query results.

v3.4.0: Added to provide immediate validation on field access.
Replaces plain dicts returned by recall() to catch field name errors at access time.
"""

from typing import Any, Iterator, List, Optional, Set


# Valid fields that can be accessed on memory results
VALID_FIELDS: Set[str] = {
    # Core identifiers
    'id',
    'type',
    't',  # timestamp

    # Content
    'summary',
    'summary_preview',  # v3.7.0: first 100 chars, always computed
    'confidence',
    'tags',
    'refs',
    'priority',

    # Session tracking (v3.2.0)
    'session_id',

    # Temporal fields
    'created_at',
    'updated_at',
    'valid_from',

    # Access tracking
    'access_count',
    'last_accessed',

    # Ranking (from cache queries, may not always be present)
    'bm25_score',
    'composite_rank',
    'composite_score',

    # Decision metadata (v4.2.0, #254)
    'alternatives',

    # Cache/internal flags
    'has_full',
    'deleted_at',
}

# Common mistakes mapping - helps users fix errors
COMMON_MISTAKES = {
    'content': 'summary',  # Most common mistake
    'text': 'summary',
    'body': 'summary',
    'message': 'summary',
    'value': 'summary',
    'memory': 'summary',
    'what': 'summary',
    'conf': 'confidence',
    'score': 'confidence',
    'timestamp': 't',
    'time': 't',
    'datetime': 't',
    'date': 't',
    'created': 'created_at',
    'updated': 'updated_at',
    'tag': 'tags',
    'ref': 'refs',
    'references': 'refs',
    'prio': 'priority',
    'importance': 'priority',
    'session': 'session_id',
    'accesses': 'access_count',
    'access': 'access_count',
    'last_access': 'last_accessed',
}


class MemoryResult:
    """Type-safe wrapper for memory query results.

    Provides immediate validation when accessing fields, raising AttributeError
    or KeyError with helpful messages for invalid field names.

    Supports both attribute-style (m.summary) and dict-style (m['summary']) access.
    Maintains full backward compatibility with existing code using dict access.

    Example:
        >>> m = MemoryResult({'id': 'abc', 'summary': 'test', 'type': 'world'})
        >>> m.summary  # 'test'
        >>> m['summary']  # 'test'
        >>> m.content  # AttributeError: Invalid field 'content'. Did you mean 'summary'?
        >>> m['content']  # KeyError: Invalid field 'content'. Did you mean 'summary'?
    """

    __slots__ = ('_data',)

    def __init__(self, data: dict):
        """Initialize with a memory dictionary from recall()."""
        object.__setattr__(self, '_data', data)

    def __getattr__(self, name: str) -> Any:
        """Attribute-style access with validation and alias resolution.

        v3.7.0: Common field aliases (e.g., 'content' -> 'summary') are
        transparently resolved instead of raising errors.
        """
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

        # Resolve aliases transparently (v3.7.0)
        if name in COMMON_MISTAKES:
            name = COMMON_MISTAKES[name]

        if name not in VALID_FIELDS:
            raise AttributeError(self._error_message(name, 'AttributeError'))

        return self._data.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent attribute modification (results are read-only)."""
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(f"MemoryResult is read-only. Cannot set '{name}'.")

    def __getitem__(self, key: str) -> Any:
        """Dict-style access with validation and alias resolution.

        v3.7.0: Common field aliases (e.g., 'content' -> 'summary') are
        transparently resolved instead of raising errors.
        """
        # Resolve aliases transparently (v3.7.0)
        if key in COMMON_MISTAKES:
            key = COMMON_MISTAKES[key]

        if key not in VALID_FIELDS:
            raise KeyError(self._error_message(key, 'KeyError'))

        return self._data.get(key)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for checking field presence."""
        return key in VALID_FIELDS and key in self._data

    def __iter__(self) -> Iterator[str]:
        """Iterate over valid fields that have values."""
        return iter(k for k in self._data if k in VALID_FIELDS)

    def __len__(self) -> int:
        """Return count of fields with values."""
        return len([k for k in self._data if k in VALID_FIELDS])

    def __repr__(self) -> str:
        """Human-readable representation."""
        summary = self._data.get('summary', '')
        if len(summary) > 50:
            summary = summary[:47] + '...'
        return f"MemoryResult(id={self._data.get('id', '?')[:8]}..., type={self._data.get('type')}, summary={summary!r})"

    def __str__(self) -> str:
        """String representation showing key fields."""
        return f"[{self._data.get('type', '?')}] {self._data.get('summary', '')}"

    def _error_message(self, field: str, error_type: str) -> str:
        """Generate helpful error message for invalid field access."""
        msg = f"Invalid field '{field}'."

        # Check for common mistakes
        if field in COMMON_MISTAKES:
            correct = COMMON_MISTAKES[field]
            msg += f" Did you mean '{correct}'?"
        else:
            # Show valid fields
            msg += f"\n\nValid fields: {', '.join(sorted(VALID_FIELDS))}"

        return msg

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get() with validation and alias resolution.

        v3.7.0: Common field aliases are transparently resolved.

        Args:
            key: Field name to access
            default: Value to return if field is not set (but key must still be valid)

        Raises:
            KeyError: If key is not a valid field name
        """
        # Resolve aliases transparently (v3.7.0)
        if key in COMMON_MISTAKES:
            key = COMMON_MISTAKES[key]
        if key not in VALID_FIELDS:
            raise KeyError(self._error_message(key, 'KeyError'))
        return self._data.get(key, default)

    def keys(self) -> List[str]:
        """Return list of valid field names that have values."""
        return [k for k in self._data if k in VALID_FIELDS]

    def values(self) -> List[Any]:
        """Return list of values for valid fields."""
        return [v for k, v in self._data.items() if k in VALID_FIELDS]

    def items(self) -> List[tuple]:
        """Return list of (key, value) pairs for valid fields."""
        return [(k, v) for k, v in self._data.items() if k in VALID_FIELDS]

    def to_dict(self) -> dict:
        """Convert back to plain dictionary.

        Use when you need raw dict access without validation,
        or for serialization.
        """
        return dict(self._data)

    # Support for common dict operations that code might use
    def copy(self) -> dict:
        """Return a copy as a plain dict."""
        return dict(self._data)


class MemoryResultList(list):
    """List subclass that wraps results from recall() functions.

    Behaves exactly like a normal list but ensures all elements
    are MemoryResult objects. Provides helpful __repr__ for debugging.
    """

    def __repr__(self) -> str:
        if not self:
            return "MemoryResultList([])"
        return f"MemoryResultList([{len(self)} memories])"

    def to_dicts(self) -> List[dict]:
        """Convert all results back to plain dictionaries."""
        return [m.to_dict() if isinstance(m, MemoryResult) else m for m in self]


def _normalize_memory(data: dict) -> dict:
    """Ensure a memory dict has all standard computed fields.

    v5.1.0: summary_preview now includes tag context for multi-topic memories (#309).
    v3.7.0: Normalizes results from any source (cache or Turso) to have
    a consistent set of fields, preventing silent failures when code
    assumes fields like summary_preview exist.

    Adds missing computed fields:
    - summary_preview: Tag-prefixed first ~100 chars of summary (if summary present)
    - alternatives: Extracted from refs for decision memories (v4.2.0, #254)
    """
    if 'summary_preview' not in data and 'summary' in data:
        summary = data.get('summary') or ''
        tags_raw = data.get('tags')

        # v5.1.0: Front-load tag context in preview for large multi-topic memories (#309)
        # This ensures previews capture topical scope even when content starts with
        # structurally-first (but potentially less relevant) material.
        tag_prefix = ''
        if tags_raw:
            import json
            try:
                tag_list = json.loads(tags_raw) if isinstance(tags_raw, str) else (tags_raw or [])
            except (json.JSONDecodeError, TypeError):
                tag_list = []
            if tag_list and len(summary) > 150:
                # Only prefix tags on large memories where preview truncation matters
                tag_prefix = '[' + ', '.join(tag_list[:5]) + '] '

        preview_budget = 100 - len(tag_prefix)
        data['summary_preview'] = tag_prefix + summary[:max(preview_budget, 50)]

    # v4.2.0: Extract alternatives from refs for decision memories (#254)
    if 'alternatives' not in data and data.get('type') == 'decision':
        refs_raw = data.get('refs')
        alternatives = []
        if refs_raw:
            try:
                import json
                refs = json.loads(refs_raw) if isinstance(refs_raw, str) else (refs_raw or [])
                for entry in refs:
                    if isinstance(entry, dict) and entry.get('_type') == 'alternatives':
                        alternatives = entry.get('items', [])
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        data['alternatives'] = alternatives if alternatives else None

    return data


def wrap_results(results: List[dict]) -> MemoryResultList:
    """Wrap a list of memory dicts in MemoryResult objects.

    v3.7.0: Normalizes all results to have consistent computed fields
    regardless of whether they came from cache or Turso.

    Args:
        results: List of memory dictionaries from database queries

    Returns:
        MemoryResultList containing MemoryResult objects
    """
    wrapped = MemoryResultList()
    for r in results:
        if isinstance(r, MemoryResult):
            wrapped.append(r)
        elif isinstance(r, dict):
            wrapped.append(MemoryResult(_normalize_memory(r)))
        else:
            # Pass through anything else unchanged
            wrapped.append(r)
    return wrapped
