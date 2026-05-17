"""
Unit tests for named-layer + compose support (v0.2.0).

Runnable standalone:

    cd container-layer
    python3 -m scripts.test_named_layers
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

from . import containerfile
from .containerfile import (
    ContainerLayer,
    BuildResult,
    compose,
    content_hash,
    default_layer_name,
)


class TestDefaultLayerName(unittest.TestCase):
    """Path -> layer name derivation."""

    def test_bare_containerfile_becomes_base(self):
        self.assertEqual(default_layer_name("Containerfile"), "base")
        self.assertEqual(default_layer_name("/abs/path/Containerfile"), "base")
        self.assertEqual(default_layer_name("./rel/Containerfile"), "base")

    def test_dot_suffix_becomes_name(self):
        self.assertEqual(default_layer_name("Containerfile.mojo"), "mojo")
        self.assertEqual(default_layer_name("Containerfile.torch-cpu"), "torch-cpu")
        self.assertEqual(default_layer_name("layers/Containerfile.scientific"), "scientific")

    def test_lowercase_and_sanitize(self):
        self.assertEqual(default_layer_name("Containerfile.JuliaSR"), "juliasr")
        self.assertEqual(default_layer_name("Containerfile.foo bar"), "foo-bar")
        # Note: os.path.basename strips directory components first, so
        # "Containerfile.weird/path" becomes "path" before suffix-stripping.

    def test_fallback_to_file_stem(self):
        self.assertEqual(default_layer_name("foo/bar.txt"), "bar")
        self.assertEqual(default_layer_name("/tmp/my_layer"), "my_layer")

    def test_empty_or_all_special_chars_falls_back(self):
        self.assertEqual(default_layer_name("Containerfile.@@@"), "layer")
        self.assertEqual(default_layer_name("Containerfile.---"), "layer")


class TestContainerLayerTag(unittest.TestCase):
    """tag property: with vs without layer_name."""

    def _layer(self, path: str, name: str = None) -> ContainerLayer:
        # ContainerLayer reads the file for hashing; create a temp file.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".Containerfile", delete=False) as f:
            f.write("RUN echo hello\n")
            cf_path = f.name
        self.addCleanup(os.unlink, cf_path)
        return ContainerLayer(
            containerfile_path=cf_path,
            cache_repo="testorg/test-cache",
            gh_token="test-token",
            layer_name=name,
        )

    def test_unnamed_layer_uses_back_compat_tag(self):
        layer = self._layer("Containerfile")
        self.assertRegex(layer.tag, r"^layer-[a-f0-9]{16}$")

    def test_named_layer_uses_named_tag(self):
        layer = self._layer("Containerfile", name="scientific")
        self.assertRegex(layer.tag, r"^layer-scientific-[a-f0-9]{16}$")

    def test_same_content_same_hash_regardless_of_name(self):
        layer_a = self._layer("Containerfile", name="alpha")
        layer_b = self._layer("Containerfile", name="beta")
        # Different names -> different tags, but same underlying content hash
        self.assertNotEqual(layer_a.tag, layer_b.tag)
        self.assertEqual(layer_a._hash, layer_b._hash)


class TestCompose(unittest.TestCase):
    """compose() orchestrates per-layer restore in order."""

    def setUp(self):
        # Three fake containerfiles in a clean tempdir so basename == filename
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup_tmpdir)
        self.cf_paths = []
        for name, body in [
            ("Containerfile", "RUN echo base\n"),
            ("Containerfile.scientific", "RUN echo sci\n"),
            ("Containerfile.mojo", "RUN echo mojo\n"),
        ]:
            path = os.path.join(self.tmpdir, name)
            with open(path, "w") as f:
                f.write(body)
            self.cf_paths.append(path)

    def _cleanup_tmpdir(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_compose_invokes_restore_or_build_on_each_layer_in_order(self):
        calls = []

        def fake_restore(self):
            calls.append((self.layer_name, self.containerfile_path))
            return BuildResult(success=True, snapshot_paths=[], content_hash="abc")

        with mock.patch.object(ContainerLayer, "restore_or_build", fake_restore):
            results = compose(
                containerfile_paths=self.cf_paths,
                cache_repo="testorg/cache",
                gh_token="t",
            )

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))
        # Order preserved + names derived from filename suffix:
        # Containerfile -> 'base', Containerfile.scientific -> 'scientific', etc.
        self.assertEqual([n for n, _ in calls], ["base", "scientific", "mojo"])

    def test_compose_halts_on_first_failure(self):
        attempt_log = []

        def flaky_restore(self):
            attempt_log.append(self.layer_name)
            success = self.layer_name != "scientific"
            return BuildResult(
                success=success,
                snapshot_paths=[],
                content_hash="abc",
                errors=[] if success else ["simulated failure"],
            )

        with mock.patch.object(ContainerLayer, "restore_or_build", flaky_restore):
            results = compose(
                containerfile_paths=self.cf_paths,
                cache_repo="testorg/cache",
                gh_token="t",
            )

        # Stopped at scientific (the 2nd layer), didn't try mojo
        self.assertEqual(attempt_log, ["base", "scientific"])
        self.assertEqual(len(results), 2)
        self.assertFalse(results[1].success)

    def test_compose_respects_explicit_name_overrides(self):
        seen_names = []

        def capture(self):
            seen_names.append(self.layer_name)
            return BuildResult(success=True, snapshot_paths=[], content_hash="abc")

        with mock.patch.object(ContainerLayer, "restore_or_build", capture):
            compose(
                containerfile_paths=self.cf_paths[:2],
                names=["custom-1", None],  # second falls back to default
                cache_repo="testorg/cache",
                gh_token="t",
            )

        # First is overridden, second derived from filename
        self.assertEqual(seen_names[0], "custom-1")
        self.assertEqual(seen_names[1], "scientific")

    def test_compose_rejects_mismatched_names_length(self):
        with self.assertRaises(ValueError):
            compose(
                containerfile_paths=self.cf_paths,  # 3 paths
                names=["only-one"],  # 1 name
                cache_repo="testorg/cache",
                gh_token="t",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
