"""
Sparse N-gram extraction for fast regex search indexing.

Based on the approach described by Cursor (2026): variable-length n-grams
selected deterministically via a weight function over character pairs.

Two modes:
- build_all: Extract ALL valid sparse n-grams (used at index time)
- build_covering: Extract MINIMAL covering set (used at query time)

A sparse n-gram is a substring where the character-pair weights at both
boundary positions are strictly greater than all interior weights.
"""

import zlib
from typing import List, Tuple, Optional
from collections import Counter


def weight_crc32(a: int, b: int) -> int:
    """CRC32-based weight for a character pair. Deterministic, uniform."""
    return zlib.crc32(bytes([a, b])) & 0xFFFFFFFF


class FrequencyWeights:
    """
    Frequency-based weight function: rare character pairs get HIGH weights,
    common pairs get LOW weights. This produces longer n-grams at rare
    boundaries (more selective posting lists) and shorter n-grams at common
    boundaries (acceptable since they appear everywhere anyway).
    """

    def __init__(self):
        self._freq: dict[tuple[int, int], int] = {}
        self._max_freq: int = 1
        self._frozen = False

    def train(self, data: bytes):
        """Accumulate character pair frequencies from training data."""
        if self._frozen:
            raise RuntimeError("Cannot train after freezing")
        for i in range(len(data) - 1):
            pair = (data[i], data[i + 1])
            self._freq[pair] = self._freq.get(pair, 0) + 1

    def freeze(self):
        """Finalize the frequency table. Converts frequencies to weights."""
        if self._freq:
            self._max_freq = max(self._freq.values())
        self._frozen = True

    def weight(self, a: int, b: int) -> int:
        """
        Weight for a character pair. Higher = rarer.
        Uses inverted frequency: rare pairs get high weights.
        Falls back to CRC32 for unseen pairs (treated as very rare).
        """
        if not self._frozen:
            raise RuntimeError("Must freeze() before computing weights")
        freq = self._freq.get((a, b), 0)
        if freq == 0:
            # Unseen pair = very rare = high weight
            return self._max_freq + weight_crc32(a, b) % (self._max_freq // 2 + 1)
        # Invert: rare = high weight
        return self._max_freq - freq + 1

    def save(self) -> bytes:
        """Serialize frequency table."""
        import json
        data = {
            "freq": {f"{a},{b}": c for (a, b), c in self._freq.items()},
            "max_freq": self._max_freq,
        }
        return json.dumps(data).encode()

    @classmethod
    def load(cls, raw: bytes) -> "FrequencyWeights":
        """Deserialize frequency table."""
        import json
        data = json.loads(raw)
        w = cls()
        w._freq = {
            (int(k.split(",")[0]), int(k.split(",")[1])): v
            for k, v in data["freq"].items()
        }
        w._max_freq = data["max_freq"]
        w._frozen = True
        return w


def compute_weights(
    text: bytes, weight_fn=weight_crc32
) -> List[int]:
    """Compute weights for all consecutive character pairs in text."""
    if len(text) < 2:
        return []
    return [weight_fn(text[i], text[i + 1]) for i in range(len(text) - 1)]


def build_all(weights: List[int]) -> List[Tuple[int, int]]:
    """
    Extract ALL valid sparse n-grams from a weight sequence.

    Uses a monotone stack algorithm (O(n) amortized).

    Returns list of (start_pair_pos, end_pair_pos) where each n-gram
    spans characters [start_pair_pos, end_pair_pos + 2) in the original text.

    A sparse n-gram from pair position a to pair position b is valid iff
    w[a] > w[k] and w[b] > w[k] for all a < k < b.
    """
    n = len(weights)
    if n == 0:
        return []
    if n == 1:
        return [(0, 0)]

    ngrams = []
    # Monotone decreasing stack of pair positions
    stack: List[int] = []

    for i in range(n):
        # Pop positions dominated by current weight
        while stack and weights[i] >= weights[stack[-1]]:
            j = stack.pop()
            # (j, i) is valid: j and i are both >= weights[j],
            # and everything between j and i on the stack was already
            # popped (so had weight < w[j] < w[i])
            ngrams.append((j, i))

        # Adjacent stack entry to current position forms valid n-gram
        if stack:
            ngrams.append((stack[-1], i))

        stack.append(i)

    return ngrams


def build_covering(weights: List[int]) -> List[Tuple[int, int]]:
    """
    Extract the MINIMAL covering set of sparse n-grams.

    Used at query time: produces the fewest, longest n-grams needed
    to look up in the index. Any document containing the query text
    must contain all of these n-grams.

    Greedy: from each position, jump to the farthest valid endpoint
    (the first position with weight >= current).
    """
    n = len(weights)
    if n == 0:
        return []
    if n == 1:
        return [(0, 0)]

    ngrams = []
    i = 0

    while i < n:
        # Find the first position j > i where w[j] >= w[i]
        j = i + 1
        while j < n and weights[j] < weights[i]:
            j += 1

        if j >= n:
            # No higher weight found — take the highest remaining position
            # as the endpoint (best available boundary)
            if i < n - 1:
                best = i + 1
                for k in range(i + 2, n):
                    if weights[k] > weights[best]:
                        best = k
                ngrams.append((i, best))
                i = best
            else:
                # At the last position, nothing more to cover
                break
        else:
            ngrams.append((i, j))
            i = j

    return ngrams


def ngram_text(text: bytes, start: int, end: int) -> bytes:
    """
    Extract the n-gram substring from text given pair positions.
    Pair position p corresponds to characters text[p:p+2].
    N-gram from pair a to pair b spans text[a:b+2].
    """
    return text[start : end + 2]


def ngram_hash(text: bytes, start: int, end: int) -> int:
    """Hash an n-gram for use as index key. Uses CRC32 for speed."""
    return zlib.crc32(text[start : end + 2]) & 0xFFFFFFFF
