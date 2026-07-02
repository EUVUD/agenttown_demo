## Context

Agentopia currently runs long-term simulations from copied world data directories under `data/`. `World` initializes all `RoleAgent` instances from `data/<run>/persona` once at startup, then keeps `self.agents` and `_name2agent` fixed for the run. Most outputs are append-only JSONL traces optimized for research analysis and RFT extraction, not for a player-facing director loop.

The target product direction is a director-style cultivation world: the player cannot directly edit character state, but can create a world from a reusable template, add characters while the world is running, and inject structured events that the simulation resolves into schedules, memories, relationships, and state changes. The first official template is a school classroom, but the architecture must support future templates such as apartment neighbors, idol agency, fantasy academy, or custom player worlds.

## Goals / Non-Goals

**Goals:**
- Add a template-driven setup layer that keeps scenario-specific fields, roles, locations, join modes, and event catalogs outside the core simulation engine.
- Define a `school-classroom` template as the first reusable template pack.
- Add structured director events that express player intent without directly mutating character internal state.
- Add dynamic character entry so new characters can join a running world through template-defined arrival flows.
- Add visualization state snapshots that expose stable, client-friendly summaries for a later UI or Godot client.
- Preserve existing research simulation behavior unless explicitly running through the new director/template flow.

**Non-Goals:**
- No Godot client, web frontend, or visual UI implementation in this change.
- No open-ended natural-language world mutation that bypasses structured event validation.
- No direct player edits to vitality, fulfillment, skills, money, relationship scores, or scratchpad contents.
- No attempt to optimize every LLM call in the existing full simulation loop; this change introduces the data contracts and integration seams needed for later cost reductions.
- No template marketplace, cloud sharing, authentication, or multiplayer functionality.

## Decisions

### Decision 1: Use runtime-readable template packs

Template packs will live as data artifacts, not Python subclasses. The initial layout should be compatible with:

```text
data/world_templates/<template_id>/
├── template.json
├── worldview.md
├── prompts/
│   ├── roleplay.md
│   ├── director_event.md
│   └── character_generation.md
└── examples/
```

`template.json` defines stable structured data: time rhythm, role archetypes, location archetypes, character fields, director event types, join modes, default simulation budgets, and visualization hints. Markdown files hold longer human-readable background and prompt fragments.

Alternative considered: YAML templates. YAML is friendlier to hand edit, but the project does not currently depend on a YAML parser. JSON keeps the first implementation dependency-free and easy to consume from Python and external clients. A later import/export layer can support YAML if needed.

### Decision 2: Keep templates declarative and make the core resolve them

The simulation core should load templates through a template registry/loader and convert template definitions into existing runtime data: worldview, locations, profile field requirements, positions, director event schemas, and prompt context. Template packs should not call LLMs or mutate run state directly.

Alternative considered: per-template Python classes. That would move faster for the first school template, but it would make player-created templates and future scene packs harder to support.

### Decision 3: Model player actions as director events

Player interventions become `DirectorEvent` records with a validated type, parameters, timing, target characters, visible characters, affected locations, intensity, duration, and a free-text description. The free-text field is flavor and context; the structured fields are the contract the simulation can validate and visualize.

Director events are persisted before resolution. Resolution may create public events, encounter schedules, relationship prompts, pressure context, arrival events, or other simulation inputs. Any state changes must be produced by normal simulation reactions or God Model evaluation, not by the director event itself directly setting internal values.

Alternative considered: allow arbitrary natural-language commands. This maximizes freedom but makes cost, validation, visualization, and repeatability much worse.

### Decision 4: Treat dynamic character entry as a special director event flow

Adding a character is not just appending a profile file. A character entry flow must:
- validate the join mode against the current world template;
- create or import a profile matching the template's character schema;
- initialize state from profile defaults;
- create required directories and memory files;
- generate or assign home/location/position data as applicable;
- seed initial relationship scratchpads through structured relationship hints;
- append an arrival director event;
- add a `RoleAgent` to `World.agents` and `_name2agent` from the next safe stage boundary.

The safe boundary should be explicit. First implementation should allow joining between weeks, before planning starts, to avoid mid-stage schedule and concurrency inconsistencies.

Alternative considered: support joining at any instant. This would be more dramatic in-game, but the current runner assumes fixed agent lists throughout many stages. Week-boundary entry is safer and still fits a director timeline.

### Decision 5: Emit visualization snapshots as read models

Visualization state should be a derived read model rather than the source of truth. Existing JSONL/profile/state data remains authoritative. The snapshot layer composes a client-friendly view:

```json
{
  "time": "...",
  "timeline_events": [],
  "characters": [],
  "relationships": [],
  "locations": [],
  "director_event_results": []
}
```

Snapshots should be written after major safe points such as week start, director event resolution, character entry, week review, and settle. This makes future Godot integration straightforward without forcing Godot to parse every internal JSONL file.

Alternative considered: make a frontend parse raw run data. That would couple clients to internal storage and make future refactors painful.

## Risks / Trade-offs

- [Risk] The template system becomes too broad and delays useful gameplay. → Mitigation: implement one narrow `school-classroom` template first, but keep the loader generic.
- [Risk] Dynamic character entry breaks assumptions in scheduling, rewards, and position application. → Mitigation: only allow first implementation at week boundaries and add tests for roster refresh, schedules, locations, positions, and rewards.
- [Risk] Director events accidentally become direct state edits. → Mitigation: validate event resolvers so they produce simulation inputs/results, not direct internal-state mutations.
- [Risk] Visualization snapshots drift from source data. → Mitigation: treat snapshots as derived read models and regenerate from authoritative files where possible.
- [Risk] Template-defined prompts create inconsistent outputs across worlds. → Mitigation: keep structured template fields normative and use prompt fragments only for flavor/context.
- [Risk] JSON templates are less friendly for creators than YAML or forms. → Mitigation: use JSON first for runtime stability; creator tooling can later generate JSON from friendlier UI forms.

## Migration Plan

1. Add template pack data and loaders without changing the default run path.
2. Add `school-classroom` as an opt-in template and verify it can instantiate a small run.
3. Add director event persistence and validation, initially without resolving every event type.
4. Add week-boundary character entry.
5. Add visualization snapshot generation from existing run data.
6. Wire the template/director flow into a small runner or service interface.

Rollback is straightforward while the feature remains opt-in: existing `scripts/run_world.py` and existing `data/school` / `data/apartment` runs can continue using the current path.

## Open Questions

- Should the first implementation expose this as CLI-only, a Python service object, or a small HTTP API for future Godot use?
- Should template packs live under `data/world_templates/` permanently, or move to a top-level `templates/` directory once creator tooling exists?
- How much of the existing public event / encounter system should be reused for director events versus introducing a separate event resolver layer?
- What is the first target simulation scale for the playable prototype: 10, 20, or 30 characters?
