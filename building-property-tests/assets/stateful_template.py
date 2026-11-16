"""Model-based stateful harness, Hypothesis RuleBasedStateMachine.

Runs as-is against the toy ``CachedStore`` below so the shape can be checked
before it is adapted. Replace the SUBJECT section with the code under test and
the MODEL section with the simplest correct implementation you can write.

    pytest -q stateful_template.py                          # should pass
    MUTANT=stale_cache pytest -q stateful_template.py       # must fail by AssertionError
    SKIP_KNOWN=0 pytest -q stateful_template.py             # stop skipping known findings
    python3 ../scripts/hypothesis_stats.py --min overwrite-after-read=5 -- pytest -q stateful_template.py
"""
import os

from hypothesis import event, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

MUTANT = os.environ.get("MUTANT")
SKIP_KNOWN = os.environ.get("SKIP_KNOWN", "1") == "1"

# ---------- SUBJECT (replace) ----------
class CachedStore:
    """Toy subject: a dict with a read cache that put/remove must invalidate."""

    def __init__(self):
        self._data, self._cache = {}, {}

    def put(self, k, v):
        if not isinstance(k, str):
            raise TypeError("keys are strings")
        self._data[k] = v
        if MUTANT != "stale_cache":  # planted defect for calibration
            self._cache.pop(k, None)

    def get(self, k):
        if k not in self._cache:
            self._cache[k] = self._data.get(k)
        return self._cache[k]

    def remove(self, k):
        self._data.pop(k, None)
        self._cache.pop(k, None)

    def __len__(self):
        return len(self._data)


# ---------- MODEL (replace): independent, no production helpers ----------
# The model for a cached store is a plain dict: it has no cache to forget.

# ---------- generators: small pools so operations collide ----------
KEYS = st.sampled_from(["a", "b", "c"])  # 3 keys: overwrites and re-reads are common
VALUES = st.integers(0, 3)               # few values, so a stale read is visible


class StoreMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.subject = CachedStore()
        self.model = {}
        self.read = set()  # keys whose value the subject may have cached

    @rule(k=KEYS, v=VALUES)
    def put(self, k, v):
        if k in self.read and self.model.get(k) != v:
            event("overwrite-after-read")  # the interaction a stale cache needs
        self.subject.put(k, v)
        self.model[k] = v

    @rule(k=KEYS)
    def remove(self, k):
        self.subject.remove(k)
        self.model.pop(k, None)
        self.read.discard(k)

    @rule(k=KEYS)
    def get(self, k):
        # A confirmed, unfixed finding: return before the state that triggers
        # it so the search continues past it, e.g.
        #     if SKIP_KNOWN and not self.model: return   # finding 2, empty store
        # Its deterministic regression lives in test_regressions.py.
        self.read.add(k)
        assert self.subject.get(k) == self.model.get(k), (k, self.model)

    @rule(v=VALUES)
    def rejected_put_changes_nothing(self, v):
        """A rejected operation must leave every observable unchanged."""
        before = {k: self.subject.get(k) for k in "abc"}
        self.read.update("abc")
        try:
            self.subject.put(0, v)
        except TypeError:
            pass
        else:
            raise AssertionError("non-string key was accepted")
        assert {k: self.subject.get(k) for k in "abc"} == before

    @invariant()
    def sizes_agree(self):
        assert len(self.subject) == len(self.model)


TestStore = StoreMachine.TestCase
TestStore.settings = settings(max_examples=int(os.environ.get("N", "300")),
                              stateful_step_count=30, deadline=None)
