"""Tests for scripts/totality_lint.py — the copied-domain report.

The lint's whole value is precision: a wall of candidates is worse than
silence, and its two precision mechanisms both came from a measured false
positive rather than from taste.

  * `no-floor` originally fired on every `for x in <local>`, which produced 27
    findings on `remex` — numpy arrays, query matrices, loop counters, all
    noise. It now fires only on a name independently recognised as a registry.
  * `sampled-domain` originally matched a literal against any registry in the
    tree, which on the `experiments` monorepo joined a test in `discrepancy/`
    to registries in `kb-k-sweep/` and `remex-vs-higgs-ablation/` because
    small integer sets collide. It now requires reachability: an import, or a
    shared top-level directory.

Both are pinned below. `--selftest` carries the fixture suite; this adds the
regressions those two measurements produced, and asserts the classifier
directly.

    python3 tests/test_totality_lint.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "totality_lint",
    Path(__file__).resolve().parent.parent / "scripts" / "totality_lint.py",
)
tl = importlib.util.module_from_spec(_SPEC)
# Register before exec: `@dataclass` resolves annotations through
# sys.modules[cls.__module__], which is None for a spec-loaded module.
sys.modules["totality_lint"] = tl
_SPEC.loader.exec_module(tl)


def scan_files(**files) -> list:
    """Write {relpath: source} into a temp tree and scan it."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for rel, src in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(textwrap.dedent(src))
        findings, _ = tl.scan(root)
        return findings


def kinds(findings, test=None):
    return sorted(
        f.kind for f in findings if test is None or f.test == test
    )


class Registries(unittest.TestCase):
    """What counts as an enumerated domain in source."""

    def regs(self, src):
        import ast
        return tl._registries_py(ast.parse(textwrap.dedent(src)), "m.py")

    def test_dict_contributes_its_keys(self):
        r = self.regs('CODES = {"a": 0, "b": 1, "c": 2}')
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].members, frozenset({"a", "b", "c"}))
        self.assertEqual(r[0].kind, "dict")

    def test_tuple_set_and_list_all_count(self):
        r = self.regs("""
            T = (1, 2, 3)
            S = {"x", "y", "z"}
            L = ["p", "q", "r"]
        """)
        self.assertEqual({x.kind for x in r}, {"tuple", "set", "list"})

    def test_enum_members_are_the_domain(self):
        r = self.regs("""
            from enum import Enum

            class Colour(Enum):
                RED = 1
                GREEN = 2
                BLUE = 3
        """)
        self.assertEqual([x.name for x in r], ["Colour"])
        self.assertEqual(r[0].members, frozenset({"RED", "GREEN", "BLUE"}))

    def test_class_attribute_registry_is_qualified(self):
        r = self.regs("""
            class Q:
                ROTATIONS = {"haar": 1, "rht": 2, "none": 3}
        """)
        self.assertEqual([x.name for x in r], ["Q.ROTATIONS"])

    def test_below_min_registry_is_not_a_domain(self):
        self.assertEqual(self.regs('PAIR = {"a": 1, "b": 2}'), [])

    def test_a_non_constant_member_disqualifies_the_whole_collection(self):
        self.assertEqual(self.regs("T = (1, 2, compute())"), [])

    def test_a_spread_disqualifies_a_dict(self):
        self.assertEqual(self.regs("D = {**other, 'a': 1, 'b': 2, 'c': 3}"), [])


