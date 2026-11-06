# Design

## Context

Director events are validated, stored in `director/events.jsonl`, and resolved into `director/results.jsonl` with a `produced_inputs` map. See proposal.md for why this is not enough. The legacy weekly loop runs the stages BEGIN, PLAN, BEFORE_CONTACT, CONTACT, AFTER_CONTACT, ACTIVITY, REVIEW, SETTLE. Its prompt text feeds an LLM response cache, so a legacy run's prompts must stay byte-identical. Resume cleanup trims every append-only JSONL file at or after the resume point and rejects rows without a `time` field.

Director runs are the runs that have a `template_meta.json`. Character entry and director events are written by another process than the one running the world, so the world can only learn about them from files.

## Goals / Non-Goals

**Goals:**
- Every resolved input kind has exactly one consumer in the weekly loop, at a fixed stage.
- Consumption never edits character state, profiles, scratchpads, or relationships.
- Legacy runs take none of the new code paths and produce identical prompts.
- Every consumption decision is explainable from a file.

**Non-Goals:**
- Starting a template-created run from `scripts/run_world.py`. That needs a documented adapter and is a separate change.
- Validating event targets and locations when an event is created. Fit is checked when the input is applied, where the roster and map are known.
- Changing relationship scores, vitality, or any other state because of an event.

## Decisions

**Template-declared kinds, legacy keys kept.** Resolution reads `resolves_to` from the template and writes one payload per kind; the old per-type keys are still written with their old shape. The alternative, a growing `if`/`elif` on type names, makes every new template an engine change, which the world-templates spec forbids. Keeping the old keys costs a few bytes and keeps existing readers working.

**Fixed hook points, one consumer per kind.**

| Kind | Stage | Consumer |
|---|---|---|
| arrival | BEGIN | roster refresh |
| prompt context | BEGIN | transient section in the roleplay prompt |
| public event | BEFORE_CONTACT | merged into the sign-up list |
| encounter candidate | AFTER_CONTACT | schedule, before generated encounters |
| snapshot | SETTLE | refresh |

Encounters run before generated ones so their participants count as engaged. Public events are rebuilt each week from active inputs rather than stored, so they follow the event's duration without touching the persisted public-event file.

**Context is transient prompt text.** It lives on the data manager in memory and is rendered as one section that is empty, and therefore dropped, when there is nothing to say. It is cleared at each week start. Persisting it into scratchpads would violate the rule that director events cannot mutate scratchpads. The wording tells the character the development is something heard or noticed, not a fact about their own state.

**Visibility.** `targeted`, `private`, and `personal` restrict an input to the event's targets; any other value is visible to the whole roster. One rule serves prompt context and public-event eligibility.

**Application log.** `director/applications.jsonl` is simulation output: append-only, time-ordered, trimmed by resume cleanup so a replayed week records its outcomes again. Events, results, and timeline entries are inputs, not output. They carry the time they are scheduled for, which can be ahead of the resume point, and nothing recreates them, so cleanup skips them. Without that exclusion, a run holding any director data fails to resume because those rows have no `time` field.

**Roster refresh by arrival event.** Because entry happens in another process, the world reads applied arrival events at week start and admits the named characters whose files exist. Scanning the persona directory instead would admit personas excluded by `max_agents`. Passing a live world handle is still supported for in-process callers; both paths use the same guard that only allows insertion at BEGIN.

**Entry records and resume.** A newcomer's initial state, memories, and hint scratchpads are stamped at the template's starting time, and only the arrival event carries the joining time. Resume cleanup trims every append-only file from the resume point, and nothing recreates a newcomer's seed rows, so stamping them at the joining week would delete them when a run is resumed from an earlier week. The profile is the exception: the engine reads `profile/year=<current year>.json`, so it is written for the joining year.

**Newcomer readiness.** Admission also registers the newcomer's profile position in the position store, because the year-end season asserts that every agent's position exists there, and reloads the location map, because the home was written by another process. When a template-created run is started again, characters added since the last start receive a model assignment; legacy runs keep failing on an incomplete assignment, as before.

**Relationship text.** Snapshots show the note summary, or a clipped excerpt for notes without one. Publishing the full body would expose private notes now that snapshots are refreshed every week.

**Snapshot time.** The label is the maximum of the checkpoint, each character's latest state row, and application records. Timeline entries are excluded for the reason above. Week end writes the label `Y<year>-W<week>-settle`.

**Engine-compatible files.** Template-created runs now write `world_setting` and `prices` in the worldview and state rows as `{time, content}`, which is what the engine reads. The snapshot reader accepts both shapes so earlier runs still render.

## Risks / Trade-offs

- A model may treat context as an instruction → the section says it is something heard or noticed and does not change what the character knows, feels, or owns.
- Template runs still cannot be started by the legacy runner → documented as a non-goal; the files are shaped so the adapter is a path change, not a data change.
- An unplaceable encounter is silently absent from the story → every skip is recorded with its reason and shown in the snapshot.
- Timing is now validated at creation, which rejects payloads that were accepted before → listed as breaking in the proposal. Events already stored with an unreadable timing are skipped with a warning when read, so one old row cannot stop a run.
- Arrival is week-granular, so an arrival timed mid-week joins at the next week start → consistent with the safe-boundary rule.
