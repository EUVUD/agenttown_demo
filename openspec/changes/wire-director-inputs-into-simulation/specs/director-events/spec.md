## ADDED Requirements

### Requirement: Director event timing is a valid world time

The system SHALL reject a director event whose timing cannot be read as a world time, and SHALL NOT persist it.

#### Scenario: Reject malformed timing
- **WHEN** a caller submits a director event whose timing is not a world time such as `Y2020-W01-begin`
- **THEN** the system SHALL reject the event with a validation error and leave the persisted events unchanged

### Requirement: Stored events with unreadable timing do not stop the simulation

The system SHALL skip a stored director event whose timing cannot be read as a world time, with a warning, and SHALL continue to apply the other events.

#### Scenario: One bad stored event
- **WHEN** a stored event has an unreadable timing next to a valid event
- **THEN** the valid event SHALL still be applied and the unreadable one SHALL be skipped

### Requirement: Resolution follows the template's declared input kinds

The system SHALL resolve a director event into the simulation-input kinds its template declares for that event type, so a template can add event types without engine changes. An event type that declares none SHALL still reach characters as context.

#### Scenario: Resolve by declared kinds
- **WHEN** an event type declares prompt context and a timeline entry as its resolved inputs
- **THEN** the resolution result SHALL contain a prompt-context input and the event SHALL appear in the timeline

#### Scenario: Existing result fields stay readable
- **WHEN** an event is resolved
- **THEN** the result SHALL still carry the fields earlier results carried, in addition to the declared input kinds

### Requirement: Active director inputs reach the weekly simulation

For a template-created run, the system SHALL make resolved director inputs available to the weekly simulation from the week of the event's timing for the event's duration in weeks, defaulting to one week. Only applied results SHALL count, and a run without director data SHALL behave exactly as before.

#### Scenario: Event window follows timing and duration
- **WHEN** an applied event is timed at week 3 with a duration of two weeks
- **THEN** it SHALL be active in weeks 3 and 4 and in no other week

#### Scenario: Unresolved events are not inputs
- **WHEN** an event has been persisted but not yet resolved
- **THEN** it SHALL NOT be offered to the simulation until it is resolved

### Requirement: Context inputs respect visibility and never edit state

The system SHALL show a prompt-context input only to characters its visibility allows, and SHALL treat it as context that is not written to any character's stored state, profile, scratchpad, or relationships.

#### Scenario: Targeted context stays private
- **WHEN** a pressure event with targeted visibility names one character
- **THEN** only that character's prompts for the week SHALL include it

#### Scenario: Broad context reaches everyone
- **WHEN** a rumor with class visibility is active
- **THEN** every character in the active roster SHALL have it in their prompts for the week

#### Scenario: Context ends with the week
- **WHEN** a new week begins
- **THEN** the previous week's context SHALL be removed before the new week's context is applied

### Requirement: Public incidents can be signed up for

The system SHALL offer an active public-event input to characters as a public event for the week, on the weekday the event specifies and defaulting to the first, restricted to its targets only when its visibility is targeted.

#### Scenario: Class-visible incident is open
- **WHEN** a campus incident with class visibility names one character
- **THEN** it SHALL be offered to all characters

#### Scenario: Targeted incident is restricted
- **WHEN** a campus incident with targeted visibility names one character
- **THEN** it SHALL be offered only to that character

### Requirement: Arranged encounters are scheduled or skipped with a reason

The system SHALL turn an active encounter input into an encounter schedule only when at least two named characters are in the active roster, one of its locations is a valid public location, and a day of the week exists on which every participant is free. Otherwise it SHALL skip the encounter and record why. Encounters from earlier inputs SHALL be placed before generated encounters, and one character SHALL NOT be booked twice on a day.

#### Scenario: Encounter fits the week
- **WHEN** two roster characters are free on day 3 and the requested location is valid
- **THEN** an encounter schedule SHALL be created for both on day 3 at that location

#### Scenario: Encounter cannot be placed
- **WHEN** the characters are never free together, a named character is unknown, or no requested location is valid
- **THEN** no schedule SHALL be created and a skipped outcome with the reason SHALL be recorded

### Requirement: Application outcomes are recorded

The system SHALL record each outcome of applying a director input to the weekly simulation in an append-only log ordered by simulation time, with the time, event, input kind, status, explanation, and affected characters and locations.

#### Scenario: Outcome is explainable
- **WHEN** an input is applied or skipped in a week
- **THEN** the log SHALL gain an entry with its status and a concise explanation

### Requirement: Resume keeps director inputs

When a run is resumed from an earlier point, the system SHALL keep persisted director events, their results, and their timeline entries, and SHALL discard application outcomes from the resumed point onward so they are recorded again.

#### Scenario: Resume replays applications only
- **WHEN** a run is resumed from week 1
- **THEN** persisted events, results, and timeline entries SHALL be unchanged and week 1's application outcomes SHALL be removed
