"""Tests for scripts/claims.py — the declared-invariant inventory.

A claim is a test whose docstring opens `invariant:`. The parts that can go
wrong are the parsing (what counts as a declaration, and how much of the
docstring the refutation swallows) and the anchoring (which registry, if any,
the claiming test actually iterates).

The anchoring case that matters is this repository's own shape: a test that
loads its subject through `importlib` and reaches a registry as
`tl.SKIP_DIRS`. Peeling that attribute down to its object lands on the local
module handle, and following THAT through the file's own constants lands on
`_SPEC` — true, useless, and it shadows the name that matters. Pinned below.

    python3 tests/test_claims.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "claims", Path(__file__).resolve().parent.parent / "scripts" / "claims.py"
)
cl = importlib.util.module_from_spec(_SPEC)
sys.modules["claims"] = cl
_SPEC.loader.exec_module(cl)


def inv(**files):
    """Write {relpath: source} into a temp tree and take its inventory."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for rel, src in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(textwrap.dedent(src))
        claims, registries, stats = cl.inventory(root)
        return claims, registries, stats, cl.findings_for(claims, registries)


SRC = 'ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}\n'


class Declaration(unittest.TestCase):

    def test_a_docstring_opening_with_invariant_is_a_claim(self):
        claims, _, stats, _ = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                from pkg.mod import ROTATION_CODES

                def test_x():
                    """invariant: every rotation round-trips."""
                    for r in ROTATION_CODES:
                        assert r
            ''',
        })
        self.assertEqual(stats["claims"], 1)
        self.assertEqual(claims[0].statement, "every rotation round-trips")

    def test_an_ordinary_docstring_is_not_a_claim(self):
        claims, _, _, _ = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                def test_x():
                    """Checks the thing."""
                    assert True
            ''',
        })
        self.assertEqual(claims, [])

    def test_the_marker_must_open_the_docstring(self):
        """A mention buried in prose is discussion, not a declaration."""
        claims, _, _, _ = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                def test_x():
                    """Checks the thing.

                    invariant: this is a sentence about invariants.
                    """
                    assert True
            ''',
        })
        self.assertEqual(claims, [])

    def test_a_test_with_no_docstring_is_skipped(self):
        claims, _, _, _ = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": "def test_x():\n    assert True\n",
        })
        self.assertEqual(claims, [])


class Refutation(unittest.TestCase):

    def _claim(self, doc: str):
        """doc is the docstring body; it is indented here, not by the caller."""
        body = "\n".join(
            ("        " + ln if ln.strip() else "") for ln in doc.splitlines()
        ).strip("\n")
        src = (
            "from pkg.mod import ROTATION_CODES\n\n\n"
            "def test_x():\n"
            '    """' + body.lstrip() + '\n    """\n'
            "    for r in ROTATION_CODES:\n"
            "        assert r\n"
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pkg" / "tests").mkdir(parents=True)
            (root / "pkg" / "mod.py").write_text(SRC)
            (root / "pkg" / "tests" / "test_it.py").write_text(src)
            claims, _, _ = cl.inventory(root)
        self.assertEqual(len(claims), 1, src)
        return claims[0]

    def test_a_refutation_is_captured(self):
        c = self._claim(
            'invariant: every rotation round-trips.\n'
            '\n'
            'refuted: added "hadamard2" -> suite green, this went red.\n'
        )
        self.assertIsNotNone(c.refuted)
        self.assertIn("hadamard2", c.refuted)

    def test_a_refutation_stops_at_its_paragraph(self):
        c = self._claim(
            'invariant: every rotation round-trips.\n'
            '\n'
            'refuted: added "hadamard2", this went red.\n'
            '\n'
            'Unrelated closing note that is not part of the refutation.\n'
        )
        self.assertNotIn("Unrelated", c.refuted)

    def test_a_claim_with_no_refutation_is_reported(self):
        _, _, _, f = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                from pkg.mod import ROTATION_CODES

                def test_x():
                    """invariant: every rotation round-trips."""
                    for r in ROTATION_CODES:
                        assert r
            ''',
        })
        self.assertIn("unrefuted", [x.kind for x in f])

    def test_a_refuted_claim_is_not(self):
        _, _, _, f = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                from pkg.mod import ROTATION_CODES

                def test_x():
                    """invariant: every rotation round-trips.

                    refuted: added a member -> this went red.
                    """
                    for r in ROTATION_CODES:
                        assert r
            ''',
        })
        self.assertNotIn("unrefuted", [x.kind for x in f])


class Anchoring(unittest.TestCase):

    def test_a_live_iteration_records_the_registry(self):
        claims, _, _, _ = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                from pkg.mod import ROTATION_CODES

                def test_x():
                    """invariant: every rotation round-trips.

                    refuted: yes.
                    """
                    for r in ROTATION_CODES:
                        assert r
            ''',
        })
        self.assertEqual(claims[0].anchors, ["ROTATION_CODES"])

    def test_an_importlib_loaded_module_attribute_still_anchors(self):
        """The shape this repository's own tests take.

        `tl.SKIP_DIRS` peels to the module handle `tl`, and following `tl`
        through the test file's constants lands on `_SPEC`. The attribute name
        has to win, or every claim in this repo reads as unanchored.
        """
        claims, _, _, _ = inv(**{
            "scripts/thing.py": 'SKIP_DIRS = {"a", "b", "c"}\n',
            "tests/test_thing.py": '''
                import importlib.util

                _SPEC = importlib.util.spec_from_file_location("t", "scripts/thing.py")
                tl = importlib.util.module_from_spec(_SPEC)

                def test_x():
                    """invariant: every skipped name is skipped.

                    refuted: yes.
                    """
                    for name in sorted(tl.SKIP_DIRS):
                        assert name
            ''',
        })
        self.assertEqual(claims[0].anchors, ["SKIP_DIRS"])

    def test_a_claim_over_a_copied_literal_is_reported(self):
        claims, _, _, f = inv(**{
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                import pytest
                from pkg.mod import ROTATION_CODES

                @pytest.mark.parametrize("r", ["haar", "rht"])
                def test_x(r):
                    """invariant: every rotation is accepted.

                    refuted: yes.
                    """
                    assert r
            ''',
        })
        self.assertEqual(claims[0].copies, ["ROTATION_CODES"])
        self.assertIn("literal", [x.kind for x in f])


class Unanchored(unittest.TestCase):

    def test_a_registry_no_invariant_names_is_reported(self):
        _, _, _, f = inv(**{
            "pkg/mod.py": 'WATCHED = {"a": 1, "b": 2, "c": 3}\n'
                          'IGNORED = {"x": 1, "y": 2, "z": 3}\n',
            "pkg/tests/test_it.py": '''
                from pkg.mod import WATCHED

                def test_x():
                    """invariant: watched holds.

                    refuted: yes.
                    """
                    for k in WATCHED:
                        assert k
            ''',
        })
        un = [x.detail for x in f if x.kind == "unanchored"]
        self.assertTrue(any("IGNORED" in d for d in un), str(un))
        self.assertFalse(any("WATCHED" in d for d in un), str(un))


class Robustness(unittest.TestCase):

    def test_an_unparseable_file_is_skipped_not_fatal(self):
        claims, _, _, _ = inv(**{
            "pkg/broken.py": "def (((:\n",
            "pkg/mod.py": SRC,
            "pkg/tests/test_it.py": '''
                from pkg.mod import ROTATION_CODES

                def test_x():
                    """invariant: it holds.

                    refuted: yes.
                    """
                    for r in ROTATION_CODES:
                        assert r
            ''',
        })
        self.assertEqual(len(claims), 1)

    def test_an_empty_tree_reports_nothing(self):
        claims, _, stats, f = inv(**{"README.md": "nothing\n"})
        self.assertEqual((claims, f), ([], []))
        self.assertEqual(stats["claims"], 0)

    def test_the_report_renders_with_no_claims(self):
        out = cl.report([], [], {"claims": 0, "refuted": 0, "registries": 0})
        self.assertIn("nothing to report", out)

    def test_strict_exits_nonzero_only_on_a_finding(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(cl.main([td, "--strict"]), 0)

    def test_selftest_passes(self):
        self.assertEqual(cl.selftest(), 0)


class Ratchets(unittest.TestCase):
    """A hand-list marked `ratchet` anchors a claim; it is not a copy."""

    SRC = 'ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}\n'

    BODY = """
        from pkg.mod import ROTATION_CODES

        MARKER
        def test_x():
            '''invariant: a shipped rotation never leaves.

            refuted: yes.
            '''
            for shipped in MEMBERS:
                assert shipped in ROTATION_CODES
    """

    def _tree(self, marker, members):
        body = self.BODY.replace("MARKER", marker).replace("MEMBERS", members)
        return {"pkg/mod.py": self.SRC, "pkg/tests/test_it.py": body}

    def test_a_ratchet_anchors_rather_than_copying(self):
        claims, _, _, f = inv(**self._tree(
            "# totality: ratchet — these two shipped first", '("haar", "rht")'))
        self.assertEqual(claims[0].ratchets, ["ROTATION_CODES"])
        self.assertEqual(claims[0].copies, [])
        self.assertNotIn("literal", [x.kind for x in f])

    def test_an_unmarked_subset_is_still_a_copy(self):
        claims, _, _, f = inv(**self._tree("# ordinary comment", '("haar", "rht")'))
        self.assertEqual(claims[0].copies, ["ROTATION_CODES"])
        self.assertIn("literal", [x.kind for x in f])

    def test_a_ratcheted_registry_is_not_unanchored(self):
        _, _, _, f = inv(**self._tree(
            "# totality: ratchet — all three shipped", '("haar", "rht", "none")'))
        un = [x.detail for x in f if x.kind == "unanchored"]
        self.assertFalse(any("ROTATION_CODES" in d for d in un), str(un))

if __name__ == "__main__":
    unittest.main(verbosity=2)
