## Purpose

Defines visualization-ready read models that let future clients inspect world state without parsing internal prompts, scratchpads, or generation traces.

## Requirements

### Requirement: System emits visualization-ready world snapshots
The system SHALL produce structured visualization snapshots that summarize world state for clients without requiring them to parse internal JSONL traces.

#### Scenario: Read current visualization snapshot
- **WHEN** a caller requests the current visualization state for a run
- **THEN** the system SHALL return current time, timeline events, character summaries, relationship summaries, location activity, and director event results

#### Scenario: Snapshot exists after advancement
- **WHEN** the world advances through a supported safe point
- **THEN** the system SHALL write or refresh a visualization snapshot for that time point

### Requirement: Timeline entries are structured
The system SHALL expose timeline entries as structured records with stable identifiers, time, type, title, summary, involved characters, involved locations, and source references.

#### Scenario: Director event creates timeline entry
- **WHEN** a director event is applied
- **THEN** the visualization state SHALL include a timeline entry linked to that director event

#### Scenario: Character entry creates timeline entry
- **WHEN** a new character joins the world
- **THEN** the visualization state SHALL include a timeline entry describing the arrival

### Requirement: Character summaries are client friendly
The system SHALL expose compact character summaries suitable for UI cards and map views.

#### Scenario: Character summary includes playable fields
- **WHEN** a visualization snapshot includes a character
- **THEN** the character record SHALL include name, role, current or last-known location when available, brief introduction, current status highlights, and recent event references

#### Scenario: Hide internal trace details
- **WHEN** a visualization snapshot is generated
- **THEN** it SHALL NOT require clients to display raw LLM prompts, hidden scratchpad internals, or full generation traces

### Requirement: Relationship summaries are derived read models
The system SHALL expose relationship summaries as derived read models rather than authoritative relationship state.

#### Scenario: Relationship summary from memories and interactions
- **WHEN** relationship visualization data is generated
- **THEN** the system SHALL derive it from available scratchpads, contact/activity records, rankings, or event references

#### Scenario: Relationship visualization tolerates sparse data
- **WHEN** two characters have little or no interaction history
- **THEN** the system SHALL omit the edge or mark it as unknown without failing snapshot generation

### Requirement: Location activity is exposed for future map clients
The system SHALL expose location activity records that future clients can render on maps or location lists.

#### Scenario: Location has active events
- **WHEN** a location has scheduled or recent events
- **THEN** the visualization state SHALL list those events and involved characters for that location

#### Scenario: Location has no activity
- **WHEN** a known location has no scheduled or recent events
- **THEN** the visualization state SHALL still be able to list the location with empty activity data

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
