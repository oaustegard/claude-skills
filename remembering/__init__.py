"""
Remembering - Minimal persistent memory for Claude.

Usage:
    from remembering import remember, recall

    remember("User prefers concise answers")
    recall()  # recent memories
    recall("deadline")  # search
    recall(tags=["task"])  # filter
"""

from .core import store, query, forget, infer_type

def remember(what: str, *, tags: list = None, conf: float = None, 
             type: str = None, entities: list = None, refs: list = None) -> str:
    """
    Store a memory. Returns memory ID.
    
    Examples:
        remember("User prefers code examples")
        remember("Deadline is Friday", tags=["project"])
        remember("Always use dark mode", conf=0.95)
    """
    return store(what, type=type, tags=tags, entities=entities, confidence=conf, refs=refs)

def recall(search: str = None, *, n: int = 10, tags: list = None, 
           type: str = None, conf: float = None) -> list:
    """
    Query memories.
    
    Examples:
        recall()                    # recent 10
        recall(20)                  # recent 20 (positional n)
        recall("deadline")          # search summaries
        recall(tags=["task"])       # by tags
        recall(type="decision")     # by type
        recall(conf=0.8)            # min confidence
    """
    # Handle positional int as limit
    if isinstance(search, int):
        return query(limit=search)
    return query(search=search, tags=tags, type=type, conf=conf, limit=n)

# Short aliases
r = remember
q = recall

__all__ = ["remember", "recall", "forget", "r", "q"]
