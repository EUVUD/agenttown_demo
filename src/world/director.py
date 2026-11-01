from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Collection, Dict, Iterable, List, Mapping, Sequence, Tuple

from src.world.clock import TimeState
from src.world.templates import TemplateRegistry, TemplateValidationError, WorldTemplate


_LOGGER = logging.getLogger(__name__)


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

# Simulation-input kinds a template may list under
# ``director_event_types.<type>.resolves_to``. The simulation consumes inputs by
# kind, so new templates can add event types without engine changes.
INPUT_KIND_PROMPT_CONTEXT = "prompt_context"
INPUT_KIND_PUBLIC_EVENT = "public_event"
INPUT_KIND_ENCOUNTER_CANDIDATE = "encounter_candidate"
INPUT_KIND_ARRIVAL_EVENT = "arrival_event"
INPUT_KIND_TIMELINE_EVENT = "timeline_event"
# Event types that declare no ``resolves_to`` still reach the characters as context.
DEFAULT_INPUT_KINDS: Tuple[str, ...] = (INPUT_KIND_PROMPT_CONTEXT,)

# Visibility values that restrict an input to the event's targets. Every other
# value (``public``, ``class``, ``world``, ...) is visible to the whole roster.
TARGETED_VISIBILITIES = frozenset({"targeted", "private", "personal"})

# Used when neither the caller nor the template says how many weeks a year has.
DEFAULT_WEEKS_PER_YEAR = 52

# ``produced_inputs`` keys written before inputs became template-driven. They are
# still written so existing results.jsonl rows and snapshot readers keep their shape.
_LEGACY_INPUT_KEYS = {
    "arranged_encounter": "encounter_candidate",
    "arrival": "arrival",
    "rumor": "rumor",
    "pressure": "pressure_context",
    "opportunity": "opportunity_context",
    "campus_incident": "public_event",
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


@dataclass(frozen=True)
class ActiveDirectorInput:
    """An applied director result whose event is active in the current week."""

    event: DirectorEvent
    result: DirectorEventResult
    kinds: Tuple[str, ...]
    display_name: str

    def payload(self, kind: str) -> Dict[str, Any]:
        """Return the stored input payload for ``kind``, deriving it for old rows."""
        stored = self.result.produced_inputs.get(kind)
        if isinstance(stored, Mapping):
            return dict(stored)
        return _input_payload(kind, self.event)


@dataclass(frozen=True)
class EncounterPlan:
    """An arranged encounter that fits the roster, the map, and the week."""

    event_id: str
    participants: Tuple[str, ...]
    day: int
    location: str
    description: str


@dataclass(frozen=True)
class SkippedInput:
    """A director input that could not be applied this week, with the reason."""

    event_id: str
    kind: str
    reason: str


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
                    "title": _display_name(template, event.type),
                    "summary": event.description,
                    "characters": event.targets,
                    "locations": event.locations,
                    "source": {"kind": "director_event", "id": event.event_id},
                },
            )
        results.append(result)
    return results


# Read side: what the simulation consumes -----------------------------------------


def load_active_director_inputs(
    run_dir: str | Path,
    *,
    time: str | TimeState,
    weeks_per_year: int | None = None,
    templates_root: str | Path = "data/world_templates",
) -> List[ActiveDirectorInput]:
    """Return applied director results whose events are active at ``time``.

    Activity is week-granular: an event is active from the week of its ``timing``
    for ``duration.weeks`` weeks (default 1). Only the latest result per event
    counts, and only results with status ``applied``. Runs without director data
    yield an empty list.
    """
    run_dir = Path(run_dir)
    results_path = run_dir / "director" / "results.jsonl"
    if not results_path.exists():
        return []
    template = _load_run_template(run_dir, templates_root)
    now = _as_time_state(time)
    weeks = int(
        weeks_per_year
        or template.time.get("weeks_per_year")
        or DEFAULT_WEEKS_PER_YEAR
    )

    events: Dict[str, DirectorEvent] = {}
    for obj in _read_jsonl(run_dir / "director" / "events.jsonl"):
        event = _dict_to_event(obj)
        events[event.event_id] = event
    latest: Dict[str, DirectorEventResult] = {}
    for obj in _read_jsonl(results_path):
        result = _dict_to_result(obj)
        latest[result.event_id] = result

    active: List[ActiveDirectorInput] = []
    for event_id, result in latest.items():
        event = events.get(event_id)
        if event is None or result.status != "applied":
            continue
        try:
            in_window = is_director_event_active(event, now, weeks_per_year=weeks)
        except DirectorValidationError as exc:
            # Events stored before timing was validated may carry an unreadable
            # timing. One such row must not stop the weekly loop.
            _LOGGER.warning("skipping director event %s: %s", event_id, exc)
            continue
        if not in_window:
            continue
        active.append(
            ActiveDirectorInput(
                event=event,
                result=result,
                kinds=input_kinds_for(template, event.type),
                display_name=_display_name(template, event.type),
            )
        )
    return active


