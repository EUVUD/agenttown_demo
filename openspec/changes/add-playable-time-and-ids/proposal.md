## Why

The playable runtime needs stable domain primitives before commands, events, and
SQLite persistence can share one contract. D1.1 supplies the smallest time,
identity, and version value objects so later event streams can be ordered,
validated, and replayed without depending on the legacy weekly simulation clock.

## What Changes

- Add immutable playable-runtime value objects for world day, four daily time
  slots, combined world time, event identity, and aggregate version.
- Require validation for invalid day, slot, UUID version, and negative version
  boundaries.
- Require deterministic equality, ordering, string/int serialization, and
  duplicate ID comparability for future persistence and replay checks.
- Keep the implementation additive under the isolated `server` package without
  importing or mutating the legacy `src.world` runtime.

## Capabilities

### New Capabilities

- `playable-time-and-identity`: Defines the playable runtime's discrete world
  time, event ID, and version value-object contracts.

### Modified Capabilities

- None.

## Impact

- Adds focused Python domain code under `server/`.
- Adds focused pytest coverage under `tests/playable/`.
- Adds a new OpenSpec capability and updates the D1.1 roadmap checkbox only
  after implementation and verification pass.
- Adds no runtime dependency; Python 3.14 standard-library UUIDv7 is sufficient.
