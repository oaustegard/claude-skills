"""Tests for sketch_ops MinHash duplicate detection.

Coverage:
- row_minhash weighted vs unweighted on rows that share a token set but
  differ in token counts (the case #787 reported)
- rows whose tokens are all distinct: both metrics agree
- cmd_dups end to end over a CSV, both metrics, including the printed label
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sketch_ops import cmd_dups, row_minhash

# Same token set {new, york}; counts 2:2 vs 1:1.
# Weighted Jaccard = sum(min)/sum(max) = (1+1)/(2+2) = 0.5.
REPEATED = ["new", "york", "new", "york"]
DISTINCT = ["york", "new"]


class TestRowMinhash(unittest.TestCase):

    def test_unweighted_collapses_repeats(self):
        a = row_minhash(REPEATED, weighted=False)
        b = row_minhash(DISTINCT, weighted=False)
        self.assertEqual(a.jaccard(b), 1.0)

    def test_weighted_separates_by_count(self):
        a = row_minhash(REPEATED, weighted=True)
        b = row_minhash(DISTINCT, weighted=True)
        est = a.jaccard(b)
        self.assertLess(est, 0.9)
        # 128 permutations; ±0.15 is well outside the sampling error here.
        self.assertAlmostEqual(est, 0.5, delta=0.15)

    def test_distinct_tokens_unaffected(self):
        toks = ["alpha", "beta", "gamma", "delta"]
        for weighted in (True, False):
            a = row_minhash(toks, weighted=weighted)
            b = row_minhash(list(reversed(toks)), weighted=weighted)
            self.assertEqual(a.jaccard(b), 1.0, f"weighted={weighted}")

    def test_weighted_default(self):
        self.assertEqual(
            row_minhash(REPEATED).digest().tolist(),
            row_minhash(REPEATED, weighted=True).digest().tolist(),
        )


class TestCmdDups(unittest.TestCase):
    """The two rows are not exact duplicates, so only the sketch separates them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.csv = Path(self.tmp.name) / "counts.csv"
        self.csv.write_text("city\nnew york new york\nyork new\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_dups(argv)
        return buf.getvalue()

    def test_weighted_rejects_the_pair(self):
        out = self._run([str(self.csv), "--threshold", "0.9"])
        self.assertIn("0 exact duplicates", out)
        self.assertIn("0 near-duplicate pairs at weighted Jaccard>=0.9", out)

    def test_unweighted_matches_the_pair(self):
        out = self._run([str(self.csv), "--threshold", "0.9", "--unweighted"])
        self.assertIn("1 near-duplicate pairs at Jaccard>=0.9", out)

    def test_exact_duplicates_still_counted(self):
        csv = Path(self.tmp.name) / "exact.csv"
        csv.write_text("city\nnew york new york\nnew york new york\n")
        out = self._run([str(csv)])
        self.assertIn("1 exact duplicates", out)


if __name__ == "__main__":
    unittest.main()
