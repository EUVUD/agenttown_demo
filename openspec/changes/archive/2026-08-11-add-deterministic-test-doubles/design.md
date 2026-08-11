## Research Findings / Recommendation

Repository inspection found no injectable playable-runtime test support: the legacy `src/world/clock.py` is tied to simulation configuration, and the legacy mock-response helper is not a reusable test double. The repository already uses pytest 9.1.1. Official pytest documentation confirms that `tmp_path` supplies an isolated per-test filesystem, and Python's standard `sqlite3` module provides the required local database behavior.

Recommendation: add small, test-only helpers under `tests/support/`, use a checked-in JSON fixture, and create a file-backed SQLite database under pytest's `tmp_path`. Do not add a dependency such as freezegun or time-machine: their process-global time patching is unnecessary before a runtime clock abstraction exists. GitHub authentication was unavailable during research, but repository inspection and public official documentation were sufficient for this bounded test-support change.

## Context

F0.3 established an inert Python and Godot skeleton. F0.4 needs repeatable inputs before the playable runtime gains its first domain behavior. Test support must remain isolated from the legacy Agentopia simulation, its JSONL runs, model configuration, and checked-in world-template packs.

## Goals / Non-Goals

**Goals:**

- Supply deterministic, directly injectable clock and LLM fakes for tests.
- Supply a small, version-controlled school fixture that is freshly decoded for each use.
- Supply a temporary, file-backed SQLite connection for tests without declaring a production schema.
- Demonstrate identical normalized outcomes and persisted rows for identical scripted inputs.

**Non-Goals:**

- Define a production clock, LLM interface, sidecar protocol, world-creation flow, or database schema.
- Migrate legacy JSONL simulation data or modify `scripts/run_world.py`.
- Turn the fixed school test fixture into the editable world-template format.
- Define relationship storage, relationship expiry, or event sourcing.
- Add test or runtime dependencies.

## Decisions

### Keep helpers in the test namespace

`tests/support/` will contain focused helpers rather than a production package. This prevents F0.4 utilities from becoming an accidental runtime contract before the runtime's ports are designed. `tests/playable/` and `tests/e2e/` can import the helpers normally.

Alternative considered: reuse the legacy clock and mock-response utilities. Rejected because they carry legacy configuration assumptions and do not provide an explicit scripted contract.

### Model time as an aware `datetime`

`FakeClock` starts at one timezone-aware `datetime`, exposes `now()`, and lets a test explicitly `set()` or `advance()` it. It rejects naive values, avoiding host timezone dependence and hidden global patches.

Alternative considered: patch `datetime.now()` with a third-party library. Rejected because the project does not yet have production code that reads the wall clock, and a global patch would hide dependencies rather than make them explicit.

### Use a scripted, recording LLM fake

`FakeLLM` maps an exact prompt string to a configured response, records every prompt, returns a deep copy of scripted response data, and fails clearly for an unconfigured prompt. It imports no provider SDK, reads no credentials, and makes no network call.

Alternative considered: a permissive canned response for every prompt. Rejected because unconfigured requests would silently conceal changes in the future runtime's prompt contract.

### Use a small independently decoded JSON school fixture

The fixture will contain exactly one protagonist, six NPCs, and five locations. Its loader reads the checked-in JSON and decodes it on every call, so mutation in one test cannot leak into another. It is explicitly test data, not the eventual versioned creator-facing world-template pack.

Alternative considered: reuse `data/school/`. Rejected because those legacy fixtures are part of existing simulation contracts and do not provide the small, stable testing boundary needed here.

### Use file-backed SQLite under `tmp_path`

The pytest fixture creates `world.sqlite3` under the current test's `tmp_path`, enables foreign keys, yields its path and connection, and closes the connection at teardown. File backing makes future tests able to exercise reconnect and multi-connection behavior while pytest cleanup prevents persistent state.

Alternative considered: `:memory:`. Rejected because it cannot represent the file lifecycle and connection boundaries relevant to the planned runtime persistence work.

## Risks / Trade-offs

- [Fixed fixture becomes too narrow for later gameplay tests] → Keep it intentionally small; add a separate fixture only when a new behavior needs it.
- [Fake response contract diverges from a future sidecar] → Keep the fake test-only and evolve it alongside the first explicit runtime port.
- [SQLite tests accidentally imply a production schema] → Do not create permanent tables or migration files in this change; test-local tables exist only to verify isolation and determinism.
- [A test reaches ambient state] → Contract tests exercise the helpers with no provider or legacy imports, and implementation stays within `tests/`.

## Migration Plan

No deployment or data migration is required. The helpers and fixture are additive test assets. Rollback consists of removing the new test-only files and OpenSpec change before any runtime code depends on them.

## Open Questions

None. Production ports, persistent schema, and relationship policy are deferred to later roadmap steps.
