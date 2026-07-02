## Why

Agentopia already has a strong long-term multi-agent simulation core, but it is currently shaped as a research runner: worlds are mostly data directories, agents are loaded once at startup, and outputs are optimized for traces rather than a playable director experience. To turn it into a creator-facing "director-style cultivation world" engine, the system needs template-driven setup, structured interventions, dynamic character entry, and visualization-ready state outputs.

## What Changes

- Introduce world template packs so scenarios such as "school classroom" are data-driven templates rather than hard-coded special cases.
- Add a first official `school-classroom` template that defines world rhythm, role archetypes, locations, director event types, character creation fields, and join modes.
- Add structured director events for player-authored interventions such as campus incidents, pressure, rumors, encounters, opportunities, and arrival events.
- Add dynamic character joining through template-defined join modes such as transfer student, new teacher, club guest, and returning student.
- Add visualization state snapshots that expose timeline events, character summaries, relationship changes, location activity, and director-event results for future clients such as Godot.
- Preserve the principle that the player does not directly edit character internal state; state changes must emerge from simulated reactions to events and character entry.

## Capabilities

### New Capabilities
- `world-templates`: Defines reusable world template packs that drive initial setup, scenario rules, character schemas, locations, director event catalogs, and prompt fragments.
- `director-events`: Defines structured player interventions that can be applied during world progression without directly mutating character state.
- `dynamic-character-entry`: Defines how new characters are introduced into an already-running world through template-defined arrival modes.
- `visualization-state`: Defines stable, structured state snapshots for timeline, character, relationship, location, and event-result visualization.

### Modified Capabilities
- None. There are no existing OpenSpec capabilities in this repository yet.

## Impact

- Affected simulation systems: world initialization, run progression, agent roster management, scheduling, locations, positions, memory initialization, and event handling.
- Affected data layout: new template files, new director event records, new character entry records, and visualization snapshot outputs under run data.
- Affected future APIs: backend operations for creating a world from a template, applying director events, adding characters, advancing the world, and reading visualization state.
- No frontend or Godot implementation is included in this change; the output contracts should be designed so a later Godot client can consume them.
