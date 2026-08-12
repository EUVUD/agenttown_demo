## Context

D1.1 is the first playable-domain slice after the F0 skeleton. The repository
already has a legacy weekly `src.world.clock` model, but project instructions
require new playable-runtime state to remain isolated under `server/` until a
documented adapter exists. Existing test support provides `FakeClock`, `FakeLLM`,
fixture loading, and temporary SQLite helpers; D1.1 should add only pure domain
value objects and focused tests.

Search-first findings:

- Repository search found no existing playable-domain primitives under
  `server/`; the legacy clock is week/stage based and tied to legacy config.
- Python 3.14 standard `uuid.uuid7()` provides time-based UUIDs with a
  millisecond timestamp and monotonic same-millisecond counter, so no ID
  dependency is needed.
- `dataclasses.dataclass(frozen=True, slots=True, order=True)` is sufficient for
  small immutable value objects.
- ULID packages are available and maintained, but they add dependency surface
  for a compact string format that D1.1 does not require.
- Pydantic supports UUIDv7 validation and can be useful later at API/schema
  boundaries; using it inside the core domain layer would add model semantics
  before the runtime has commands or API adapters.

## Goals / Non-Goals

**Goals:**

- Define immutable playable-runtime value objects for world days, four slots per
  day, combined world time, event IDs, and aggregate versions.
- Provide explicit parse/serialize helpers for future SQLite and API contracts.
- Validate invalid boundaries and duplicate ID equality through automated tests.
- Keep the domain layer free of network access, model providers, SQLite, Godot,
  and legacy runtime imports.

**Non-Goals:**

- No wall-clock to game-clock mapping; O8 owns real-time catch-up behavior.
- No database schema or repository behavior; S2 owns SQLite persistence.
- No command or event envelope schema; D1.4 owns command/event contracts.
- No migration from legacy `TimeState`.

## Decisions

### Put primitives in `server.domain`

Create `server/domain/` with small modules that import only Python standard
library types. This keeps the future sidecar's domain model separate from the
legacy simulation while leaving import paths stable for later commands and
repositories.

Alternative considered: extend `src.world.clock`. Rejected because it is tied to
the legacy weekly simulation and global config loading.

### Model playable time as `WorldDay`, `TimeSlot`, and `WorldTime`

`WorldDay` starts at 1 because day 1 is the user-facing first playable day.
`TimeSlot` exposes exactly `SLOT_1` through `SLOT_4` as neutral ordered enum
values. `WorldTime` combines them, orders by day then slot, and advances to the
next slot or next day.

Alternative considered: named morning/afternoon/evening/night slots. Rejected
for D1.1 because fiction-facing labels can be localized or themed later without
changing the storage contract.

### Use UUIDv7 for `EventId`

`EventId` wraps `uuid.UUID`, accepts only version 7 values, serializes to the
canonical UUID string, and compares by UUID value. New IDs use `uuid.uuid7()`.
Tests can construct known UUIDv7 strings directly to verify duplicate equality.

Alternative considered: ULID. Rejected because UUIDv7 is standard-library,
time-sortable enough for event identity, and avoids a new runtime dependency.

### Use `Version` as an aggregate version value object

`Version` wraps a non-negative integer and exposes `next()`. Version 0 represents
an empty aggregate before events are appended; later S2 optimistic writes can use
the same object for expected-version checks.

Alternative considered: start at 1. Rejected because event streams commonly need
to represent "no events yet" distinctly from the first committed event.

## Risks / Trade-offs

- [UUIDv7 availability depends on Python 3.14] -> F0.1 already locks CPython
  3.14.6, and tests will fail clearly if run on an unsupported interpreter.
- [Neutral slot names are less expressive in UI] -> Keep locale/facing labels
  outside the storage contract until Godot UI slices need them.
- [Value objects do not prevent duplicate persistence by themselves] -> D1.1
  verifies equality/hash comparability; S2 will add SQLite uniqueness and
  idempotent command enforcement.

## Migration Plan

The change is additive. Rollback consists of removing the new OpenSpec change,
the new `server.domain` modules, and the focused playable tests before later
runtime code depends on them.

## Open Questions

- None for D1.1. Future slices will decide event envelope shape, database
  indexes, and API schema representation.
