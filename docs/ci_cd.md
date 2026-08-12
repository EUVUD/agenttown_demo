# CI/CD Workflow

This repository uses GitHub Actions to keep changes testable and to create a
GitHub Release only after an explicit release tag is pushed.

## Continuous integration

The `Continuous integration` workflow runs for every pull request targeting
`develop`, every push to `develop`, and manual dispatches. It calls one shared
verification workflow containing three independent required gates:

1. **Python tests** — creates a CPython 3.14.6 environment with `uv`, installs
   the exact hash-checked packages from `requirements.lock`, then runs
   `python -m pytest -q`.
2. **OpenSpec validation** — installs OpenSpec 1.5.0 and runs
   `openspec validate --all --strict --no-interactive`.
3. **Godot tests** — runs the repository's vendored GdUnit4 addon with Godot
   4.7.1 on Ubuntu against `godot/tests`.

Newer CI runs cancel older in-progress runs for the same pull request or branch.
All jobs receive read-only repository permissions unless a later release step
explicitly needs more.

## Release delivery

Pushing a tag named `v*` starts `Create release`. It first runs exactly the
same three verification gates. If all pass, the workflow verifies that the
tagged commit descends from `main` and creates a GitHub Release with generated
release notes. A tag from any other branch fails before a release is created.

This is deliberately a **release record**, not an external deployment. The
project has no export preset, deployable service, or external distribution
target yet. No game binary is produced and no external deployment credential is
used. The release job receives GitHub's automatic token with only the
`contents: write` permission needed to create the Release. A future
platform-specific release change can add signed Godot artifacts or deployment
only after its target and secret-handling requirements are defined.

## GitHub repository settings

The workflow files define the checks, but GitHub repository rules decide whether
those checks block a merge. After the first successful CI run, a maintainer
should configure branch protection or a ruleset for both `develop` and `main`:

1. Require pull requests and the three checks produced by `Continuous
   integration` before merging.
2. Require the branch to be up to date before merging, and require linear
   history so feature pull requests continue to use rebase-and-merge.
3. Block direct pushes and force-pushes to both shared branches.

The workflow intentionally does not use `pull_request_target`, repository
secrets, or an external deployment environment.

## Maintainer release procedure

1. Merge approved feature pull requests into `develop` using rebase-and-merge.
2. Review and approve the explicit `develop` to `main` release pull request.
3. Create and push an annotated version tag from the resulting `main` commit,
   for example `v0.1.0`.
4. Confirm that the release workflow completed its three verification gates and
   created the GitHub Release.

Third-party actions are pinned to immutable commits. Review and intentionally
update those pins in a dedicated maintenance change when upstream releases are
needed.