def pending_arrivals(
    run_dir: str | Path,
    *,
    time: str | TimeState,
    known_characters: Collection[str],
    templates_root: str | Path = "data/world_templates",
) -> List[str]:
    """Return characters whose applied arrival event has started but who are not yet known.

    Arrival is week-granular: an arrival event counts from the week of its
    ``timing`` onward, with no end. ``known_characters`` is the current roster;
    the result keeps event order and drops duplicates. This is how a running
    world learns about characters that another process added to the run.
    """
    run_dir = Path(run_dir)
    results_path = run_dir / "director" / "results.jsonl"
    if not results_path.exists():
        return []
    template = _load_run_template(run_dir, templates_root)
    now = _as_time_state(time)
    known = set(known_characters)

    applied = {
        str(obj["event_id"])
        for obj in _read_jsonl(results_path)
        if str(obj.get("status", "")) == "applied"
    }
    arrivals: List[str] = []
    for obj in _read_jsonl(run_dir / "director" / "events.jsonl"):
        event = _dict_to_event(obj)
        if event.event_id not in applied:
            continue
        if INPUT_KIND_ARRIVAL_EVENT not in input_kinds_for(template, event.type):
            continue
        try:
            start = _parse_timing(event.timing)
        except DirectorValidationError as exc:
            _LOGGER.warning("skipping director arrival %s: %s", event.event_id, exc)
            continue
        if (start.year, start.week) > (now.year, now.week):
            continue
        for name in event.targets:
            if name not in known and name not in arrivals:
                arrivals.append(name)
    return arrivals


def is_director_event_active(
    event: DirectorEvent, time: str | TimeState, *, weeks_per_year: int
) -> bool:
    """Return True when ``time`` falls inside the event's week window."""
    start = _parse_timing(event.timing)
    now = _as_time_state(time)
    elapsed = (now.year - start.year) * int(weeks_per_year) + (now.week - start.week)
    return 0 <= elapsed < _duration_weeks(event)


def is_visible_to(event: DirectorEvent, character_name: str) -> bool:
    """Apply the event's visibility rule to one character."""
    if event.visibility in TARGETED_VISIBILITIES:
        return character_name in event.targets
    return True


def input_kinds_for(template: WorldTemplate, event_type: str) -> Tuple[str, ...]:
    """Return the simulation-input kinds the template declares for an event type."""
    schema = template.director_event_types.get(event_type, {})
    declared = schema.get("resolves_to") if isinstance(schema, Mapping) else None
    kinds = (
        [str(kind) for kind in declared if str(kind) != INPUT_KIND_TIMELINE_EVENT]
        if isinstance(declared, list)
        else []
    )
    return tuple(kinds) if kinds else DEFAULT_INPUT_KINDS


def director_prompt_context(
    inputs: Iterable[ActiveDirectorInput], character_name: str
) -> List[str]:
    """Return the context lines one character may see this week.

    Only inputs that resolve to prompt context and pass the visibility rule are
    included. The lines are context for prompts; they never touch stored state.
    """
    lines: List[str] = []
    for item in inputs:
        if INPUT_KIND_PROMPT_CONTEXT not in item.kinds:
            continue
        if not is_visible_to(item.event, character_name):
            continue
        lines.append(format_director_context_line(item))
    return lines


def format_director_context_line(item: ActiveDirectorInput) -> str:
    payload = item.payload(INPUT_KIND_PROMPT_CONTEXT)
    details: List[str] = []
    targets = [str(x) for x in payload.get("targets") or []]
    if targets:
        details.append("involves: " + ", ".join(targets))
    locations = [str(x) for x in payload.get("locations") or []]
    if locations:
        details.append("at: " + ", ".join(locations))
    try:
        intensity = int(payload.get("intensity", 1))
    except (TypeError, ValueError):
        intensity = 1
    if intensity > 1:
        details.append(f"intensity: {intensity}")
    description = str(payload.get("description") or item.event.description)
    suffix = f" ({'; '.join(details)})" if details else ""
    return f"[{item.display_name}] {description}{suffix}"