class SampledDomain(unittest.TestCase):

    SRC = 'ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}\n'

    def test_a_strict_subset_is_reported_with_what_is_missing(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                @pytest.mark.parametrize("r", ["haar", "rht"])
                def test_x(r): assert r
            """,
        })
        self.assertEqual(kinds(f), ["sampled-domain"])
        self.assertEqual(f[0].missing, ["none"])
        self.assertEqual(f[0].registry, "ROTATION_CODES")

    def test_the_full_domain_as_a_literal_is_not_a_finding(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                @pytest.mark.parametrize("r", ["haar", "rht", "none"])
                def test_x(r): assert r
            """,
        })
        self.assertEqual(kinds(f), [])

    def test_a_superset_is_not_a_finding(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                @pytest.mark.parametrize("r", ["haar", "rht", "none", "extra"])
                def test_x(r): assert r
            """,
        })
        self.assertEqual(kinds(f), [])

    def test_a_multi_parameter_table_is_out_of_scope(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                @pytest.mark.parametrize("r,n", [("haar", 1), ("rht", 2)])
                def test_x(r, n): assert r
            """,
        })
        self.assertEqual(kinds(f), [])

    def test_a_same_file_const_is_still_a_literal(self):
        """Binding the copy to a name first does not make it live."""
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                CASES = ["haar", "rht"]

                @pytest.mark.parametrize("r", CASES)
                def test_x(r): assert r
            """,
        })
        self.assertEqual(kinds(f), ["sampled-domain"])


class Reachability(unittest.TestCase):
    """Measured on `experiments`: 3 of 4 findings were cross-project noise."""

    NUMERIC = "KS = [1, 2, 3, 4]\n"

    def test_an_unrelated_project_is_not_matched(self):
        f = scan_files(**{
            "kb-k-sweep/srht.py": self.NUMERIC,
            "discrepancy/tests/test_calibration.py": """
                def test_x():
                    for k in [1, 2, 3]:
                        assert k
            """,
        })
        self.assertEqual(kinds(f), [])

    def test_an_import_makes_it_reachable(self):
        f = scan_files(**{
            "kb_k_sweep/srht.py": self.NUMERIC,
            "discrepancy/tests/test_calibration.py": """
                from kb_k_sweep.srht import KS

                def test_x():
                    for k in [1, 2, 3]:
                        assert k
            """,
        })
        self.assertEqual(kinds(f), ["sampled-domain"])

    def test_a_shared_top_level_directory_makes_it_reachable(self):
        f = scan_files(**{
            "caps/conditions.py": "DOSE = [0.0, 0.1, 0.5, 1.0]\n",
            "caps/test_lib.py": """
                def test_x():
                    for d in (0.0, 0.5, 1.0):
                        assert d >= 0
            """,
        })
        self.assertEqual(kinds(f), ["sampled-domain"])
        self.assertEqual(f[0].missing, [0.1])


class NoFloor(unittest.TestCase):
    """Measured on `remex`: firing on every local produced 27 noise findings.

    A live enumeration with no ratchet would also raise `unratcheted`, but the
    two landed on the same line saying overlapping things (3 of 3 on
    `claude-workspace`), so `no-floor` — the narrower statement, naming the same
    fix first — wins the line. See `Ratchet` below for `unratcheted` on its own.
    """

    SRC = 'ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}\n'

    def test_the_finding_names_the_registry_not_the_module_handle(self):
        """`for k in bra.CLASS.items()` is about CLASS, not about `bra`.

        The resolved root of an importlib-loaded attribute chain is the local
        module handle, which named `_spec` in this repo's own report before the
        message was keyed on the matched registry instead.
        """
        f = scan_files(**{
            "scripts/thing.py": 'CLASS = {"a": 1, "b": 2, "c": 3}\n',
            "tests/test_thing.py": """
                import importlib.util

                _spec = importlib.util.spec_from_file_location("t", "x.py")
                bra = importlib.util.module_from_spec(_spec)

                def test_x():
                    for k in bra.CLASS:
                        assert k
            """,
        })
        self.assertEqual(kinds(f), ["no-floor"])
        self.assertIn("`CLASS`", f[0].detail)
        self.assertNotIn("_spec", f[0].detail)

    def test_a_live_registry_without_a_floor_is_reported(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                @pytest.mark.parametrize("r", sorted(ROTATION_CODES))
                def test_x(r): assert r
            """,
        })
        self.assertEqual(kinds(f), ["no-floor"])

    def test_a_floor_on_the_local_alias_counts(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                LIVE = sorted(ROTATION_CODES)

                def test_floor(): assert len(LIVE) >= 3

                @pytest.mark.parametrize("r", LIVE)
                def test_x(r): assert r
            """,
        })
        self.assertEqual(kinds(f), ["unratcheted"])

    def test_an_ordinary_local_is_not_a_domain(self):
        """`for q in queries` over a numpy array is not an enumeration."""
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                from pkg.mod import ROTATION_CODES

                def test_x():
                    queries = make_queries()
                    for q in queries:
                        assert q
            """,
        })
        self.assertEqual(kinds(f), [])


