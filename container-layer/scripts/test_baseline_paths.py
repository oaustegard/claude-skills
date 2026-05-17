"""
Unit tests for the PYTHON_INSTALL_PATHS baseline fix (v0.2.1).

Locks in the behavior that dist-packages for python3.10/3.11/3.12/3.13 are
ALL recognized as baselined paths — so a SNAPSHOT directive that references
any of them gets the diff-vs-baseline treatment instead of full-tree capture.

Run:
    cd container-layer
    python3 -m scripts.test_baseline_paths
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from . import containerfile
from .containerfile import (
    PYTHON_INSTALL_PATHS,
    ContainerfileExecutor,
    snapshot_baseline,
)


class TestPythonInstallPathsCoverage(unittest.TestCase):
    """PYTHON_INSTALL_PATHS must include every dist-packages version we run on."""

    def test_python_3_10_through_3_13_dist_packages_present(self):
        for v in ("3.10", "3.11", "3.12", "3.13"):
            self.assertIn(
                f"/usr/local/lib/python{v}/dist-packages",
                PYTHON_INSTALL_PATHS,
                f"missing python{v}/dist-packages — diff-vs-baseline won't fire on "
                f"containers using this version",
            )

    def test_local_bin_still_listed(self):
        self.assertIn("/usr/local/bin", PYTHON_INSTALL_PATHS)


class TestBaselineCapturesNonExistentPaths(unittest.TestCase):
    """snapshot_baseline returns an entry for every requested path, even
    if the path doesn't exist — so _dedup_paths can later treat it as
    baselined regardless of build-time presence."""

    def test_missing_path_in_baseline_keys(self):
        baseline = snapshot_baseline(["/nonexistent/path/here"])
        self.assertIn("/nonexistent/path/here", baseline)
        self.assertEqual(baseline["/nonexistent/path/here"], set())


class TestDedupPathsDiffsBaselinedDirEvenWhenItGrows(unittest.TestCase):
    """Regression test for the bug: with python3.11 in PYTHON_INSTALL_PATHS,
    a SNAPSHOT directive on /usr/local/lib/python3.11/dist-packages should
    trigger the diff path (only NEW files captured), not the whole-tree path."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def _fake_baselined_dir_in_install_paths(self, simulate_path: str):
        """Patch PYTHON_INSTALL_PATHS to include a tempdir we control,
        so we can test the executor's baseline + diff path without
        touching real /usr/local."""
        self._patch_paths = simulate_path
        self._orig = containerfile.PYTHON_INSTALL_PATHS
        containerfile.PYTHON_INSTALL_PATHS = [simulate_path] + [
            p for p in self._orig if not p.endswith("dist-packages")
        ]
        self.addCleanup(setattr, containerfile, "PYTHON_INSTALL_PATHS", self._orig)

    def test_only_new_files_captured_in_baselined_dir(self):
        simulated = str(self.tmpdir / "fake-dist-packages")
        os.makedirs(simulated, exist_ok=True)
        # Pre-existing "baseline" file
        (Path(simulated) / "existing.py").write_text("# already there\n")

        self._fake_baselined_dir_in_install_paths(simulated)

        executor = ContainerfileExecutor()
        # Capture baseline as the real executor would, before any RUN
        executor._baseline = snapshot_baseline(containerfile.PYTHON_INSTALL_PATHS)
        # Simulate a SNAPSHOT directive having added this path
        executor.snapshot_paths.append(simulated)

        # Simulate a RUN command adding new files into the same dir
        (Path(simulated) / "added_by_run.py").write_text("# new\n")
        (Path(simulated) / "another.py").write_text("# also new\n")

        snapshotted = executor._dedup_paths()

        # The diff path should pick up ONLY the new files, not the existing one
        names = {os.path.basename(p) for p in snapshotted}
        self.assertIn("added_by_run.py", names)
        self.assertIn("another.py", names)
        self.assertNotIn("existing.py", names)
        # And it should be a list of individual files (diff), not the whole dir
        self.assertNotIn(simulated, snapshotted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