def director_public_events(
    inputs: Iterable[ActiveDirectorInput],
    *,
    year: int,
    week: int,
    n_days: int | None = None,
) -> List[Dict[str, Any]]:
    """Return this week's director incidents as public-event records.

    The records use the same field names as the simulation's public events so
    they can be offered for sign-up next to generated events, plus
    ``source_event_id`` pointing back at the director event. ``metadata.day``
    picks the weekday (default 1) and ``metadata.event_name`` the title.
    """
    records: List[Dict[str, Any]] = []
    used_names: set[str] = set()
    for item in inputs:
        if INPUT_KIND_PUBLIC_EVENT not in item.kinds:
            continue
        payload = item.payload(INPUT_KIND_PUBLIC_EVENT)
        description = str(payload.get("summary") or item.event.description)
        name = str(
            item.event.metadata.get("event_name")
            or f"{item.display_name}: {_shorten(description, 40)}"
        )
        if name.strip().lower() in used_names:
            name = f"{name} ({item.event.event_id})"
        used_names.add(name.strip().lower())
        targets = [str(x) for x in payload.get("targets") or []]
        records.append(
            {
                "source_event_id": item.event.event_id,
                "event_id": f"director-{item.event.event_id}",
                "event_name": name,
                "start_year": int(year),
                "start_week": int(week),
                "start_day": _event_day(item.event, n_days),
                "repeat_weeks": _duration_weeks(item.event),
                "description": description,
                "eligible_participants": (
                    targets
                    if targets and item.event.visibility in TARGETED_VISIBILITIES
                    else "all"
                ),
            }
        )
    return records


def plan_arranged_encounters(
    inputs: Iterable[ActiveDirectorInput],
    *,
    known_characters: Collection[str],
    busy_days: Mapping[str, Collection[int]],
    valid_locations: Collection[str],
    n_days: int,
) -> Tuple[List[EncounterPlan], List[SkippedInput]]:
    """Fit encounter candidates into the week without double-booking anyone.

    A candidate needs at least two characters from the active roster, one of its
    locations on the map, and a day on which every participant is free. Days
    taken by earlier plans in the same call count as busy.
    """
    known = set(known_characters)
    locations = set(valid_locations)
    reserved: Dict[str, set[int]] = {
        name: set(days) for name, days in busy_days.items()
    }
    plans: List[EncounterPlan] = []
    skipped: List[SkippedInput] = []
    for item in inputs:
        if INPUT_KIND_ENCOUNTER_CANDIDATE not in item.kinds:
            continue
        payload = item.payload(INPUT_KIND_ENCOUNTER_CANDIDATE)
        requested = _unique([str(x) for x in payload.get("characters") or item.event.targets])
        participants = sorted(name for name in requested if name in known)
        if len(participants) < 2:
            skipped.append(
                SkippedInput(
                    item.event.event_id,
                    INPUT_KIND_ENCOUNTER_CANDIDATE,
                    "needs at least two characters from the active roster; "
                    f"requested {requested}",
                )
            )
            continue
        wanted = [str(x) for x in payload.get("locations") or item.event.locations]
        location = next((loc for loc in wanted if loc in locations), None)
        if location is None:
            skipped.append(
                SkippedInput(
                    item.event.event_id,
                    INPUT_KIND_ENCOUNTER_CANDIDATE,
                    f"no valid public location among {wanted}",
                )
            )
            continue
        day = next(
            (
                d
                for d in range(1, int(n_days) + 1)
                if all(d not in reserved.get(name, set()) for name in participants)
            ),
            None,
        )
        if day is None:
            skipped.append(
                SkippedInput(
                    item.event.event_id,
                    INPUT_KIND_ENCOUNTER_CANDIDATE,
                    "no day this week when all participants are free",
                )
            )
            continue
        for name in participants:
            reserved.setdefault(name, set()).add(day)
        plans.append(
            EncounterPlan(
                event_id=item.event.event_id,
                participants=tuple(participants),
                day=day,
                location=location,
                description=str(payload.get("description") or item.event.description),
            )
        )
    return plans, skipped


