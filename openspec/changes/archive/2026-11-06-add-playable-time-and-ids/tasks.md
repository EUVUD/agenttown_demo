## 1. Contract Tests

- [x] 1.1 Add focused playable tests for world day, slot, world time ordering, and slot rollover.
- [x] 1.2 Add focused playable tests for UUIDv7 event IDs, duplicate equality, and non-v7 rejection.
- [x] 1.3 Add focused playable tests for aggregate version boundaries and immutable advancement.

## 2. Domain Implementation

- [x] 2.1 Add isolated `server.domain` modules for time, identity, and version value objects.
- [x] 2.2 Export stable domain primitives from `server.domain` without importing legacy runtime modules.
- [x] 2.3 Keep implementation dependency-free beyond Python 3.14 standard library.

## 3. Verification and Roadmap

- [x] 3.1 Run the focused playable test module and strict OpenSpec validation.
- [x] 3.2 Update `GAME_DEVELOPMENT_PLAN.md` D1.1 only after the D1.1 acceptance tests pass.
- [x] 3.3 Run the relevant wider Python tests and record any skipped external checks.
