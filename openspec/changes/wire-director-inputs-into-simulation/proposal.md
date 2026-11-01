# Proposal

## Why

Director events are accepted, resolved, and recorded, but the weekly simulation never consumes the inputs they produce, so a rumor, pressure, incident, or arranged encounter has no effect on what characters see or do. Characters added through the director service never reach a running world's roster, and every visualization snapshot is written under one fixed time label, so each snapshot overwrites the last. These three gaps were recorded as known issues in the handoff and block any client from relying on the director and snapshot contracts.

## What Changes

- Resolve each director event into the simulation-input kinds its template declares, instead of a fixed per-type table, while keeping the existing result fields readable.
- Reject director events whose timing is not a valid world time.
- Consume resolved inputs in the weekly loop of template-created runs:
  - rumors and pressure become prompt context for the characters the event's visibility allows;
  - campus incidents become public events characters can sign up for;
  - arranged encounters become encounter schedules when the characters, location, and a free day exist, and are otherwise skipped with a recorded reason.
- Record every application outcome in an append-only, time-ordered director application log and expose it in the snapshot.
- Admit characters who joined through the director service into the running roster at the next week boundary, using their arrival event.
- Make character entry follow the join mode (home and starting location) and the active world time instead of fixed values.
- Default the snapshot time to the latest time recorded in the run, so successive safe points write distinct snapshots, and refresh the snapshot at the end of every week of a template-created run.
- Write template-created runs in the file shapes the legacy engine reads (worldview keys, state rows) and keep director inputs intact when a run is resumed.
- **BREAKING**: a director event whose timing is not a valid world time (for example `whenever`) is now rejected at creation instead of being stored.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `director-events`: resolved inputs are template-declared and are consumed by the weekly simulation with visibility rules; application outcomes are recorded; timing is validated; inputs survive resume.
- `visualization-state`: the snapshot time follows simulation progress, snapshots are refreshed at week end, and application records and engine-written character state are exposed.
- `dynamic-character-entry`: join mode decides the home and starting location, arrival time follows the active world, and the running roster is refreshed from arrival events at the next week boundary.

## Impact

- Code: `src/world/director.py`, `director_service.py`, `template_world.py`, `visualization.py`, `world.py`, `cleanup.py`, `locations.py`, `clock.py`, and `src/agents/data_manager.py` and `role_agent.py` (a transient prompt section that is empty for legacy runs).
- Legacy runs (no `template_meta.json`) take none of the new paths, and their prompts are unchanged.
- Run files: adds `director/applications.jsonl`; the snapshot gains `director_applications`. Existing fields are unchanged, so clients keep working.
- Not changed: `scripts/run_world.py` still cannot start a template-created run directly; that adapter is out of scope here.
