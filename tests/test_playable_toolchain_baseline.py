from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.playable_toolchain import ToolchainManifestError, load_toolchain_baseline


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PlayableToolchainBaselineTests(unittest.TestCase):
    def test_loads_the_declared_exact_baseline(self) -> None:
        baseline = load_toolchain_baseline(PROJECT_ROOT / "toolchain.toml")

        self.assertEqual(baseline.python_implementation, "CPython")
        self.assertEqual(baseline.python_version, "3.14.6")
        self.assertEqual(baseline.python_build, "standard-gil")
        self.assertEqual(baseline.pytest_version, "9.1.1")
        self.assertEqual(baseline.godot_version, "4.7.1")
        self.assertEqual(baseline.godot_edition, "standard")
        self.assertEqual(baseline.godot_scripting_language, "GDScript")
        self.assertEqual(baseline.export_templates_version, "4.7.1")
        self.assertEqual(baseline.gdunit4_version, "6.2.0")
        self.assertEqual(baseline.verification_host, "macos-arm64")
        self.assertEqual(baseline.deferred_hosts, ("windows-x86_64",))

    def test_rejects_a_manifest_missing_a_required_version(self) -> None:
        manifest = self._write_manifest(
            self._valid_manifest_contents().replace(
                "[pytest]\nversion = \"9.1.1\"\n\n", ""
            )
        )

        with self.assertRaisesRegex(ToolchainManifestError, "pytest.version"):
            load_toolchain_baseline(manifest)

    def test_rejects_the_unsupported_free_threaded_python_variant(self) -> None:
        manifest = self._write_manifest(
            self._valid_manifest_contents().replace(
                'build = "standard-gil"', 'build = "free-threaded"'
            )
        )

        with self.assertRaisesRegex(ToolchainManifestError, "standard-gil"):
            load_toolchain_baseline(manifest)

    def test_rejects_the_dotnet_godot_edition(self) -> None:
        manifest = self._write_manifest(
            self._valid_manifest_contents().replace(
                'edition = "standard"', 'edition = "dotnet"'
            )
        )

        with self.assertRaisesRegex(ToolchainManifestError, "standard"):
            load_toolchain_baseline(manifest)

    def _write_manifest(self, contents: str) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        manifest = Path(temporary_directory.name) / "toolchain.toml"
        manifest.write_text(contents, encoding="utf-8")
        return manifest

    def _valid_manifest_contents(self) -> str:
        return """
[python]
implementation = "CPython"
version = "3.14.6"
build = "standard-gil"

[pytest]
version = "9.1.1"

[godot]
version = "4.7.1"
edition = "standard"
scripting_language = "GDScript"
export_templates_version = "4.7.1"

[gdunit4]
version = "6.2.0"

[verification]
host = "macos-arm64"
deferred_hosts = ["windows-x86_64"]
"""


if __name__ == "__main__":
    unittest.main()
