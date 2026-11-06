## ADDED Requirements

### Requirement: Playable world time is discrete and ordered

The playable runtime SHALL represent time as a positive world day and one of
exactly four ordered slots within that day. The representation MUST be immutable,
comparable, serializable to primitive values, and independent of wall-clock time,
SQLite, Godot, model providers, and the legacy simulation runtime.

#### Scenario: World time advances across the final slot

- **WHEN** playable world time is day 1 slot 4 and the runtime asks for the next
  time
- **THEN** the result is day 2 slot 1

#### Scenario: Invalid time boundaries are rejected

- **WHEN** playable world time is created from day 0 or from a slot outside 1
  through 4
- **THEN** the runtime rejects the value with a clear validation error

#### Scenario: World time sorts by day before slot

- **WHEN** multiple playable world times are sorted
- **THEN** they are ordered by world day first and slot second

### Requirement: Playable event IDs are UUIDv7 value objects

The playable runtime SHALL represent event identity as an immutable UUIDv7 value
object. Event IDs MUST serialize to canonical UUID strings, parse from canonical
UUID strings, reject non-UUIDv7 values, and compare/hash by identity value so
duplicates can be detected before persistence adds unique constraints.

#### Scenario: Duplicate event IDs compare equal

- **WHEN** two event IDs are parsed from the same canonical UUIDv7 string
- **THEN** they compare equal and collapse to one member in a set

#### Scenario: Non-UUIDv7 IDs are rejected

- **WHEN** an event ID is parsed from a UUID that is not version 7
- **THEN** the runtime rejects the value with a clear validation error

### Requirement: Playable versions are non-negative value objects

The playable runtime SHALL represent aggregate versions as immutable
non-negative integer value objects. Version 0 MUST represent an empty aggregate,
and advancing a version MUST produce the next integer version without mutating
the original value.

#### Scenario: Empty aggregate version advances to first version

- **WHEN** version 0 is advanced
- **THEN** the result is version 1 and the original version remains 0

#### Scenario: Negative versions are rejected

- **WHEN** a playable version is created from a negative integer
- **THEN** the runtime rejects the value with a clear validation error
