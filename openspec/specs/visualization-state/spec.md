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
