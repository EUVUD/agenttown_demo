# Tomorrow's Reply — Handoff

## Current State

The F0 engineering foundation is complete within its declared host scope.
F0.1 through F0.4 are represented by their archived OpenSpec changes and the
roadmap checkpoint; do not recreate those artifacts:

- `openspec/changes/archive/2026-08-11-establish-playable-toolchain-baseline/`
- `openspec/changes/archive/2026-08-11-establish-playable-runtime-skeleton/`
- `openspec/changes/archive/2026-08-11-add-deterministic-test-doubles/`
- `GAME_DEVELOPMENT_PLAN.md`

The fixed CI/CD flow is merged into `develop` as commit
`292ff992da1d4f1641423d2d8ac85b3264f796e8` through
[PR #2](https://github.com/EUVUD/agenttown_demo/pull/2). Its first GitHub
Actions run completed successfully:
[run 31559070167](https://github.com/EUVUD/agenttown_demo/actions/runs/31559070167).
The implementation and maintainer procedure are documented in
`docs/ci_cd.md` on `develop`.

## Decisions That Matter Next

- CI reuses three gates: hash-checked Python tests, strict OpenSpec validation,
  and vendored GdUnit4 tests on Godot 4.7.1.
- CI runs for pull requests targeting `develop`, pushes to `develop`, and
  manual dispatches. A `v*` tag reruns the same gates and creates a GitHub
  Release only after the tagged commit is verified to descend from `main`.
- The release is a GitHub Release record, not an artifact deployment. It uses
  no repository secrets or external deployment credentials; third-party action
  references are pinned to immutable commits.
- Windows x86_64 has not been validated. The completed F0 and G0 checkpoints
  mean stable verification for the declared macOS Apple Silicon and Ubuntu CI
  scope only; they do not claim Windows support.
- The playable runtime remains separate from the legacy JSONL simulation. The
  roadmap contains the authoritative product and architecture decisions.

## Verification Already Performed

- Local workflow linting, CI-workflow regression tests, the full Python suite,
  and strict OpenSpec validation passed.
- Local Godot headless startup and the vendored GdUnit4 test run passed.
- The first remote CI run passed its Python, OpenSpec, and Godot jobs.

Exact commands and release/branch-protection procedure are recorded in
`docs/ci_cd.md`; avoid duplicating or weakening those checks in another
workflow.

## Required Follow-up

Configure GitHub branch protection or equivalent rulesets for both `develop`
and `main`, as described in `docs/ci_cd.md`: require pull requests, require
the three CI checks, require an up-to-date branch and linear history, and block
direct and force pushes. This is a repository setting, not something the
workflow can enforce by itself.

## Working Tree and Git

The currently checked-out branch is `feature/f0-playable-foundation`, which is
behind `origin/develop`. Its dirty worktree is intentionally restored and
user-owned: `AGENTS.md`, the roadmap, toolchain documentation, OpenSpec
artifacts, `requirements-dev.txt`, `toolchain.toml`, `src/playable_toolchain.py`,
and focused baseline tests. Do not reset, clean, or switch it until that work
has been reviewed or safely stashed.

`stash@{0}` (`codex/pre-ci-cd-2026-08-11`) remains as an extra backup. The
local `develop` branch is also stale; update it only from a clean worktree.

## Recommended Next Session

1. Apply the documented GitHub protection settings, then confirm the checks
   appear as required on a new pull request.
2. Review and intentionally commit the restored F0 planning/toolchain work as
   its own milestone; keep it separate from the already merged CI/CD commit.
3. Start D1.1 as a new OpenSpec change after research and a confirmed planning
   review. Preserve the JSON fixture, FakeClock, FakeLLM, and temporary SQLite
   boundaries established in F0.

## Suggested Skills

- `git-feature-develop-workflow` and `caveman-commit` — safely integrate the
  restored F0 work and create an atomic milestone commit.
- `openspec-explore`, `search-first`, and `openspec-propose` — research and
  frame D1.1 before implementation.
- `grill-me` — required before executing the D1.1 plan and again before
  marking it complete.
- `openspec-apply-change` — implement an approved D1.1 change incrementally.
