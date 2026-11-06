# Tasks

## 1. Resolution and validation

- [x] 1.1 Resolve events by template-declared input kinds with legacy keys kept, and verify with `tests/test_director_inputs.py::test_resolution_follows_the_template_and_keeps_legacy_keys`
- [x] 1.2 Reject malformed timing and verify with `tests/test_director_inputs.py::test_timing_must_be_a_world_time`
- [x] 1.3 Document the input kinds and visibility rule in `docs/director_world.md`
- [x] 1.4 Skip stored events with unreadable timing, and verify with `test_unreadable_stored_timing_is_skipped_not_fatal`

## 2. Consumption in the weekly loop

- [x] 2.1 Compute active inputs from timing and duration, applied results only, and verify with `test_active_inputs_follow_timing_duration_and_year_wrap` and `test_pending_events_are_not_inputs_until_resolved`
- [x] 2.2 Render prompt context with visibility and clear it each week, and verify with `test_prompt_context_respects_visibility_and_names_the_event` and the prompt assertions in `tests/test_world_director_integration.py`
- [x] 2.3 Offer public incidents for sign-up, and verify with `test_public_event_records_are_ready_for_sign_up` and `test_targeted_incident_is_offered_only_to_its_targets`
- [x] 2.4 Schedule or skip arranged encounters with a reason, and verify with `test_arranged_encounters_respect_roster_conflicts_and_locations`
- [x] 2.5 Record application outcomes and expose them in the snapshot, and verify with `test_applications_are_recorded_and_exposed_in_the_snapshot`
- [x] 2.6 Keep director inputs on resume and verify with the cleanup assertions in `tests/test_world_director_integration.py`

## 3. Character entry and roster

- [x] 3.1 Decide home and starting location by join mode, and verify with `test_join_mode_decides_home_and_starting_location`
- [x] 3.2 Time entry records at the active world's time and refuse insertion outside BEGIN, and verify with `test_service_refreshes_the_active_roster_only_at_a_safe_boundary`
- [x] 3.3 Refresh the roster from arrival events at week start, and verify with `test_pending_arrivals_start_at_their_week_and_skip_known_characters` and the roster assertions in `tests/test_world_director_integration.py`
- [x] 3.4 Stamp seed records at the template start and the profile at the joining year, and verify with `test_entry_records_use_the_template_start_and_the_profile_uses_the_joining_year` and the resume assertions in the weekly-flow scenario of `tests/test_world_director_integration.py`
- [x] 3.5 Assign models and register positions for newcomers and keep legacy runs strict, and verify with the weekly-flow and legacy-run scenarios in `tests/test_world_director_integration.py`
- [x] 3.6 Verify the weekly hooks through `World.step()` itself with the step-drives-hooks scenario, and the roster edge cases with the roster-edge-cases scenario

## 4. Snapshots and run files

- [x] 4.1 Infer the snapshot time and refresh it at week end, and verify with `test_snapshot_time_follows_the_simulation_not_the_schedule`
- [x] 4.3 Publish relationship summaries without private note bodies, and verify with `test_relationship_summaries_publish_the_summary_not_the_private_note`
- [x] 4.2 Write engine-compatible worldview keys and state rows and read both shapes in the snapshot, and verify with the state assertions in `test_service_refreshes_the_active_roster_only_at_a_safe_boundary` and `test_snapshot_time_follows_the_simulation_not_the_schedule`

## 5. Integration

- [x] 5.1 Run `python -m pytest -q` and verify the full suite passes
- [x] 5.2 Run `openspec validate --all --strict --no-interactive` and verify every item passes