class Acknowledgement(unittest.TestCase):

    SRC = 'ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}\n'

    def test_a_comment_ack_suppresses_the_finding(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                # totality: partial — mojo has no construction for "none"
                @pytest.mark.parametrize("r", ["haar", "rht"])
                def test_x(r): assert r
            """,
        })
        self.assertEqual(kinds(f), [])

    def test_a_docstring_ack_suppresses_the_finding(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": '''
                import pytest
                from pkg.mod import ROTATION_CODES

                @pytest.mark.parametrize("r", ["haar", "rht"])
                def test_x(r):
                    """Compare the two constructions.

                    totality: partial — "none" has no fidelity claim.
                    """
                    assert r
            ''',
        })
        self.assertEqual(kinds(f), [])

    def test_an_ack_that_no_longer_suppresses_anything_is_reported(self):
        """A suppression must not become a silence."""
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                import pytest
                from pkg.mod import ROTATION_CODES

                # totality: partial — stale, this covers everything now
                @pytest.mark.parametrize("r", sorted(ROTATION_CODES))
                def test_x(r): assert r
            """,
        })
        self.assertIn("stale-ack", kinds(f))


class Robustness(unittest.TestCase):

    def test_an_unparseable_file_is_skipped_not_fatal(self):
        f = scan_files(**{
            "pkg/broken.py": "def (((:\n",
            "pkg/mod.py": 'CODES = {"a": 0, "b": 1, "c": 2}\n',
            "pkg/tests/test_it.py": """
                from pkg.mod import CODES

                def test_x():
                    for k in ["a", "b"]:
                        assert k
            """,
        })
        self.assertEqual(kinds(f), ["sampled-domain"])

    def test_vendored_trees_are_not_scanned(self):
        f = scan_files(**{
            "node_modules/pkg/mod.py": 'CODES = {"a": 0, "b": 1, "c": 2}\n',
            "pkg/tests/test_it.py": """
                def test_x():
                    for k in ["a", "b"]:
                        assert k
            """,
        })
        self.assertEqual(kinds(f), [])

    def test_an_empty_tree_reports_nothing_and_does_not_raise(self):
        self.assertEqual(scan_files(**{"README.md": "nothing here\n"}), [])

    def test_the_report_renders_with_no_findings(self):
        out = tl.report([], {"source_files": 0, "registries": 0,
                             "test_files": 0, "domains": 0})
        self.assertIn("nothing to report", out)

    def test_selftest_passes(self):
        self.assertEqual(tl.selftest(), 0)


class SkipDirs(unittest.TestCase):

    def test_every_skipped_directory_is_actually_skipped(self):
        """invariant: every name in SKIP_DIRS is excluded from the walk.

        The domain is SKIP_DIRS itself. A name added to the set with nothing
        behind it reads as protection the walk does not provide, and the
        failure is silent: the linter scans a vendored tree and reports its
        registries as the project's own.

        The fixture keeps the registry and the test under one top-level
        directory on purpose. An earlier version put the registry at
        `<skipdir>/mod.py` and the test at `pkg/tests/`, which passes whether
        or not the skip works — `_reachable` rejects the pair either way. It
        was green under perturbation, which is the whole failure class this
        file exists to catch.

        refuted: replaced the walk's `part in SKIP_DIRS` check with
        `part in {"node_modules"}` -> this test went red naming `.coherence`,
        while the other 25 tests in this file stayed green.
        """
        self.assertGreaterEqual(len(tl.SKIP_DIRS), 8)
        for name in sorted(tl.SKIP_DIRS):
            files = {
                f"pkg/{name}/mod.py": 'CODES = {"a": 0, "b": 1, "c": 2}\n',
                "pkg/tests/test_it.py": """
                    def test_x():
                        for k in ["a", "b"]:
                            assert k
                """,
            }
            self.assertEqual(
                kinds(scan_files(**files)), [],
                f"a registry under {name}/ reached the report",
            )


