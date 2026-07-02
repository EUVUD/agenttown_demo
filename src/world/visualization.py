from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping


def generate_visualization_snapshot(
    run_dir: str | Path,
    *,
    time: str = "Y2020-W00-begin",
) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    snapshot = {
        "time": time,
        "timeline_events": _timeline_events(run_dir),
        "characters": _character_summaries(run_dir),
        "relationships": _relationship_summaries(run_dir),
        "locations": _location_activity(run_dir),
        "director_event_results": _read_jsonl(run_dir / "director" / "results.jsonl"),
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
        state = _read_last_jsonl(persona / "state.jsonl") or {}
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
                    "summary": last.get("content", ""),
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
