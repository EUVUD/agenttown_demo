# Tomorrow's Reply — Handoff

## Current State

`develop` now includes the F0 playable foundation, fixed CI/CD flow, and D1.1
time/identity domain slice. The latest confirmed merge is
[PR #3](https://github.com/EUVUD/agenttown_demo/pull/3), merged into `develop`
at commit `678bb75689c821981e93d740bb46da3a7e103973`.

The roadmap marks F0.1 through F0.5, the F0 phase gate, G0, and D1.1 as
complete in `GAME_DEVELOPMENT_PLAN.md`. G1 is not complete yet; D1.2
`WorldBlueprintV1` is the next roadmap item.

Important artifacts now present on `develop`:

- `GAME_DEVELOPMENT_PLAN.md`
- `docs/ci_cd.md`
- `docs/playable_toolchain.md`
- `openspec/changes/add-playable-time-and-ids/`
- `openspec/changes/archive/2026-08-11-establish-playable-toolchain-baseline/`
- `openspec/specs/playable-toolchain-baseline/spec.md`
- `server/domain/`
- `tests/playable/test_time_and_identity.py`

## Implemented D1.1 Behavior

D1.1 added dependency-free playable-domain value objects under `server.domain`:

- `server/domain/time.py`: `WorldDay`, `TimeSlot`, and `WorldTime`. Days start
  at 1, each day has exactly four neutral slots, `WorldTime` sorts by day then
  slot, and `WorldTime.next()` rolls day 1 slot 4 to day 2 slot 1.
- `server/domain/identity.py`: `EventId`, backed by Python 3.14 UUIDv7. It
  generates, parses, serializes, hashes, and compares event IDs, and rejects
  non-UUIDv7 values.
- `server/domain/version.py`: `Version`, a non-negative aggregate version value
  object. Version 0 represents an empty event stream, and `next()` returns a new
  incremented value without mutation.

These are pure domain primitives. They do not read SQLite, call model providers,
advance a real runtime, import `src.world`, or touch Godot. Later slices should
use them rather than raw integers or strings for time, event ID, and version
concepts.

## Decisions That Matter Next

- `time.py` is not the world clock service. It only defines the legal time
  shape and the pure next-time calculation. Runtime command handlers will later
  decide when to call `WorldTime.next()`, persist the result, and emit events.
- `EventId` and `Version` are both required. `EventId` answers "is this the same
  event?" while `Version` answers "where is this event in the aggregate stream?"
- UUIDv7 was chosen over ULID because CPython 3.14 already provides it in the
  standard library. No new runtime dependency was added.
- Time slots remain neutral as `SLOT_1` through `SLOT_4`; localized or
  fiction-facing labels can be added later without changing persistence.
- The playable runtime remains isolated from legacy JSONL simulation data until
  a documented adapter exists.

## Verification Already Performed

Before PR #3 was opened and merged:

- `.venv/bin/python -m pytest tests/playable/test_time_and_identity.py -q`
  passed with 9 tests.
- `.venv/bin/python -m pytest tests/playable -q` passed with 14 tests.
- `.venv/bin/python -m pytest -q` passed with 33 tests.
- `openspec validate add-playable-time-and-ids --strict` passed.
- `openspec validate --all --strict` passed with 8 items.
- `git diff --check origin/develop..HEAD` passed.

CI/CD was previously merged through [PR #2](https://github.com/EUVUD/agenttown_demo/pull/2)
at commit `292ff992da1d4f1641423d2d8ac85b3264f796e8`; its first remote run
passed. Check the latest GitHub Actions status on `develop` before relying on a
fresh merged commit.

## OpenSpec Status

`openspec list --json` currently reports `add-playable-time-and-ids` as a
complete active change with 9/9 tasks done. It has not been archived yet.

Next session should decide whether to archive D1.1 immediately with
`openspec-archive-change`, or keep it active until the project owner explicitly
asks for archival. Do not recreate the D1.1 artifacts.

## Required Follow-up

- Confirm branch protection or repository rulesets are configured for `develop`
  and `main` as described in `docs/ci_cd.md`.
- Archive the complete D1.1 OpenSpec change when the user approves.
- Start D1.2 `WorldBlueprintV1`: define the fixed world blueprint schema,
  legal/illegal JSON fixtures, and the boundary between creator-facing JSON and
  runtime domain objects.
- Keep updating `GAME_DEVELOPMENT_PLAN.md` whenever a roadmap step is fully
  implemented and its acceptance checks pass.

## Working Tree and Git

This handoff update was prepared from local `develop` after fast-forwarding to
`origin/develop` commit `678bb75689c821981e93d740bb46da3a7e103973`, then
creating `feature/update-d1-handoff`.

Older local stashes still exist and were intentionally left untouched:

- `stash@{0}` on `feature/f0-playable-foundation`: `codex/pre-ci-cd-2026-08-11`
- `stash@{1}` on `feature/f0-playable-foundation`:
  `codex/generated-godot-cache-before-feature-migration`
- `stash@{2}` on `codex/f0-toolchain-baseline`:
  `codex/pre-feature-migration-2026-08-11`

## Suggested Skills

- `git-feature-develop-workflow` and `caveman-commit` for any commit, push, PR,
  rebase, or post-merge cleanup.
- `openspec-archive-change` if the user approves archiving the completed D1.1
  change.
- `search-first`, `grill-me`, `solid`, `openspec-propose`, and
  `openspec-apply-change` for D1.2 implementation.
- `openspec-explore` for requirements discussion before locking D1.2 details.