class Ratchet(unittest.TestCase):
    """Enumeration and a hand-list are complementary, not a ladder.

    An enumeration loops whatever the domain currently holds, so it is
    structurally blind to the domain NARROWING. Measured on `oaustegard/remex`:
    substituting one member for another, keeping cardinality and keeping a
    second spelling of the domain in agreement, left the domain floor, the
    enumeration and the parity check all green while a supported rotation
    silently left. Raised by Yep, 2026-08-24; reproduced before being believed.
    """

    SRC = 'ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}\n'
    SHRUNK = 'ROTATION_CODES = {"haar": 0, "rht": 1, "xyz": 2}\n'

    def _tree(self, src, marker="# totality: ratchet — these three shipped"):
        return {
            "pkg/mod.py": src,
            "pkg/tests/test_it.py": f"""
                from pkg.mod import ROTATION_CODES

                {marker}
                def test_pinned():
                    for shipped in ("haar", "rht", "none"):
                        assert shipped in ROTATION_CODES
            """,
        }

    def test_an_intact_ratchet_is_silent(self):
        self.assertEqual(kinds(scan_files(**self._tree(self.SRC))), [])

    def test_a_member_leaving_breaks_the_ratchet_and_is_named(self):
        f = scan_files(**self._tree(self.SHRUNK))
        self.assertEqual(kinds(f), ["ratchet-broken"])
        self.assertEqual(f[0].missing, ["none"])
        self.assertEqual(f[0].registry, "ROTATION_CODES")

    def test_a_full_hand_list_is_not_a_sample_with_or_without_the_marker(self):
        """Pinning the WHOLE domain is not a sampling oracle in either case."""
        self.assertEqual(
            kinds(scan_files(**self._tree(self.SRC, marker="# ordinary"))), [])

    def test_a_partial_ratchet_still_reports_what_it_does_not_cover(self):
        """The marker must not be a laundering channel.

        A ratchet is a statement about the domain SHRINKING. It says nothing
        about members it never listed, so a partial ratchet leaves those exactly
        as uncovered as an unmarked hand-list does. Verified 2026-08-25: before
        this, `# totality: ratchet` over 2 of 3 members silenced the report
        entirely — the same escape hatch this tool's notes criticise `via guard`
        for being in `daniloc/coherence`, reproduced one day later.
        """
        tree = {
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                from pkg.mod import ROTATION_CODES

                def test_pinned():
                    for shipped in ("haar", "rht"):
                        assert shipped in ROTATION_CODES
            """,
        }
        self.assertEqual(kinds(scan_files(**tree)), ["sampled-domain"])
        tree["pkg/tests/test_it.py"] = tree["pkg/tests/test_it.py"].replace(
            "                def test_pinned",
            "                # totality: ratchet — the two that shipped first\n"
            "                def test_pinned")
        marked = scan_files(**tree)
        self.assertEqual(kinds(marked), ["sampled-domain"])
        self.assertEqual(marked[0].missing, ["none"])
        self.assertIn("covers only shrink", marked[0].detail)

    def test_a_partial_ack_does_not_earn_ratchet_checking(self):
        """`partial` excuses a hand-list; only `ratchet` asserts one."""
        f = scan_files(**self._tree(self.SHRUNK, marker="# totality: partial — two of three"))
        self.assertEqual(kinds(f), [])

    def test_an_enumeration_with_no_ratchet_is_reported(self):
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                from pkg.mod import ROTATION_CODES

                def test_floor(): assert len(ROTATION_CODES) >= 3

                def test_x():
                    for r in ROTATION_CODES:
                        assert r
            """,
        })
        self.assertEqual(kinds(f), ["unratcheted"])
        self.assertEqual(f[0].registry, "ROTATION_CODES")

    def test_no_floor_and_unratcheted_do_not_both_claim_one_line(self):
        """Two findings on one line saying overlapping things is fatigue.

        Measured 3 of 3 on `claude-workspace` and named by a cross-model review;
        `no-floor` is the narrower statement and wins.
        """
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                from pkg.mod import ROTATION_CODES

                def test_x():
                    for r in ROTATION_CODES:
                        assert r
            """,
        })
        self.assertEqual(kinds(f), ["no-floor"])

    def test_an_enumeration_WITH_a_ratchet_is_silent(self):
        """The pair is the answer; neither half alone is."""
        f = scan_files(**{
            "pkg/mod.py": self.SRC,
            "pkg/tests/test_it.py": """
                from pkg.mod import ROTATION_CODES

                def test_floor(): assert len(ROTATION_CODES) >= 3

                def test_x():
                    for r in ROTATION_CODES:
                        assert r

                # totality: ratchet — these three shipped
                def test_pinned():
                    for shipped in ("haar", "rht", "none"):
                        assert shipped in ROTATION_CODES
            """,
        })
        self.assertEqual(kinds(f), [])

if __name__ == "__main__":
    unittest.main(verbosity=2)
