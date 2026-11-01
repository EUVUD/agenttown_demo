## ADDED Requirements

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
