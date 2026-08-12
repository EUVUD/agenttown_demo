"""Load and validate the declared playable-runtime toolchain baseline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib


class ToolchainManifestError(ValueError):
    """Raised when the playable toolchain manifest is missing or unsupported."""


@dataclass(frozen=True)
class PlayableToolchainBaseline:
    """The exact versions and variants approved for playable-runtime work."""

    python_implementation: str
    python_version: str
    python_build: str
    pytest_version: str
    godot_version: str
    godot_edition: str
    godot_scripting_language: str
    export_templates_version: str
    gdunit4_version: str
    verification_host: str
    deferred_hosts: tuple[str, ...]


def load_toolchain_baseline(manifest_path: Path) -> PlayableToolchainBaseline:
    """Return the supported baseline after validating its exact contract."""
    document = _load_toml(manifest_path)
    return PlayableToolchainBaseline(
        python_implementation=_expected_value(
            document, "python", "implementation", "CPython"
        ),
        python_version=_expected_value(document, "python", "version", "3.14.6"),
        python_build=_expected_value(document, "python", "build", "standard-gil"),
        pytest_version=_expected_value(document, "pytest", "version", "9.1.1"),
        godot_version=_expected_value(document, "godot", "version", "4.7.1"),
        godot_edition=_expected_value(document, "godot", "edition", "standard"),
        godot_scripting_language=_expected_value(
            document, "godot", "scripting_language", "GDScript"
        ),
        export_templates_version=_expected_value(
            document, "godot", "export_templates_version", "4.7.1"
        ),
        gdunit4_version=_expected_value(document, "gdunit4", "version", "6.2.0"),
        verification_host=_expected_value(
            document, "verification", "host", "macos-arm64"
        ),
        deferred_hosts=_expected_strings(
            document, "verification", "deferred_hosts", ("windows-x86_64",)
        ),
    )


def _load_toml(manifest_path: Path) -> dict[str, Any]:
    try:
        with manifest_path.open("rb") as manifest_file:
            return tomllib.load(manifest_file)
    except FileNotFoundError as error:
        raise ToolchainManifestError(f"Toolchain manifest not found: {manifest_path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ToolchainManifestError(f"Invalid toolchain manifest: {error}") from error


def _expected_value(
    document: dict[str, Any], section_name: str, key: str, expected: str
) -> str:
    value = _required_value(document, section_name, key)
    if value == expected:
        return value
    raise ToolchainManifestError(
        f"{section_name}.{key} must be {expected!r}; found {value!r}"
    )


def _required_value(document: dict[str, Any], section_name: str, key: str) -> str:
    section = document.get(section_name)
    if not isinstance(section, dict):
        raise ToolchainManifestError(f"Missing required value: {section_name}.{key}")
    value = section.get(key)
    if isinstance(value, str) and value:
        return value
    raise ToolchainManifestError(f"Missing required value: {section_name}.{key}")


def _expected_strings(
    document: dict[str, Any], section_name: str, key: str, expected: tuple[str, ...]
) -> tuple[str, ...]:
    section = document.get(section_name)
    if not isinstance(section, dict):
        raise ToolchainManifestError(f"Missing required value: {section_name}.{key}")
    value = section.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ToolchainManifestError(f"Missing required value: {section_name}.{key}")
    actual = tuple(value)
    if actual == expected:
        return actual
    raise ToolchainManifestError(
        f"{section_name}.{key} must be {expected!r}; found {actual!r}"
    )
