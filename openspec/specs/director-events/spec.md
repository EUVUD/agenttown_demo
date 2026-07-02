## Purpose

Defines structured director events that represent player-authored interventions while preserving the rule that player input cannot directly mutate character internal state.

## Requirements

### Requirement: Director events represent player interventions
The system SHALL represent player-authored interventions as structured director events rather than direct state mutations.

#### Scenario: Create a valid director event
- **WHEN** a caller submits a director event whose type and fields match the active world template
- **THEN** the system SHALL persist the event with its type, timing, targets, visibility, intensity, location references, duration, and description

#### Scenario: Reject unsupported event type
- **WHEN** a caller submits a director event type not declared by the active world template
- **THEN** the system SHALL reject the event before world progression

### Requirement: Director events do not directly edit character internal state
The system SHALL NOT allow director events to directly set character vitality, fulfillment, skills, money, relationship scores, or scratchpad contents.

#### Scenario: Reject direct state edit payload
- **WHEN** a director event payload contains direct internal-state assignments
- **THEN** the system SHALL reject the payload and explain that state changes must emerge from simulation

#### Scenario: Resolve pressure event through simulation inputs
- **WHEN** a pressure event targets a character
- **THEN** the system SHALL add structured context for future simulation stages rather than directly lowering fulfillment or vitality

### Requirement: Director events are resolved into simulation inputs
The system SHALL resolve accepted director events into normal simulation inputs such as public events, encounter candidates, schedule context, prompt context, arrival events, or relationship context.

#### Scenario: Resolve campus rumor event
- **WHEN** a `school-classroom` rumor event is active for a week
- **THEN** the system SHALL make the rumor available to relevant characters according to its visibility rules during that week's planning, contact, or activity stages

#### Scenario: Resolve arranged encounter event
- **WHEN** a director event requests an encounter between valid characters at a valid location
- **THEN** the system SHALL attempt to create a schedule or encounter input subject to timing and conflict validation

### Requirement: Director event results are recorded
The system SHALL record the outcome of director event resolution for later review and visualization.

#### Scenario: Event affects world progression
- **WHEN** a director event is resolved during world advancement
- **THEN** the system SHALL record whether it was applied, skipped, partially applied, or failed validation

#### Scenario: Event result is explainable
- **WHEN** a caller retrieves a director event result
- **THEN** the result SHALL include a concise explanation and references to affected characters, locations, schedules, or timeline entries
