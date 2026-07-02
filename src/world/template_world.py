from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.world.director import create_director_event
from src.world.templates import TemplateRegistry, TemplateValidationError, WorldTemplate


class CharacterEntryError(ValueError):
    """Raised when a character cannot safely join a running world."""


@dataclass(frozen=True)
class CharacterEntryResult:
    character_name: str
    join_mode: str
    profile_path: Path
    arrival_event_id: str
    inserted_stage: str


def create_world_from_template(
    template_id: str,
    payload: Mapping[str, Any],
    *,
    run_id: str | None = None,
    data_root: str | Path = "data",
    templates_root: str | Path = "data/world_templates",
) -> Path:
    registry = TemplateRegistry(root=templates_root)
    template = registry.load(template_id)
    registry.validate_creator_payload(template_id, payload)

    run_name = f"{template_id}_{run_id}" if run_id else template_id
    run_dir = Path(data_root) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    world_payload = dict(payload.get("world", {}))
    (run_dir / "template_meta.json").write_text(
        json.dumps(
            {
                "template_id": template.template_id,
                "template_name": template.name,
                "template_version": template.version,
                "world": world_payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_worldview(run_dir, template, world_payload)
    _write_locations(run_dir, template)
    _ensure_runtime_dirs(run_dir)

    for draft in payload["characters"]:
        _initialize_character_storage(run_dir, template, dict(draft))

    return run_dir


def add_character_to_world(
    run_dir: str | Path,
    request: Mapping[str, Any],
    *,
    current_stage: Any = "BEGIN",
    templates_root: str | Path = "data/world_templates",
    active_world: Any | None = None,
) -> CharacterEntryResult:
    run_dir = Path(run_dir)
    stage = _normalize_stage(current_stage)
    if stage.name != "BEGIN":
        raise CharacterEntryError(
            f"characters can join only at safe week boundaries; current stage is {stage.name}"
        )

    template = _load_run_template(run_dir, templates_root)
    registry = TemplateRegistry(root=templates_root)
    join_mode = str(request.get("join_mode", "")).strip()
    try:
        registry.validate_join_mode(template, join_mode)
        character = dict(request.get("character", {}))
        registry.validate_character_draft(template, character)
    except TemplateValidationError as exc:
        raise CharacterEntryError(str(exc)) from exc

    allowed_roles = template.join_modes[join_mode].get("roles", [])
    if allowed_roles and character.get("role") not in allowed_roles:
        raise CharacterEntryError(
            f"join mode {join_mode} does not allow role: {character.get('role')}"
        )

    name = str(character["name"]).strip()
    persona_root = run_dir / "persona" / name
    if persona_root.exists():
        raise CharacterEntryError(f"character already exists: {name}")

    profile_path = _initialize_character_storage(run_dir, template, character)
    _ensure_private_location(run_dir, name, template)
    _seed_known_character_hints(
        persona_root,
        request.get("known_character_hints", []),
        str(request.get("arrival_context", "")),
    )
    event = create_director_event(
        run_dir,
        {
            "type": "arrival",
            "timing": "Y2020-W00-begin",
            "targets": [name],
            "visibility": "class",
            "intensity": 1,
            "locations": [str(request.get("starting_location", "classroom"))],
            "duration": {"weeks": 1},
            "description": str(
                request.get("arrival_context")
                or template.join_modes[join_mode].get("description")
                or f"{name} joins the world."
            ),
            "metadata": {"join_mode": join_mode},
        },
        templates_root=templates_root,
    )
    _append_timeline(
        run_dir,
        {
            "id": f"timeline-{event.event_id}",
            "time": event.timing,
            "type": "character_arrival",
            "title": f"{name} joins",
            "summary": event.description,
            "characters": [name],
            "locations": event.locations,
            "source": {"kind": "director_event", "id": event.event_id},
        },
    )

    if active_world is not None and hasattr(active_world, "add_agent_from_data"):
        active_world.add_agent_from_data(name)

    return CharacterEntryResult(
        character_name=name,
        join_mode=join_mode,
        profile_path=profile_path,
        arrival_event_id=event.event_id,
        inserted_stage=stage.name,
    )


def _load_run_template(
    run_dir: Path, templates_root: str | Path = "data/world_templates"
) -> WorldTemplate:
    meta_path = run_dir / "template_meta.json"
    if not meta_path.exists():
        raise CharacterEntryError(f"run has no template metadata: {run_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return TemplateRegistry(root=templates_root).load(str(meta["template_id"]))


def _write_worldview(
    run_dir: Path, template: WorldTemplate, world_payload: Mapping[str, Any]
) -> None:
    background = template.prompt_fragments.get("worldview", template.description).strip()
    worldview = {
        "template_id": template.template_id,
        "name": template.name,
        "background": background,
        "world": dict(world_payload),
        "time": template.time,
    }
    (run_dir / "worldview.json").write_text(
        json.dumps(worldview, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_locations(run_dir: Path, template: WorldTemplate) -> None:
    public = {}
    for key, data in template.location_archetypes.items():
        public[key] = {
            "display_name": data.get("display_name", key),
            "size": data.get("size", "medium"),
            "description": data.get("description", ""),
            "objects": data.get("objects", []),
        }
    (run_dir / "locations.json").write_text(
        json.dumps({"public": public, "private": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _ensure_runtime_dirs(run_dir: Path) -> None:
    for dirname in ("director", "visualization", "reward", "god"):
        (run_dir / dirname).mkdir(parents=True, exist_ok=True)


def _initialize_character_storage(
    run_dir: Path, template: WorldTemplate, draft: Mapping[str, Any]
) -> Path:
    name = str(draft["name"]).strip()
    root = run_dir / "persona" / name
    profile_dir = root / "profile"
    scratch = root / "memory" / "scratchpad"
    for path in (
        profile_dir,
        root / "generation",
        root / "memory",
        scratch / "characters",
        scratch / "others",
        root / "contact",
    ):
        path.mkdir(parents=True, exist_ok=True)

    profile = _profile_from_draft(template, draft)
    profile_path = profile_dir / "year=2020.json"
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _ensure_jsonl(root / "state.jsonl", _initial_state(template))
    _ensure_jsonl(root / "schedule.jsonl")
    _ensure_jsonl(root / "activity.jsonl")
    _ensure_jsonl(root / "reward.jsonl")
    _ensure_jsonl(root / "memory" / "weekly_diary.jsonl")
    _ensure_jsonl(root / "memory" / "history.jsonl")
    _ensure_jsonl(scratch / "general.jsonl", {"time": "Y2020-W00-begin", "content": profile["brief_introduction"]})
    _ensure_jsonl(scratch / "working_memory.jsonl")
    _ensure_jsonl(scratch / ".access_log.jsonl")
    return profile_path


def _profile_from_draft(template: WorldTemplate, draft: Mapping[str, Any]) -> dict:
    role = str(draft.get("role", "student"))
    archetype = template.role_archetypes.get(role, {})
    motivation = str(draft.get("motivation", "Find a place in the world."))
    personality = str(draft.get("personality", "Observant and adaptable."))
    return {
        "name": str(draft["name"]),
        "gender": str(draft.get("gender", "unspecified")),
        "appearance_and_impression": str(draft["appearance_and_impression"]),
        "brief_introduction": str(draft["brief_introduction"]),
        "talents": {
            "qualitative": str(draft.get("talents", archetype.get("talents", ""))),
            "quantitative": dict(archetype.get("talent_scores", {})),
        },
        "details": str(draft.get("details", draft["brief_introduction"])),
        "conflicts": str(draft.get("conflicts", "Adapting to the current world.")),
        "core_motivation": motivation,
        "personality_traits": {
            "qualitative": personality,
            "quantitative": dict(archetype.get("personality_scores", {})),
        },
        "preferences": str(draft.get("preferences", "")),
        "position": dict(archetype.get("position", {"role": role, "type": "non-work"})),
        "init_skills": dict(draft.get("init_skills", archetype.get("init_skills", {}))),
        "init_assets": dict(
            draft.get("init_assets", {"deposit": 0, "possessions": []})
        ),
        "extra_income": int(draft.get("extra_income", 0)),
        "values": str(draft.get("values", "")),
        "birthday": str(draft.get("birthday", "Y2004-W01-begin")),
        "birth_year": int(draft.get("birth_year", 2004)),
    }


def _initial_state(template: WorldTemplate) -> dict:
    state = {
        "time": "Y2020-W00-begin",
        "vitality": 80,
        "fulfillment": {"mood": 60, "social": 50, "esteem": 50, "material": 50},
        "skills": {},
        "assets": {"money": 0, "possessions": []},
    }
    state.update(template.default_state)
    return state


def _ensure_jsonl(path: Path, first_obj: Mapping[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    if first_obj is not None and path.stat().st_size == 0:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dict(first_obj), ensure_ascii=False) + "\n")


def _ensure_private_location(run_dir: Path, name: str, template: WorldTemplate) -> None:
    if not any(mode.get("requires_home") for mode in template.join_modes.values()):
        return
    path = run_dir / "locations.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    private = data.setdefault("private", {})
    private.setdefault(
        f"home/{name}",
        {
            "owner": name,
            "display_name": f"{name}'s Home",
            "size": "small",
            "description": f"A private starting space for {name}.",
            "objects": [],
        },
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_known_character_hints(
    persona_root: Path, hints: Any, arrival_context: str
) -> None:
    if arrival_context:
        _append_jsonl(
            persona_root / "memory" / "scratchpad" / "general.jsonl",
            {"time": "Y2020-W00-begin", "content": arrival_context},
        )
    if not isinstance(hints, list):
        return
    for hint in hints:
        if not isinstance(hint, Mapping) or not hint.get("name"):
            continue
        _append_jsonl(
            persona_root
            / "memory"
            / "scratchpad"
            / "characters"
            / f"{hint['name']}.jsonl",
            {
                "time": "Y2020-W00-begin",
                "content": str(hint.get("context", "Known before joining.")),
            },
        )


def _append_timeline(run_dir: Path, item: Mapping[str, Any]) -> None:
    _append_jsonl(run_dir / "visualization" / "timeline.jsonl", item)


def _append_jsonl(path: Path, item: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(item), ensure_ascii=False) + "\n")


def _normalize_stage(stage: Any):
    from src.world.clock import Stage

    if isinstance(stage, Stage):
        return stage
    return Stage[str(stage).upper()]
