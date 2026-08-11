"""Contract tests for the F0.3 playable-runtime skeleton."""

from __future__ import annotations

import importlib
import re
import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GODOT_ROOT = PROJECT_ROOT / "godot"
LOCK_PATH = PROJECT_ROOT / "requirements.lock"
GODOT_PROVENANCE_PATH = GODOT_ROOT / "gdunit4.lock"

DIRECT_REQUIREMENTS = {
    "anthropic",
    "file-read-backwards",
    "google-auth",
    "google-genai",
    "jsonlines",
    "openai",
    "pytest",
    "python-dotenv",
    "requests",
    "tiktoken",
}


def test_python_skeleton_packages_import_without_legacy_runtime_side_effects() -> None:
    legacy_modules_before = {
        module_name
        for module_name in sys.modules
        if module_name == "src.world" or module_name.startswith("src.world.")
    }

    for package_name in ("server", "tests.playable", "tests.e2e"):
        assert importlib.import_module(package_name)

    legacy_modules_after = {
        module_name
        for module_name in sys.modules
        if module_name == "src.world" or module_name.startswith("src.world.")
    }
    assert legacy_modules_after == legacy_modules_before


def test_dependency_lock_is_exact_and_records_its_uv_inputs() -> None:
    lock_contents = LOCK_PATH.read_text(encoding="utf-8")

    assert "uv pip compile" in lock_contents
    assert "requirements.txt requirements-dev.txt" in lock_contents
    for requirement_name in DIRECT_REQUIREMENTS:
        assert re.search(
            rf"^{re.escape(requirement_name)}==[^\s]+",
            lock_contents,
            flags=re.MULTILINE,
        ), requirement_name


def test_godot_bootstrap_project_has_only_the_required_inert_contract() -> None:
    project_contents = (GODOT_ROOT / "project.godot").read_text(encoding="utf-8")
    scene_contents = (GODOT_ROOT / "scenes" / "bootstrap.tscn").read_text(
        encoding="utf-8"
    )
    script_contents = (GODOT_ROOT / "scripts" / "bootstrap.gd").read_text(
        encoding="utf-8"
    )

    assert 'run/main_scene="res://scenes/bootstrap.tscn"' in project_contents
    assert 'type="Node"' in scene_contents
    assert 'path="res://scripts/bootstrap.gd"' in scene_contents
    assert script_contents.strip() == "extends Node"


def test_gdunit4_provenance_matches_the_declared_toolchain_version() -> None:
    provenance = tomllib.loads(GODOT_PROVENANCE_PATH.read_text(encoding="utf-8"))

    assert provenance["gdunit4"]["version"] == "6.2.0"
    assert provenance["gdunit4"]["source_url"].startswith("https://github.com/")
    assert re.fullmatch(r"[a-f0-9]{64}", provenance["gdunit4"]["sha256"])
    assert list((GODOT_ROOT / "addons").glob("*/plugin.cfg"))


def test_gdunit4_bootstrap_test_is_present() -> None:
    test_contents = (GODOT_ROOT / "tests" / "test_bootstrap_scene.gd").read_text(
        encoding="utf-8"
    )

    assert "extends GdUnitTestSuite" in test_contents
    assert "res://scenes/bootstrap.tscn" in test_contents
