"""Regression checks for the repository's GitHub Actions contract.

These checks intentionally use only the Python standard library.  GitHub
validates workflow syntax when the workflows run; this module guards the
project-specific gates, versions, and permission boundaries locally.
"""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIRECTORY = REPOSITORY_ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS_DIRECTORY / name).read_text(encoding="utf-8")


def test_verification_workflow_covers_all_project_quality_gates() -> None:
    workflow = _workflow("verify.yml")

    assert "workflow_call:" in workflow
    assert "contents: read" in workflow
    assert "python-tests:" in workflow
    assert "spec-validation:" in workflow
    assert "godot-tests:" in workflow
    assert "requirements.lock" in workflow
    assert "uv python install 3.14.6" in workflow
    assert "uv pip sync --python .venv/bin/python --require-hashes requirements.lock" in workflow
    assert "npm install --global @fission-ai/openspec@1.5.0" in workflow
    assert "openspec validate --all --strict --no-interactive" in workflow
    assert 'godot-version: "4.7.1"' in workflow
    assert "version: installed" in workflow


def test_continuous_integration_runs_for_develop_changes_and_pull_requests() -> None:
    workflow = _workflow("ci.yml")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "- develop" in workflow
    assert "workflow_dispatch:" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "uses: ./.github/workflows/verify.yml" in workflow


def test_release_workflow_only_delivers_verified_main_tags() -> None:
    workflow = _workflow("release.yml")

    assert "tags:" in workflow
    assert '- "v*"' in workflow
    assert "contents: write" in workflow
    assert "uses: ./.github/workflows/verify.yml" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "github.rest.repos.createRelease" in workflow


def test_external_actions_are_pinned_to_immutable_commits() -> None:
    external_action_references = re.findall(
        r"^\s*uses:\s+[^./][^@\s]+@([^\s#]+)",
        "\n".join(
            _workflow(name) for name in ("verify.yml", "ci.yml", "release.yml")
        ),
        flags=re.MULTILINE,
    )

    assert external_action_references
    assert all(re.fullmatch(r"[0-9a-f]{40}", reference) for reference in external_action_references)
