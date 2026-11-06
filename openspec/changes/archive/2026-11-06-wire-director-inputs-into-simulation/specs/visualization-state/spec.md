## ADDED Requirements

### Requirement: Snapshot time follows simulation progress

When no time is given, the system SHALL label a snapshot with the latest simulation time recorded in the run, and SHALL fall back to the world's starting time when nothing is recorded. Times that director events are merely scheduled for SHALL NOT advance the label.

#### Scenario: Successive safe points write distinct snapshots
- **WHEN** snapshots are generated at two safe points after the simulation advanced between them
- **THEN** each SHALL be written under its own time and the current snapshot SHALL carry the later time

#### Scenario: Scheduled events do not move the label
- **WHEN** a director event is scheduled for a future week
- **THEN** a snapshot generated without a time SHALL NOT use that future week

#### Scenario: Character entry labels the snapshot with the active world time
- **WHEN** a character is added while the active world is at the start of week 3
- **THEN** the snapshot written for the entry SHALL be labelled with that time

### Requirement: Snapshots are refreshed at the end of each week

For a template-created run, the system SHALL write or refresh the snapshot when each simulated week ends.

#### Scenario: Week end refreshes the snapshot
- **WHEN** a week of a template-created run completes
- **THEN** the current snapshot SHALL carry that week's time

### Requirement: Snapshots expose director application records

The snapshot SHALL include the director application records so a client can show how each director input was used.

#### Scenario: Applications appear in the snapshot
- **WHEN** director inputs were applied or skipped
- **THEN** the snapshot SHALL list those records

### Requirement: Character status comes from the state the simulation writes

The system SHALL read character status highlights from the state records the simulation itself writes, and SHALL keep accepting the earlier flat record shape.

#### Scenario: Highlights from engine-written state
- **WHEN** the latest state record of a character was written by the simulation
- **THEN** the character summary SHALL show its vitality and fulfillment

### Requirement: Relationship summaries publish summaries, not private notes

The system SHALL publish the summary of a relationship note, or a bounded excerpt when the note has no summary, and SHALL NOT publish the full text of a character's private note.

#### Scenario: Note with a summary
- **WHEN** a relationship note has a summary and a longer private body
- **THEN** the snapshot SHALL carry the summary only

#### Scenario: Note without a summary
- **WHEN** a relationship note has no summary and a very long body
- **THEN** the snapshot SHALL carry a bounded excerpt of it
