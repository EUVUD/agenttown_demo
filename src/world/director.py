from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping

from src.world.templates import TemplateRegistry, TemplateValidationError, WorldTemplate


class DirectorValidationError(ValueError):
    """Raised when a director event violates template or safety rules."""


DIRECT_STATE_KEYS = {
    "vitality",
    "fulfillment",
    "skills",
    "money",
    "relationship_score",
    "relationship_scores",
    "relationships",
    "scratchpad",
    "scratchpads",
    "profile",
    "state",
}


@dataclass(frozen=True)
class DirectorEvent:
    event_id: str
    type: str
    timing: str
    targets: List[str]
    visibility: str
    intensity: int
    locations: List[str]
    duration: Dict[str, Any]
    description: str
    template_id: str
    status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectorEventResult:
    event_id: str
    status: str
    explanation: str
    affected_characters: List[str]
    affected_locations: List[str]
    produced_inputs: Dict[str, Any]
    timeline_entry_id: str | None = None


def create_director_event(
    run_dir: str | Path,
    payload: Mapping[str, Any],
    *,
    templates_root: str | Path = "data/world_templates",
) -> DirectorEvent:
    run_dir = Path(run_dir)
    template = _load_run_template(run_dir, templates_root)
    event = _event_from_payload(template, payload)
    _append_jsonl(run_dir / "director" / "events.jsonl", asdict(event))
    return event


def resolve_director_events(
    run_dir: str | Path,
    *,
    templates_root: str | Path = "data/world_templates",
) -> List[DirectorEventResult]:
    run_dir = Path(run_dir)
    template = _load_run_template(run_dir, templates_root)
    events = [_dict_to_event(obj) for obj in _read_jsonl(run_dir / "director" / "events.jsonl")]
    resolved_ids = {
        obj.get("event_id") for obj in _read_jsonl(run_dir / "director" / "results.jsonl")
    }
    results: List[DirectorEventResult] = []
    for event in events:
        if event.event_id in resolved_ids:
            continue
        result = _resolve_one(template, event)
        _append_jsonl(run_dir / "director" / "results.jsonl", asdict(result))
        if result.timeline_entry_id:
            _append_jsonl(
                run_dir / "visualization" / "timeline.jsonl",
                {
                    "id": result.timeline_entry_id,
                    "time": event.timing,
                    "type": f"director_{event.type}",
                    "title": template.director_event_types[event.type].get(
                        "display_name", event.type
                    ),
                    "summary": event.description,
                    "characters": event.targets,
                    "locations": event.locations,
                    "source": {"kind": "director_event", "id": event.event_id},
                },
            )
        results.append(result)
    return results


def _event_from_payload(
    template: WorldTemplate, payload: Mapping[str, Any]
) -> DirectorEvent:
    if not isinstance(payload, Mapping):
        raise DirectorValidationError("director event payload must be an object")
    _reject_direct_state_edits(payload)
    event_type = str(payload.get("type", "")).strip()
    try:
        TemplateRegistry(root=template.root.parent).validate_event_type(
            template, event_type
        )
    except TemplateValidationError as exc:
        raise DirectorValidationError(str(exc)) from exc

    missing = [
        key
        for key in ("timing", "description")
        if key not in payload or payload[key] in ("", None)
    ]
    if missing:
        raise DirectorValidationError(
            f"missing required director event fields: {', '.join(missing)}"
        )

    type_schema = template.director_event_types[event_type]
    required_params = type_schema.get("required", [])
    missing_params = [
        key for key in required_params if key not in payload or payload[key] in ("", None)
    ]
    if missing_params:
        raise DirectorValidationError(
            f"missing required fields for {event_type}: {', '.join(missing_params)}"
        )

    return DirectorEvent(
        event_id=str(payload.get("event_id") or f"de-{uuid.uuid4().hex[:12]}"),
        type=event_type,
        timing=str(payload["timing"]),
        targets=[str(x) for x in payload.get("targets", [])],
        visibility=str(payload.get("visibility", type_schema.get("visibility", "world"))),
        intensity=int(payload.get("intensity", 1)),
        locations=[str(x) for x in payload.get("locations", [])],
        duration=dict(payload.get("duration", {})),
        description=str(payload["description"]),
        template_id=template.template_id,
        status=str(payload.get("status", "pending")),
        metadata=dict(payload.get("metadata", {})),
    )


def _reject_direct_state_edits(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in DIRECT_STATE_KEYS:
                raise DirectorValidationError(
                    f"director events cannot directly edit internal state: {path}{key}"
                )
            _reject_direct_state_edits(nested, f"{path}{key}.")
    elif isinstance(value, list):
        for idx, nested in enumerate(value):
            _reject_direct_state_edits(nested, f"{path}{idx}.")


def _resolve_one(
    template: WorldTemplate, event: DirectorEvent
) -> DirectorEventResult:
    if event.type == "arranged_encounter":
        produced = {"encounter_candidate": {"characters": event.targets, "locations": event.locations}}
    elif event.type == "arrival":
        produced = {"arrival": {"characters": event.targets, "locations": event.locations}}
    elif event.type == "rumor":
        produced = {"rumor": {"visibility": event.visibility, "targets": event.targets}}
    elif event.type == "pressure":
        produced = {"pressure_context": {"targets": event.targets, "intensity": event.intensity}}
    elif event.type == "opportunity":
        produced = {"opportunity_context": {"targets": event.targets, "intensity": event.intensity}}
    elif event.type == "campus_incident":
        produced = {"public_event": {"locations": event.locations, "summary": event.description}}
    else:
        produced = {event.type: {"targets": event.targets, "locations": event.locations}}

    display = template.director_event_types[event.type].get("display_name", event.type)
    return DirectorEventResult(
        event_id=event.event_id,
        status="applied",
        explanation=f"Resolved {display} as structured simulation input.",
        affected_characters=event.targets,
        affected_locations=event.locations,
        produced_inputs=produced,
        timeline_entry_id=f"timeline-{event.event_id}",
    )


def _load_run_template(
    run_dir: Path, templates_root: str | Path = "data/world_templates"
) -> WorldTemplate:
    meta_path = run_dir / "template_meta.json"
    if not meta_path.exists():
        raise DirectorValidationError(f"run has no template metadata: {run_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return TemplateRegistry(root=templates_root).load(str(meta["template_id"]))


def _dict_to_event(obj: Mapping[str, Any]) -> DirectorEvent:
    return DirectorEvent(
        event_id=str(obj["event_id"]),
        type=str(obj["type"]),
        timing=str(obj["timing"]),
        targets=[str(x) for x in obj.get("targets", [])],
        visibility=str(obj.get("visibility", "world")),
        intensity=int(obj.get("intensity", 1)),
        locations=[str(x) for x in obj.get("locations", [])],
        duration=dict(obj.get("duration", {})),
        description=str(obj.get("description", "")),
        template_id=str(obj["template_id"]),
        status=str(obj.get("status", "pending")),
        metadata=dict(obj.get("metadata", {})),
    )


def _append_jsonl(path: Path, item: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(item), ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
