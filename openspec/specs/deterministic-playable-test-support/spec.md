## Purpose

Defines the isolated deterministic test support required before playable-runtime
behavior is implemented.

## Requirements

### Requirement: Deterministic clock and LLM test doubles

The repository SHALL provide test-only `FakeClock` and `FakeLLM` helpers that can be injected directly into playable-runtime tests. `FakeClock` MUST hold a timezone-aware `datetime`, return it through `now()`, and permit explicit `set()` and `advance()` operations. `FakeLLM` MUST return only explicitly scripted prompt responses, record received prompts in order, return independent response data, and raise a clear error for an unconfigured prompt. Neither helper MUST access the network, model credentials, legacy simulation modules, or ambient wall-clock state.

#### Scenario: A test advances a fixed clock

- **WHEN** a test creates `FakeClock` with a timezone-aware instant and advances it by a duration
- **THEN** `now()` returns exactly the resulting timezone-aware instant without consulting system time

#### Scenario: A test uses a scripted LLM response

- **WHEN** a test submits a configured prompt to `FakeLLM`
- **THEN** it receives an independent copy of the configured response and the prompt is recorded in call order

#### Scenario: A test submits an unexpected prompt

- **WHEN** a test submits a prompt absent from `FakeLLM`'s script
- **THEN** the fake records the attempt and raises a clear unexpected-prompt error without contacting a provider

### Requirement: Fixed school fixture is isolated from legacy data

The repository SHALL provide a checked-in JSON school fixture containing exactly one protagonist, six NPCs, and five locations. A test loader MUST return a newly decoded independent fixture value on every call. The fixture and loader MUST NOT read or mutate `data/school/`, `data/apartment/`, or `data/world_templates/`.

#### Scenario: A test mutates one loaded fixture

- **WHEN** a test changes a nested value in one loaded school fixture and loads the fixture again
- **THEN** the new value matches the checked-in JSON and is unaffected by the first mutation

### Requirement: Temporary SQLite fixture is file-backed and isolated

The repository SHALL provide a pytest fixture that creates a `world.sqlite3` database under the current test's `tmp_path`, enables SQLite foreign-key enforcement, yields the database path and open connection, and closes that connection after the test. The fixture MUST NOT create a permanent production schema or leave state outside pytest's temporary directory.

#### Scenario: A test verifies temporary database behavior

- **WHEN** a test writes and commits a row through the temporary database connection
- **THEN** another connection to the yielded file can read that row, foreign-key enforcement is enabled, and the database path is located below that test's `tmp_path`

### Requirement: Same scripted inputs produce the same persisted result

The test suite SHALL demonstrate that two independent executions using the same fixed clock, LLM script, and school fixture produce identical normalized output and identical ordered SQLite rows. The demonstration MUST use only test-local state and MUST NOT require network access, model credentials, legacy run data, or a production server process.

#### Scenario: A deterministic test probe runs twice

- **WHEN** the focused test executes its scripted probe in two separate temporary database directories
- **THEN** its normalized outcomes and ordered persisted rows are equal
