"""Strict sequences for test harnesses: silent out-of-range access raises.

Python reports a[i] past the end, but two out-of-range accesses pass silently:
  a[i] with a negative i reads from the end of the sequence,
  a[lo:hi] with hi past the end returns a shorter result.
A fuzzer or property test never sees either. Wrap the input in a strict type
and both raise StrictAccessError, with the offending bounds in the message.

    from strict import strict
    parse(strict(data))      # bytes, bytearray or list

Slices of a strict value are strict too, so the check follows the data
through the parser. Code that hands the value to C (struct.unpack,
int.from_bytes, memoryview) sees plain bytes past that point.

Deliberate negative indexing (a[-1] for "last") raises as well. If the code
under test relies on it, allow it per call site:  strict(data, allow_negative=True).
"""
from __future__ import annotations


class StrictAccessError(IndexError):
    """An access Python would have allowed silently."""


def _check(seq_len: int, key, allow_negative: bool) -> None:
    if isinstance(key, slice):
        if key.step not in (None, 1):
            return
        lo, hi = key.start, key.stop
        for b in (lo, hi):
            if b is not None and b < 0 and not allow_negative:
                raise StrictAccessError(f'negative slice bound {key} on length {seq_len}')
        lo = 0 if lo is None else (lo + seq_len if lo < 0 else lo)
        hi = seq_len if hi is None else (hi + seq_len if hi < 0 else hi)
        if hi > seq_len and hi > lo:
            raise StrictAccessError(f'slice [{key.start}:{key.stop}] past end of length {seq_len}')
        if lo > seq_len:
            raise StrictAccessError(f'slice start {key.start} past end of length {seq_len}')
    elif isinstance(key, int) and key < 0 and not allow_negative:
        raise StrictAccessError(f'negative index {key} on length {seq_len}')


def _make(base: type):
    class Strict(base):  # type: ignore[valid-type, misc]
        _allow_negative = False

        def __getitem__(self, key):
            _check(len(self), key, self._allow_negative)
            r = super().__getitem__(key)
            if isinstance(key, slice):
                r = Strict(r)
                r._allow_negative = self._allow_negative
            return r

        if base is not bytes:
            def __setitem__(self, key, value):
                _check(len(self), key, self._allow_negative)
                super().__setitem__(key, value)

    Strict.__name__ = Strict.__qualname__ = f'Strict{base.__name__.capitalize()}'
    return Strict


StrictBytes = _make(bytes)
StrictBytearray = _make(bytearray)
StrictList = _make(list)


def strict(x, allow_negative: bool = False):
    """Wrap bytes, bytearray or list in its strict counterpart."""
    for base, cls in ((bytes, StrictBytes), (bytearray, StrictBytearray), (list, StrictList)):
        if isinstance(x, base):
            r = cls(x)
            r._allow_negative = allow_negative
            return r
    raise TypeError(f'strict() takes bytes, bytearray or list, not {type(x).__name__}')
