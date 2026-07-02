## Purpose

Defines reusable world template packs that describe scenario setup, creator fields, role archetypes, locations, director event catalogs, join modes, prompt fragments, and visualization hints without hard-coding scenario-specific branches into the simulation core.

## Requirements

### Requirement: Template packs define reusable world setup
The system SHALL load reusable world template packs that define scenario setup data separately from simulation engine code.

#### Scenario: Load a valid template pack
- **WHEN** a caller requests a known template id
- **THEN** the system SHALL load its structured template data and associated text prompt fragments

#### Scenario: Reject an unknown template pack
- **WHEN** a caller requests a template id that does not exist
- **THEN** the system SHALL return a clear validation error without creating a run

### Requirement: Template packs define required creator fields
The system SHALL expose the fields required to create a world and characters for a template.

#### Scenario: Query school classroom creator fields
- **WHEN** a caller asks for the `school-classroom` template schema
- **THEN** the system SHALL include world fields, character fields, role archetypes, join modes, and director event types

#### Scenario: Validate missing required character fields
- **WHEN** a character draft omits a field required by its selected template role
- **THEN** the system SHALL reject the draft and report the missing fields

### Requirement: School classroom template is the first official template
The system SHALL provide a `school-classroom` template suitable for a director-style school class simulation.

#### Scenario: Inspect school classroom template
- **WHEN** the `school-classroom` template is loaded
- **THEN** it SHALL define school rhythm, student and teacher role archetypes, classroom-oriented locations, campus event types, and character join modes

#### Scenario: Instantiate school classroom world
- **WHEN** a caller creates a world from the `school-classroom` template with valid initial characters
- **THEN** the system SHALL create a run directory with template-derived worldview, locations, character profiles, and initial state inputs

### Requirement: Templates remain extensible
The system SHALL allow future templates to add scenario-specific roles, locations, event types, join modes, prompt fragments, and visualization hints without changing existing template definitions.

#### Scenario: Load a template with additional event types
- **WHEN** a future template declares event types not present in `school-classroom`
- **THEN** the system SHALL expose those event types through the same template interface

#### Scenario: Preserve core engine independence
- **WHEN** a template defines scenario-specific vocabulary or roles
- **THEN** the simulation core SHALL consume them through generic template fields rather than hard-coded scenario branches
