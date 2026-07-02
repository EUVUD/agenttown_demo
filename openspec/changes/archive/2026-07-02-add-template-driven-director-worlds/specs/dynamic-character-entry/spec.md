## ADDED Requirements

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
