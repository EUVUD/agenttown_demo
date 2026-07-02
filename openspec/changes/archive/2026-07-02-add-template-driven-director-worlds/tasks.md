## 1. Template Pack Foundation

- [x] 1.1 Define the template pack JSON schema for world fields, character fields, role archetypes, location archetypes, event types, join modes, prompt fragments, and visualization hints
- [x] 1.2 Implement a template registry/loader that can load `data/world_templates/<template_id>/template.json` and associated markdown prompt fragments
- [x] 1.3 Add validation for unknown template ids, missing required template sections, and malformed creator fields
- [x] 1.4 Expose a backend function or CLI path that returns the creator schema for a selected template
- [x] 1.5 Add fixture tests for loading a valid template, rejecting an unknown template, and rejecting malformed template data

## 2. School Classroom Template

- [x] 2.1 Create the initial `school-classroom` template pack with school rhythm, classroom roles, locations, join modes, director event types, and visualization hints
- [x] 2.2 Add school-specific prompt fragments for roleplay context, director event resolution, and character generation
- [x] 2.3 Implement world creation from a template so a valid `school-classroom` creator payload produces a run directory with worldview, locations, profiles, and initial state inputs
- [x] 2.4 Add validation for missing required school classroom world fields and character fields
- [x] 2.5 Verify a small school classroom run can be instantiated without changing existing `data/school` and `data/apartment` run behavior

## 3. Director Events

- [x] 3.1 Define a persisted `DirectorEvent` record shape with id, type, timing, targets, visibility, intensity, location references, duration, description, status, and source template id
- [x] 3.2 Add director event validation against the active template's declared event types and parameter schema
- [x] 3.3 Reject payloads that attempt direct edits to vitality, fulfillment, skills, money, relationship scores, profile fields, or scratchpad contents
- [x] 3.4 Persist accepted director events before world advancement in an append-only run data file
- [x] 3.5 Implement initial director event resolvers for school rumors, pressure, opportunities, arranged encounters, campus incidents, and arrival events
- [x] 3.6 Record director event resolution results as applied, skipped, partially applied, or failed with concise explanations and source references
- [x] 3.7 Add tests covering valid event creation, unsupported event type rejection, direct state edit rejection, and explainable resolution results

## 4. Dynamic Character Entry

- [x] 4.1 Define a character entry request shape that references the active template, join mode, character draft, arrival context, and optional known-character hints
- [x] 4.2 Validate character entry requests against template-defined join modes and role-specific character fields
- [x] 4.3 Implement week-boundary insertion rules so new characters are accepted between weeks and rejected or deferred during unsafe stages
- [x] 4.4 Create profile, state initialization inputs, memory directories, scratchpad files, contact directory, schedule readiness, and generation directory readiness for accepted characters
- [x] 4.5 Assign or generate required home, starting location, and position data for new characters when the template requires them
- [x] 4.6 Seed initial social context from known-character hints without directly setting relationship scores
- [x] 4.7 Refresh `World.agents` and name lookup indexes before the next weekly planning stage
- [x] 4.8 Emit an arrival director event and timeline entry when a character joins
- [x] 4.9 Add tests for transfer student entry, unsupported join mode rejection, unsafe-stage insertion handling, and active roster refresh

## 5. Visualization State

- [x] 5.1 Define the visualization snapshot schema for current time, timeline events, character summaries, relationship summaries, location activity, and director event results
- [x] 5.2 Implement snapshot generation as a derived read model from authoritative run data rather than a new source of truth
- [x] 5.3 Generate or refresh snapshots after safe points such as week start, director event resolution, character entry, weekly review, and settlement
- [x] 5.4 Include structured timeline entries for director events, character arrivals, public events, and important weekly outcomes
- [x] 5.5 Include compact character summaries with role, introduction, last-known location when available, status highlights, and recent event references
- [x] 5.6 Derive relationship summaries from scratchpads, contact/activity records, rankings, and event references while tolerating sparse data
- [x] 5.7 Include location activity records for known locations even when a location has no recent activity
- [x] 5.8 Add tests that snapshots can be read by a future client without parsing raw prompts, scratchpads, or generation traces

## 6. Integration And Compatibility

- [x] 6.1 Add an opt-in runner or service interface for creating a template world, submitting director events, adding characters, advancing the world, and reading visualization state
- [x] 6.2 Keep existing research runner behavior working for current non-template data directories
- [x] 6.3 Add a minimal end-to-end test or scripted verification that creates a small school classroom world, injects a director event, adds a transfer student between weeks, advances the simulation, and reads a visualization snapshot
- [x] 6.4 Document the template pack format, director event constraints, character entry flow, and visualization snapshot contract for future Godot integration
