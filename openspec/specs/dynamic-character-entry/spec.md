## Purpose

Defines how new characters enter a running template-driven world through validated join modes and safe progression boundaries.

## Requirements

### Requirement: Characters can join a running world through template modes
The system SHALL support adding new characters to a running world through join modes declared by the active world template.

#### Scenario: Add transfer student between weeks
- **WHEN** a valid `transfer_student` character entry is submitted to a `school-classroom` world between weeks
- **THEN** the system SHALL create the new character data and include the character in simulation from the next week

#### Scenario: Reject unsupported join mode
- **WHEN** a caller submits a character entry with a join mode not declared by the active template
- **THEN** the system SHALL reject the entry without modifying the run data

### Requirement: Character entry initializes required runtime data
The system SHALL create all required runtime files and indexes for a newly joined character before the character participates in simulation.

#### Scenario: Initialize new character storage
- **WHEN** a new character entry is accepted
- **THEN** the system SHALL create profile, state initialization inputs, memory directories, scratchpad files, contact directory, schedule file readiness, and generation directory readiness

#### Scenario: Initialize home or starting location
- **WHEN** a template requires a home or starting location for new characters
- **THEN** the system SHALL assign or generate that location before the character participates in activities

### Requirement: Character entry seeds social context
The system SHALL seed initial social context for newly joined characters using structured relationship hints rather than direct relationship score edits.

#### Scenario: Seed known classmates
- **WHEN** a transfer student entry includes known characters
- **THEN** the system SHALL create initial character scratchpad context that explains how those people are known

#### Scenario: No initial relationships
- **WHEN** a character entry contains no known characters
- **THEN** the system SHALL allow the character to join with an empty relationship context

### Requirement: Character entry updates active world roster safely
The system SHALL update the active world roster and lookup indexes only at safe progression boundaries.

#### Scenario: Roster refresh before weekly planning
- **WHEN** a character entry is accepted between weeks
- **THEN** the system SHALL add a `RoleAgent` instance and update name lookups before the next planning stage starts

#### Scenario: Prevent mid-activity insertion
- **WHEN** a caller attempts to add a character during an activity stage
- **THEN** the system SHALL defer or reject the insertion according to safe-boundary rules and explain the next eligible insertion point

### Requirement: Character arrival is visible as a world event
The system SHALL record a character's arrival as a timeline event and director event result.

#### Scenario: Transfer student arrival appears in timeline
- **WHEN** a transfer student joins a school classroom world
- **THEN** the visualization state SHALL include an arrival timeline entry referencing the new character and arrival context

### Requirement: Join mode decides home and starting location

The system SHALL decide whether a new character gets a private home from the chosen join mode, and SHALL use the join mode's starting location when the request names none.

#### Scenario: Mode without a home
- **WHEN** a character joins through a join mode that does not require a home
- **THEN** no private home SHALL be created for the character

#### Scenario: Mode with a starting location
- **WHEN** a character joins through a join mode that declares a starting location and the request names none
- **THEN** the arrival SHALL take place at that location

### Requirement: Entry time follows the active world

The system SHALL time a character's arrival at the active world's current time when one is available, and at the template's starting time otherwise. The character's profile SHALL be stored for the year of arrival. The character's initial state and memory records SHALL be stamped at the template's starting time, so that resuming a run from an earlier week does not discard them.

#### Scenario: Arrival during a running world
- **WHEN** a character joins while the active world is at the start of week 3
- **THEN** the arrival event SHALL be timed at the start of week 3

#### Scenario: Arrival in a later year
- **WHEN** a character joins while the active world is in its second year
- **THEN** the character's profile SHALL exist for that year and the engine SHALL read it without error

#### Scenario: Resume keeps a newcomer's records
- **WHEN** a run is resumed from a week earlier than the one in which a character joined
- **THEN** the character's initial state and memory records SHALL be unchanged

### Requirement: Running roster is refreshed from arrival events

At the start of each week of a template-created run, the system SHALL add to the active roster every character named by an applied arrival event whose week has started and whose files exist, before planning begins. It SHALL NOT add characters that no arrival event names, and refreshing twice SHALL NOT duplicate anyone.

#### Scenario: Newcomer plans the same week
- **WHEN** a character was added through the director service before a week begins
- **THEN** the character SHALL be in the roster before that week's planning stage

#### Scenario: Insertion mid-week is refused
- **WHEN** a character is added to a running world during any stage other than the week start
- **THEN** the world SHALL refuse the insertion and leave the roster unchanged

#### Scenario: Characters without an arrival are not added
- **WHEN** persona files exist that no arrival event names, such as personas left out by a roster cap
- **THEN** they SHALL NOT be added

### Requirement: Newcomers are ready for restart and year-end processing

The system SHALL give a character admitted to a running world a model assignment and a known position, and SHALL assign a model to characters added since the last start when a template-created run is started again. A run that is not template-created SHALL keep rejecting an incomplete model assignment.

#### Scenario: Restart after a character was added
- **WHEN** a character is added while the world is stopped and the world is started again
- **THEN** the character SHALL receive a model assignment and the start SHALL succeed

#### Scenario: Position known at year end
- **WHEN** a newcomer's role has no entry in the position store
- **THEN** the position SHALL be added with the newcomer as its holder, and a position already in the store SHALL list the newcomer without losing its other holders

#### Scenario: Incomplete assignment in a legacy run
- **WHEN** a run that is not template-created has characters without a model assignment
- **THEN** starting the world SHALL be rejected as before
