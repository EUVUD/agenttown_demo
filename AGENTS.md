# Project Instructions

## Scope

- `GAME_DEVELOPMENT_PLAN.md` is the roadmap for the playable Godot game; it is not implemented by the legacy runner.
- Preserve the behavior and file contracts of `scripts/run_world.py` unless an approved migration explicitly changes them.
- Keep new playable-runtime state separate from legacy JSONL run data until a documented adapter exists.

## Layout

| Area | Purpose |
|---|---|
| `src/agents/` | Role-agent behavior, prompts, context, validation, and data access |
| `src/world/` | Legacy simulation, templates, Director events, and visualization |
| `scripts/` | CLI entry points and offline analysis tools |
| `data/world_templates/` | Versioned creator-facing world-template packs |
| `tests/` | Focused Python tests |
| `openspec/specs/` | Current behavior specifications |
| `docs/director_world.md` | Template/Director/Godot snapshot contract |

## Commands

| Task | Command |
|---|---|
| Install dependencies | `pip install -r requirements.txt` |
| Run one focused test module | `python -m pytest tests/test_template_director_world.py -q` |
| Run all tests | `python -m pytest -q` |
| Inspect the first template schema | `python scripts/director_world.py schema school-classroom` |
| Smoke-test the legacy runner | `python scripts/run_world.py --world school --max-agents 5 --years 1 --weeks 1` |

## Documentation Language

- Write all new or modified project documentation in English, including plans, `README*`, `docs/`, and OpenSpec proposal, design, spec, and task artifacts.
- Keep existing localized documentation unchanged unless the task explicitly requests its translation or revision.
- Refer to OpenSpec artifacts as `proposal`, `design`, `spec`, and `tasks`; do not translate those artifact labels.

## Data and Contracts

- Treat `data/school/`, `data/apartment/`, and `data/world_templates/` as checked-in source fixtures.
- Do not edit generated run directories (`data/<world>_<runid>/`), `logs/`, or `rft_data/` unless the task explicitly targets generated data.
- Never commit `config.json`, API keys, provider credentials, or real generated conversation traces.
- Godot or other clients must consume `visualization/current.json` and snapshot files, not raw prompts, scratchpads, generation traces, or internal JSONL files.
- Director events may add context and timeline entries; they must not directly mutate character state, relationships, profiles, or scratchpads.

## Change Rules

- When a roadmap step in `GAME_DEVELOPMENT_PLAN.md` is implemented and its acceptance criteria pass, update its checklist status in the same change; never mark incomplete work as complete.
- Keep simulation persistence append-only and time-ordered when modifying legacy JSONL paths.
- Add focused tests in `tests/test_<module>.py` for reusable validators, schemas, transformations, or data contracts.
- Run the narrowest relevant test before the full suite.
- Put new behavior specifications under `openspec/` when changing template, Director, visualization, or game-runtime contracts.
- Prefer additive, backwards-compatible changes to template packs and visualization snapshots.
