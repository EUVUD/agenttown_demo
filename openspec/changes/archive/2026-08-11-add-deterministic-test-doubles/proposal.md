## Why

The playable-runtime skeleton cannot yet test future behavior repeatably: wall-clock time, model responses, fixture data, and database state would otherwise come from ambient services or machines. F0.4 supplies the smallest isolated test support before domain and runtime work begins.

## What Changes

- Add test-only deterministic `FakeClock` and scripted `FakeLLM` helpers shared by playable and end-to-end tests.
- Add an immutable checked-in small school fixture with a loader that returns an independent copy for every test.
- Add pytest support for an isolated, temporary file-backed SQLite database under `tmp_path`.
- Add contract tests proving that the same scripted input produces the same normalized output and database rows without legacy, network, or model-service access.
- Keep the dependency set unchanged by using pytest 9.1.1 and the Python standard library.

## Capabilities

### New Capabilities

- `deterministic-playable-test-support`: Defines deterministic test doubles, fixed school fixture data, and temporary SQLite support for playable-runtime tests.

### Modified Capabilities

- None.

## Impact

- Adds test-only helpers, fixtures, and focused contract tests under `tests/`.
- Does not change the legacy simulation, its JSONL data contracts, production server behavior, or checked-in world-template packs.
- Uses existing pytest and Python `sqlite3`; no network access, model credentials, or new dependencies are introduced.
