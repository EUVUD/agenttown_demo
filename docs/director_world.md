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

Use `src.world.director_service.DirectorWorldService` to create events and resolve them into simulation inputs and timeline entries.

## Character Entry

Characters can join through template-defined join modes such as `transfer_student`, `new_teacher`, `club_guest`, and `returning_student`. The first safe insertion point is the week boundary (`Stage.BEGIN`). Entry initializes profile, state, memory, contact, generation, home/location data, social context hints, an arrival event, and visualization timeline data.

## Visualization Snapshot

`src.world.visualization.generate_visualization_snapshot(run_dir)` writes:

```text
<run_dir>/visualization/current.json
<run_dir>/visualization/snapshots/<time>.json
```

Snapshots contain current time, timeline events, compact character summaries, derived relationship summaries, location activity, and director event results. Clients such as Godot should read these snapshots instead of parsing raw prompts, scratchpads, or generation traces.
