from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

# Used when a run has recorded nothing yet (a freshly created template world).
DEFAULT_SNAPSHOT_TIME = "Y2020-W00-begin"


def generate_visualization_snapshot(
    run_dir: str | Path,
    *,
    time: str | None = None,
) -> Dict[str, Any]:
    """Write ``visualization/current.json`` plus a per-time snapshot file.

    ``time`` labels the snapshot and names the file under ``snapshots/``. When
    it is omitted the latest time recorded in the run data is used (see
    :func:`infer_snapshot_time`), so successive safe points produce distinct
    files instead of overwriting one default-named snapshot.
    """
    run_dir = Path(run_dir)
    if time is None:
        time = infer_snapshot_time(run_dir)
    snapshot = {
        "time": time,
        "timeline_events": _timeline_events(run_dir),
        "characters": _character_summaries(run_dir),
        "relationships": _relationship_summaries(run_dir),
        "locations": _location_activity(run_dir),
        "director_event_results": _read_jsonl(run_dir / "director" / "results.jsonl"),
        "director_applications": _read_jsonl(run_dir / "director" / "applications.jsonl"),
    }
    out_dir = run_dir / "visualization"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "current.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    safe_time = time.replace("/", "_").replace(":", "_")
    snapshots = out_dir / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    (snapshots / f"{safe_time}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return snapshot


def infer_snapshot_time(run_dir: str | Path) -> str:
    """Return the latest simulation time recorded anywhere in the run.

    Sources, each optional: the legacy runner's ``checkpoint.json`` (a completed
    week counts as its ``settle`` stage), the last row of every character's
    ``state.jsonl``, and director application records. Timeline entries are not
    consulted because director events carry the time they are scheduled for,
    which may lie ahead of the simulation. Values that do not parse as a world
    time are ignored; when nothing is recorded the result is
    :data:`DEFAULT_SNAPSHOT_TIME`.
    """
    from src.world.clock import TimeState

    run_dir = Path(run_dir)
    candidates: List[str] = []

    checkpoint_path = run_dir / "checkpoint.json"
    if checkpoint_path.exists():
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            year = int(checkpoint["year"])
            week = int(checkpoint["week"])
            stage = "settle" if week > 0 else "begin"
            candidates.append(f"Y{year}-W{week:02d}-{stage}")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            pass

    persona_root = run_dir / "persona"
    if persona_root.exists():
        for persona in sorted(p for p in persona_root.iterdir() if p.is_dir()):
            last_state = _read_last_jsonl(persona / "state.jsonl") or {}
            if last_state.get("time"):
                candidates.append(str(last_state["time"]))

    for item in _read_jsonl(run_dir / "director" / "applications.jsonl"):
        if item.get("time"):
            candidates.append(str(item["time"]))

    parsed: List[TimeState] = []
    for value in candidates:
        try:
            parsed.append(TimeState.from_string(value))
        except (KeyError, ValueError):
            continue
    if not parsed:
        return DEFAULT_SNAPSHOT_TIME
    return str(max(parsed))


def _timeline_events(run_dir: Path) -> List[dict]:
    seen = set()
    events = []
    for item in _read_jsonl(run_dir / "visualization" / "timeline.jsonl"):
        event_id = item.get("id")
        if event_id in seen:
            continue
        seen.add(event_id)
        events.append(
            {
                "id": event_id,
                "time": item.get("time", ""),
                "type": item.get("type", "event"),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "characters": item.get("characters", []),
                "locations": item.get("locations", []),
                "source": item.get("source", {}),
            }
        )
    return events


def _character_summaries(run_dir: Path) -> List[dict]:
    root = run_dir / "persona"
    if not root.exists():
        return []
    result = []
    timeline = _timeline_events(run_dir)
    for persona in sorted(p for p in root.iterdir() if p.is_dir()):
        profile = _read_first_profile(persona)
        if not profile:
            continue
        state = _state_content(_read_last_jsonl(persona / "state.jsonl"))
        name = profile.get("name", persona.name)
        recent_event_ids = [
            item["id"]
            for item in timeline
            if name in item.get("characters", [])
        ][-5:]
        result.append(
            {
                "name": name,
                "role": profile.get("position", {}).get("role", profile.get("role", "")),
                "last_known_location": state.get("location"),
                "brief_introduction": profile.get("brief_introduction", ""),
                "status_highlights": {
                    "vitality": state.get("vitality"),
                    "fulfillment": state.get("fulfillment"),
                },
                "recent_event_refs": recent_event_ids,
            }
        )
    return result


def _relationship_summaries(run_dir: Path) -> List[dict]:
    relationships = []
    for persona in sorted((run_dir / "persona").glob("*")):
        char_dir = persona / "memory" / "scratchpad" / "characters"
        if not char_dir.exists():
            continue
        for pad in sorted(char_dir.glob("*.jsonl")):
            last = _read_last_jsonl(pad)
            if not last:
                continue
            relationships.append(
                {
                    "source": persona.name,
                    "target": pad.stem,
                    "summary": _relationship_summary_text(last),
                    "confidence": "derived",
                }
            )
    return relationships


def _location_activity(run_dir: Path) -> List[dict]:
    path = run_dir / "locations.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    timeline = _timeline_events(run_dir)
    result = []
    for kind in ("public", "private"):
        for key, loc in sorted((data.get(kind) or {}).items()):
            events = [
                item for item in timeline if key in item.get("locations", [])
            ]
            result.append(
                {
                    "key": key,
                    "kind": kind,
                    "display_name": loc.get("display_name", key),
                    "description": loc.get("description", ""),
                    "active_events": events,
                }
            )
    return result


# Longest relationship text a snapshot publishes. Matches the engine's own clip for
# scratchpad summaries, so a snapshot never carries more than a prompt would.
_RELATIONSHIP_TEXT_LIMIT = 500


def _relationship_summary_text(row: Mapping[str, Any]) -> str:
    """Return the public text for a scratchpad row.

    The engine writes ``{"summary", "content"}`` where ``content`` is the full
    private note. A snapshot shows the summary, or a clipped ``content`` for rows
    that have none (for example hints seeded at character entry).
    """
    summary = row.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    content = str(row.get("content", "") or "")
    if len(content) > _RELATIONSHIP_TEXT_LIMIT:
        return content[: _RELATIONSHIP_TEXT_LIMIT - 1].rstrip() + "…"
    return content


def _state_content(row: dict | None) -> dict:
    """Unwrap a ``state.jsonl`` row.

    The engine writes ``{"time": ..., "content": {...}}``; older template runs
    wrote the fields flat next to ``time``. Both shapes are accepted.
    """
    if not row:
        return {}
    content = row.get("content")
    if isinstance(content, dict):
        return content
    return row


def _read_first_profile(persona_root: Path) -> dict:
    profiles = sorted((persona_root / "profile").glob("year=*.json"))
    if not profiles:
        return {}
    return json.loads(profiles[0].read_text(encoding="utf-8"))


def _read_last_jsonl(path: Path) -> dict | None:
    rows = _read_jsonl(path)
    return rows[-1] if rows else None


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
