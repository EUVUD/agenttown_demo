# Director World Backend

This change adds an opt-in backend layer for template-driven director worlds. It does not replace the existing research runner in `scripts/run_world.py`.

## Template Packs

World templates live under `data/world_templates/<template_id>/`.

```text
data/world_templates/school-classroom/
├── template.json
├── worldview.md
└── prompts/
    ├── roleplay.md
    ├── director_event.md
    └── character_generation.md
```

`template.json` defines required world fields, character fields, role archetypes, locations, director event types, join modes, default state, and visualization hints. The first template is `school-classroom`.

Inspect a creator schema:

```bash
python scripts/director_world.py schema school-classroom
```

## Director Events

Director events are structured interventions. They can introduce rumors, pressure, opportunities, arranged encounters, campus incidents, and arrivals. They must not directly set internal state such as vitality, fulfillment, skills, money, relationship scores, profiles, or scratchpads.

Use `src.world.director_service.DirectorWorldService` to create events and resolve them into simulation inputs and timeline entries. An event's `timing` must be a world time such as `Y2020-W01-begin`; anything else is rejected.

### Input kinds

Each event type lists the inputs it resolves to under `resolves_to` in `template.json`. The result's `produced_inputs` holds one payload per kind. Earlier per-type keys (for example `pressure_context`) are still written.

| Kind | Consumed by the weekly loop as |
|---|---|
| `prompt_context` | A "World Developments This Week" section in the roleplay prompt of each character who may see it |
| `public_event` | A public event characters can sign up for, on `metadata.day` (default 1), named by `metadata.event_name` |
| `encounter_candidate` | An encounter schedule placed before generated encounters |
| `arrival_event` | Admission of the named character to the active roster |
| `timeline_event` | An entry in `visualization/timeline.jsonl` |

An event is active from the week of its `timing` for `duration.weeks` weeks (default 1). `targeted`, `private`, and `personal` visibility restrict an input to the event's `targets`; any other visibility reaches everyone. Context is never written to a profile, scratchpad, state, or relationship, and it is cleared at each week start.

### Weekly consumption

Only runs created from a template (those with `template_meta.json`) take these steps. Legacy runs and their prompts are unchanged.

| Stage | Step |
|---|---|
| `BEGIN` | Admit new arrivals, resolve pending events, set prompt context |
| `BEFORE_CONTACT` | Offer incidents as public events |
| `AFTER_CONTACT` | Place arranged encounters, then generate the rest |
| `SETTLE` | Refresh the visualization snapshot |

An encounter needs two roster characters, one valid public location, and a day when all participants are free. Otherwise it is skipped. Every outcome is appended to `director/applications.jsonl` with its time, event, kind, status (`applied` or `skipped`), and reason. The file is trimmed on resume like other simulation output. `director/events.jsonl`, `director/results.jsonl`, and `visualization/timeline.jsonl` are inputs and are left untouched by resume.

## Character Entry

Characters can join through template-defined join modes such as `transfer_student`, `new_teacher`, `club_guest`, and `returning_student`. The first safe insertion point is the week boundary (`Stage.BEGIN`). Entry initializes profile, state, memory, contact, generation, home/location data, social context hints, an arrival event, and visualization timeline data.

The join mode decides whether the character gets a private home (`requires_home`) and where the arrival happens (`starting_location`, unless the request names one). The arrival event is timed at the active world's current time when `active_world` is passed, and at the template's start otherwise. The character's initial state and memories are stamped at the template's start so resuming a run from an earlier week never discards them, and the profile is written for the joining year (`profile/year=<year>.json`), because the engine reads the profile of the current year.

Character entry usually runs in a different process than the world. The running world therefore reads applied arrival events at the start of each week and adds the named characters to its roster before planning, so a newcomer plans and acts that week. Characters that no arrival event names are not added. An admitted character also gets a model assignment and a position in the position store; a template run that is started again assigns models to characters added since its last start. In-process callers may instead pass `active_world`; both paths refuse insertion outside `Stage.BEGIN`.

## Visualization Snapshot

`src.world.visualization.generate_visualization_snapshot(run_dir)` writes:

```text
<run_dir>/visualization/current.json
<run_dir>/visualization/snapshots/<time>.json
```

Snapshots contain current time, timeline events, compact character summaries, derived relationship summaries, location activity, director event results, and director application records (`director_applications`). Relationship summaries publish a note's summary (or a clipped excerpt when it has none), never the full private note. Clients such as Godot should read these snapshots instead of parsing raw prompts, scratchpads, or generation traces.

When no `time` is passed, the snapshot is labelled with the latest time recorded in the run: the legacy `checkpoint.json` (a finished week counts as its `settle` stage), each character's latest state row, and application records. Times that events are merely scheduled for do not count. A world of a template-created run refreshes the snapshot at the end of every week, so each week leaves its own file under `snapshots/`.

## Starting a Template Run

Template-created runs now write the files the legacy engine reads: `worldview.json` carries `world_setting` and `prices`, and `state.jsonl` rows use the `{time, content}` shape. `scripts/run_world.py` still cannot start such a run directly, because it requires a base world directory next to the run. That adapter is a separate change.