def record_director_application(
    run_dir: str | Path,
    *,
    time: str | TimeState,
    event_id: str,
    kind: str,
    status: str,
    detail: str,
    characters: Sequence[str] = (),
    locations: Sequence[str] = (),
) -> Dict[str, Any]:
    """Append one weekly application outcome to ``director/applications.jsonl``.

    The file is append-only and ordered by simulation time, so resume cleanup
    treats it like the other simulation outputs.
    """
    row = {
        "time": str(_as_time_state(time)),
        "event_id": str(event_id),
        "kind": str(kind),
        "status": str(status),
        "detail": str(detail),
        "characters": [str(x) for x in characters],
        "locations": [str(x) for x in locations],
    }
    _append_jsonl(Path(run_dir) / "director" / "applications.jsonl", row)
    return row


# Internals -------------------------------------------------------------------------


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
    _parse_timing(str(payload["timing"]))

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
    kinds = input_kinds_for(template, event.type)
    produced: Dict[str, Any] = {kind: _input_payload(kind, event) for kind in kinds}
    legacy_key = _LEGACY_INPUT_KEYS.get(event.type, event.type)
    produced.setdefault(legacy_key, _legacy_input_payload(event))

    display = _display_name(template, event.type)
    return DirectorEventResult(
        event_id=event.event_id,
        status="applied",
        explanation=f"Resolved {display} into simulation inputs: {', '.join(kinds)}.",
        affected_characters=event.targets,
        affected_locations=event.locations,
        produced_inputs=produced,
        timeline_entry_id=f"timeline-{event.event_id}",
    )


def _input_payload(kind: str, event: DirectorEvent) -> Dict[str, Any]:
    if kind == INPUT_KIND_PROMPT_CONTEXT:
        return {
            "targets": list(event.targets),
            "visibility": event.visibility,
            "intensity": event.intensity,
            "locations": list(event.locations),
            "description": event.description,
        }
    if kind == INPUT_KIND_PUBLIC_EVENT:
        return {
            "locations": list(event.locations),
            "summary": event.description,
            "targets": list(event.targets),
        }
    if kind == INPUT_KIND_ENCOUNTER_CANDIDATE:
        return {
            "characters": list(event.targets),
            "locations": list(event.locations),
            "description": event.description,
        }
    if kind == INPUT_KIND_ARRIVAL_EVENT:
        return {"characters": list(event.targets), "locations": list(event.locations)}
    return {
        "targets": list(event.targets),
        "locations": list(event.locations),
        "description": event.description,
    }


def _legacy_input_payload(event: DirectorEvent) -> Dict[str, Any]:
    if event.type == "arranged_encounter":
        return {"characters": event.targets, "locations": event.locations}
    if event.type == "arrival":
        return {"characters": event.targets, "locations": event.locations}
    if event.type == "rumor":
        return {"visibility": event.visibility, "targets": event.targets}
    if event.type in ("pressure", "opportunity"):
        return {"targets": event.targets, "intensity": event.intensity}
    if event.type == "campus_incident":
        return {"locations": event.locations, "summary": event.description}
    return {"targets": event.targets, "locations": event.locations}


def _display_name(template: WorldTemplate, event_type: str) -> str:
    schema = template.director_event_types.get(event_type, {})
    if isinstance(schema, Mapping):
        return str(schema.get("display_name", event_type))
    return event_type


def _duration_weeks(event: DirectorEvent) -> int:
    try:
        weeks = int(event.duration.get("weeks", 1))
    except (TypeError, ValueError, AttributeError):
        weeks = 1
    return max(1, weeks)


def _event_day(event: DirectorEvent, n_days: int | None) -> int:
    try:
        day = int(event.metadata.get("day", 1))
    except (TypeError, ValueError, AttributeError):
        day = 1
    day = max(1, day)
    if n_days is not None:
        day = min(day, int(n_days))
    return day


def _parse_timing(timing: str) -> TimeState:
    try:
        return TimeState.from_string(str(timing))
    except (KeyError, ValueError) as exc:
        raise DirectorValidationError(
            f"director event timing must look like Y2020-W01-begin, got: {timing!r}"
        ) from exc


def _as_time_state(value: str | TimeState) -> TimeState:
    if isinstance(value, TimeState):
        return value
    return TimeState.from_string(str(value))


def _shorten(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _unique(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


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


def _dict_to_result(obj: Mapping[str, Any]) -> DirectorEventResult:
    return DirectorEventResult(
        event_id=str(obj["event_id"]),
        status=str(obj.get("status", "")),
        explanation=str(obj.get("explanation", "")),
        affected_characters=[str(x) for x in obj.get("affected_characters", [])],
        affected_locations=[str(x) for x in obj.get("affected_locations", [])],
        produced_inputs=dict(obj.get("produced_inputs") or {}),
        timeline_entry_id=obj.get("timeline_entry_id"),
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
