"""Director inputs: template-driven resolution and weekly consumption contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.world.clock import Stage, TimeState
from src.world.director import (
    DEFAULT_WEEKS_PER_YEAR,
    INPUT_KIND_ENCOUNTER_CANDIDATE,
    INPUT_KIND_PROMPT_CONTEXT,
    INPUT_KIND_PUBLIC_EVENT,
    DirectorValidationError,
    create_director_event,
    director_prompt_context,
    director_public_events,
    load_active_director_inputs,
    pending_arrivals,
    plan_arranged_encounters,
    record_director_application,
    resolve_director_events,
)
from src.world.director_service import DirectorWorldService
from src.world.template_world import (
    CharacterEntryError,
    add_character_to_world,
    create_world_from_template,
)
from src.world.visualization import generate_visualization_snapshot, infer_snapshot_time


def _character(name: str, role: str = "student") -> dict:
    return {
        "name": name,
        "role": role,
        "gender": "female",
        "brief_introduction": f"{name} is new here.",
        "appearance_and_impression": "Short hair and a clean uniform.",
        "personality": "Careful and observant.",
        "motivation": "Find a place in the class.",
    }


def _make_world(tmp_path: Path, names=("Lin", "Mina")) -> Path:
    return create_world_from_template(
        "school-classroom",
        {
            "world": {"class_name": "Class 2-3", "school_name": "North High"},
            "characters": [_character(name) for name in names],
        },
        run_id="01010000",
        data_root=tmp_path / "data",
    )


def _event(event_type: str, **overrides) -> dict:
    payload = {
        "type": event_type,
        "timing": "Y2020-W01-begin",
        "targets": ["Lin"],
        "visibility": "class",
        "intensity": 1,
        "locations": ["classroom"],
        "duration": {"weeks": 1},
        "description": f"A {event_type} unfolds.",
    }
    payload.update(overrides)
    return payload


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class FakeClock:
    def __init__(self, time: TimeState) -> None:
        self.time = time

    def get_time(self) -> TimeState:
        return self.time


class FakeActiveWorld:
    """Stands in for the legacy World: a clock plus the roster hook."""

    def __init__(self, time: TimeState) -> None:
        self.clock = FakeClock(time)
        self.added: list[str] = []

    def add_agent_from_data(self, name: str) -> None:
        self.added.append(name)


# Resolution ---------------------------------------------------------------------


def test_resolution_follows_the_template_and_keeps_legacy_keys(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    for payload in (
        _event("rumor", intensity=3),
        _event("pressure", visibility="targeted"),
        _event("campus_incident", targets=[]),
        _event("arranged_encounter", targets=["Lin", "Mina"], locations=["library"]),
    ):
        create_director_event(run_dir, payload)

    results = {r.event_id: r for r in resolve_director_events(run_dir)}
    events = {row["event_id"]: row for row in _read_jsonl(run_dir / "director" / "events.jsonl")}
    by_type = {events[event_id]["type"]: result for event_id, result in results.items()}

    rumor = by_type["rumor"].produced_inputs
    assert rumor[INPUT_KIND_PROMPT_CONTEXT]["intensity"] == 3
    assert rumor["rumor"] == {"visibility": "class", "targets": ["Lin"]}
    assert "prompt_context" in by_type["rumor"].explanation

    pressure = by_type["pressure"].produced_inputs
    assert pressure[INPUT_KIND_PROMPT_CONTEXT]["visibility"] == "targeted"
    assert pressure["pressure_context"] == {"targets": ["Lin"], "intensity": 1}

    incident = by_type["campus_incident"].produced_inputs
    assert incident[INPUT_KIND_PUBLIC_EVENT]["summary"] == "A campus_incident unfolds."
    assert incident[INPUT_KIND_PUBLIC_EVENT]["locations"] == ["classroom"]

    encounter = by_type["arranged_encounter"].produced_inputs
    assert encounter[INPUT_KIND_ENCOUNTER_CANDIDATE]["characters"] == ["Lin", "Mina"]
    assert encounter[INPUT_KIND_ENCOUNTER_CANDIDATE]["description"]
    assert all(r.status == "applied" for r in results.values())


def test_timing_must_be_a_world_time(tmp_path) -> None:
    run_dir = _make_world(tmp_path)

    with pytest.raises(DirectorValidationError, match="timing"):
        create_director_event(run_dir, _event("rumor", timing="whenever"))

    assert _read_jsonl(run_dir / "director" / "events.jsonl") == []


# Consumption --------------------------------------------------------------------


def test_active_inputs_follow_timing_duration_and_year_wrap(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    rumor = create_director_event(run_dir, _event("rumor", duration={"weeks": 2}))
    later = create_director_event(run_dir, _event("opportunity", timing="Y2020-W03-begin"))
    wrap = create_director_event(
        run_dir, _event("pressure", timing="Y2020-W10-begin", duration={"weeks": 2})
    )
    resolve_director_events(run_dir)

    def active(time: str) -> set[str]:
        return {
            item.event.event_id
            for item in load_active_director_inputs(run_dir, time=time, weeks_per_year=10)
        }

    assert active("Y2020-W00-begin") == set()
    assert active("Y2020-W01-plan") == {rumor.event_id}
    assert active("Y2020-W02-activity-D3") == {rumor.event_id}
    assert active("Y2020-W03-begin") == {later.event_id}
    assert active("Y2020-W10-begin") == {wrap.event_id}
    assert active("Y2021-W01-begin") == {wrap.event_id}
    assert active("Y2021-W02-begin") == set()


def test_pending_events_are_not_inputs_until_resolved(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    create_director_event(run_dir, _event("rumor"))

    assert load_active_director_inputs(run_dir, time="Y2020-W01-begin") == []
    resolve_director_events(run_dir)
    assert len(load_active_director_inputs(run_dir, time="Y2020-W01-begin")) == 1


def test_prompt_context_respects_visibility_and_names_the_event(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    create_director_event(
        run_dir,
        _event("rumor", intensity=3, description="A rumor spreads before morning reading."),
    )
    create_director_event(
        run_dir,
        _event("pressure", visibility="targeted", description="Exams are closing in."),
    )
    create_director_event(
        run_dir, _event("arranged_encounter", targets=["Lin", "Mina"], locations=["library"])
    )
    resolve_director_events(run_dir)
    inputs = load_active_director_inputs(run_dir, time="Y2020-W01-plan")

    lin = director_prompt_context(inputs, "Lin")
    mina = director_prompt_context(inputs, "Mina")

    assert lin == [
        "[Campus Rumor] A rumor spreads before morning reading. "
        "(involves: Lin; at: classroom; intensity: 3)",
        "[Pressure] Exams are closing in. (involves: Lin; at: classroom)",
    ]
    assert mina == [lin[0]]  # targeted pressure stays private; encounters are not context


def test_public_event_records_are_ready_for_sign_up(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    drill = create_director_event(
        run_dir,
        _event(
            "campus_incident",
            targets=[],
            locations=["playground"],
            duration={"weeks": 2},
            description="The whole school practices a fire drill.",
            metadata={"day": 3, "event_name": "Fire Drill"},
        ),
    )
    create_director_event(
        run_dir,
        _event(
            "campus_incident",
            targets=["Lin"],
            description="A burst pipe floods the corridor outside the classroom.",
        ),
    )
    resolve_director_events(run_dir)
    inputs = load_active_director_inputs(run_dir, time="Y2020-W01-before_contact")

    records = director_public_events(inputs, year=2020, week=1, n_days=5)

    assert records[0] == {
        "source_event_id": drill.event_id,
        "event_id": f"director-{drill.event_id}",
        "event_name": "Fire Drill",
        "start_year": 2020,
        "start_week": 1,
        "start_day": 3,
        "repeat_weeks": 2,
        "description": "The whole school practices a fire drill.",
        "eligible_participants": "all",
    }
    assert records[1]["event_name"].startswith("Campus Incident: A burst pipe")
    assert records[1]["start_day"] == 1
    assert records[1]["eligible_participants"] == "all"  # class-visible: anyone may join

    clamped = director_public_events(inputs, year=2020, week=1, n_days=2)
    assert clamped[0]["start_day"] == 2


def test_targeted_incident_is_offered_only_to_its_targets(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    create_director_event(
        run_dir,
        _event("campus_incident", targets=["Lin"], visibility="targeted"),
    )
    resolve_director_events(run_dir)
    inputs = load_active_director_inputs(run_dir, time="Y2020-W01-begin")

    (record,) = director_public_events(inputs, year=2020, week=1, n_days=5)

    assert record["eligible_participants"] == ["Lin"]


def test_arranged_encounters_respect_roster_conflicts_and_locations(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    fits = create_director_event(
        run_dir, _event("arranged_encounter", targets=["Mina", "Lin"], locations=["library"])
    )
    crowded = create_director_event(
        run_dir, _event("arranged_encounter", targets=["Lin", "Mina"], locations=["library"])
    )
    unknown = create_director_event(
        run_dir, _event("arranged_encounter", targets=["Lin", "Nobody"], locations=["library"])
    )
    nowhere = create_director_event(
        run_dir, _event("arranged_encounter", targets=["Lin", "Mina"], locations=["moon"])
    )
    resolve_director_events(run_dir)
    inputs = load_active_director_inputs(run_dir, time="Y2020-W01-after_contact")

    plans, skipped = plan_arranged_encounters(
        inputs,
        known_characters={"Lin", "Mina"},
        busy_days={"Lin": {1}, "Mina": {2}},
        valid_locations=["classroom", "library"],
        n_days=3,
    )

    assert [(p.event_id, p.participants, p.day, p.location) for p in plans] == [
        (fits.event_id, ("Lin", "Mina"), 3, "library")
    ]
    reasons = {item.event_id: item.reason for item in skipped}
    assert "all participants are free" in reasons[crowded.event_id]
    assert "at least two characters" in reasons[unknown.event_id]
    assert "no valid public location" in reasons[nowhere.event_id]


def test_applications_are_recorded_and_exposed_in_the_snapshot(tmp_path) -> None:
    run_dir = _make_world(tmp_path)

    row = record_director_application(
        run_dir,
        time=TimeState(2020, 1, Stage.PLAN),
        event_id="de-1",
        kind=INPUT_KIND_PROMPT_CONTEXT,
        status="applied",
        detail="added to the prompt context of 2 character(s)",
        characters=["Lin", "Mina"],
    )

    assert row["time"] == "Y2020-W01-plan"
    assert _read_jsonl(run_dir / "director" / "applications.jsonl") == [row]
    snapshot = generate_visualization_snapshot(run_dir)
    assert snapshot["director_applications"] == [row]


# Snapshot time --------------------------------------------------------------------


def test_snapshot_time_follows_the_simulation_not_the_schedule(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    snapshots = run_dir / "visualization" / "snapshots"

    assert infer_snapshot_time(run_dir) == "Y2020-W00-begin"
    generate_visualization_snapshot(run_dir)
    assert (snapshots / "Y2020-W00-begin.json").exists()

    create_director_event(run_dir, _event("rumor", timing="Y2020-W05-begin"))
    resolve_director_events(run_dir)
    assert infer_snapshot_time(run_dir) == "Y2020-W00-begin"

    (run_dir / "checkpoint.json").write_text(json.dumps({"year": 2020, "week": 3}))
    assert generate_visualization_snapshot(run_dir)["time"] == "Y2020-W03-settle"
    assert (snapshots / "Y2020-W03-settle.json").exists()

    with (run_dir / "persona" / "Lin" / "state.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"time": "Y2020-W04-plan", "content": {"vitality": 42}}) + "\n")
    snapshot = generate_visualization_snapshot(run_dir)
    assert snapshot["time"] == "Y2020-W04-plan"
    lin = next(c for c in snapshot["characters"] if c["name"] == "Lin")
    assert lin["status_highlights"]["vitality"] == 42

    explicit = generate_visualization_snapshot(run_dir, time="Y2020-W09-begin")
    assert explicit["time"] == "Y2020-W09-begin"
    assert (snapshots / "Y2020-W09-begin.json").exists()
    assert json.loads((run_dir / "visualization" / "current.json").read_text())["time"] == (
        "Y2020-W09-begin"
    )


# Character entry ------------------------------------------------------------------


def test_service_refreshes_the_active_roster_only_at_a_safe_boundary(tmp_path) -> None:
    service = DirectorWorldService(data_root=tmp_path / "data")
    run_dir = service.create_world(
        "school-classroom",
        {
            "world": {"class_name": "Class 2-3", "school_name": "North High"},
            "characters": [_character("Lin")],
        },
        run_id="01010000",
    )

    world = FakeActiveWorld(TimeState(2020, 3, Stage.BEGIN))
    entry = service.add_character(
        run_dir,
        {"join_mode": "transfer_student", "character": _character("Mina")},
        active_world=world,
    )

    assert world.added == ["Mina"]
    assert entry.inserted_stage == "BEGIN"
    events = {row["event_id"]: row for row in _read_jsonl(run_dir / "director" / "events.jsonl")}
    assert events[entry.arrival_event_id]["timing"] == "Y2020-W03-begin"
    # The arrival is timed when she joins; her seed records keep the template start so
    # a resume from an earlier week cannot trim them away.
    first_state = _read_jsonl(run_dir / "persona" / "Mina" / "state.jsonl")[0]
    assert first_state["time"] == "Y2020-W00-begin"
    assert first_state["content"]["assets"] == {"deposit": 0, "possessions": []}
    assert json.loads((run_dir / "visualization" / "current.json").read_text())["time"] == (
        "Y2020-W03-begin"
    )

    busy = FakeActiveWorld(TimeState(2020, 3, Stage.ACTIVITY, day=2))
    with pytest.raises(CharacterEntryError, match="ACTIVITY"):
        service.add_character(
            run_dir,
            {"join_mode": "transfer_student", "character": _character("Kai")},
            active_world=busy,
        )
    assert busy.added == []
    assert not (run_dir / "persona" / "Kai").exists()
    assert len(_read_jsonl(run_dir / "director" / "events.jsonl")) == 1


def test_join_mode_decides_home_and_starting_location(tmp_path) -> None:
    run_dir = _make_world(tmp_path, names=("Lin",))

    guest = add_character_to_world(
        run_dir, {"join_mode": "club_guest", "character": _character("Kai")}
    )
    transfer = add_character_to_world(
        run_dir, {"join_mode": "transfer_student", "character": _character("Mina")}
    )

    locations = json.loads((run_dir / "locations.json").read_text(encoding="utf-8"))
    assert "home/Kai" not in locations["private"]
    assert "home/Mina" in locations["private"]
    events = {row["event_id"]: row for row in _read_jsonl(run_dir / "director" / "events.jsonl")}
    assert events[guest.arrival_event_id]["locations"] == ["club_room"]
    assert events[transfer.arrival_event_id]["locations"] == ["classroom"]
    assert events[guest.arrival_event_id]["timing"] == "Y2020-W00-begin"


def test_pending_arrivals_start_at_their_week_and_skip_known_characters(tmp_path) -> None:
    run_dir = _make_world(tmp_path, names=("Lin",))
    early = add_character_to_world(
        run_dir, {"join_mode": "transfer_student", "character": _character("Mina")}
    )
    late = add_character_to_world(
        run_dir,
        {"join_mode": "transfer_student", "character": _character("Kai")},
        active_world=FakeActiveWorld(TimeState(2020, 5, Stage.BEGIN)),
    )
    resolve_director_events(run_dir)

    def arrivals(time: str, known: set[str]) -> list[str]:
        return pending_arrivals(run_dir, time=time, known_characters=known)

    assert early.arrival_event_id != late.arrival_event_id
    assert arrivals("Y2020-W01-begin", {"Lin"}) == ["Mina"]
    assert arrivals("Y2020-W04-begin", {"Lin"}) == ["Mina"]
    assert arrivals("Y2020-W05-begin", {"Lin"}) == ["Mina", "Kai"]
    assert arrivals("Y2020-W07-plan", {"Lin", "Mina"}) == ["Kai"]
    assert arrivals("Y2020-W07-plan", {"Lin", "Mina", "Kai"}) == []


def test_pending_arrivals_ignore_unresolved_events_and_runs_without_director_data(
    tmp_path,
) -> None:
    run_dir = _make_world(tmp_path, names=("Lin",))
    assert pending_arrivals(run_dir, time="Y2020-W01-begin", known_characters=set()) == []

    create_director_event(run_dir, _event("arrival", targets=["Mina"]))
    assert pending_arrivals(run_dir, time="Y2020-W01-begin", known_characters=set()) == []


# Contract details --------------------------------------------------------------------


def _active_ids(run_dir: Path, time: str, **kwargs) -> set[str]:
    return {
        item.event.event_id
        for item in load_active_director_inputs(run_dir, time=time, **kwargs)
    }


def test_only_the_latest_applied_result_counts(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    kept = create_director_event(run_dir, _event("rumor"))
    withdrawn = create_director_event(run_dir, _event("opportunity"))
    resolve_director_events(run_dir)
    with (run_dir / "director" / "results.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "event_id": withdrawn.event_id,
                    "status": "rejected",
                    "explanation": "withdrawn",
                    "affected_characters": [],
                    "affected_locations": [],
                    "produced_inputs": {},
                }
            )
            + "\n"
        )

    assert _active_ids(run_dir, "Y2020-W01-begin") == {kept.event_id}


def test_zero_or_malformed_duration_still_lasts_one_week(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    zero = create_director_event(run_dir, _event("rumor", duration={"weeks": 0}))
    junk = create_director_event(run_dir, _event("pressure", duration={"weeks": "soon"}))
    resolve_director_events(run_dir)

    assert _active_ids(run_dir, "Y2020-W01-begin") == {zero.event_id, junk.event_id}
    assert _active_ids(run_dir, "Y2020-W02-begin") == set()


def test_default_weeks_per_year_applies_without_a_template_value(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    wrap = create_director_event(
        run_dir,
        _event("rumor", timing=f"Y2020-W{DEFAULT_WEEKS_PER_YEAR:02d}-begin", duration={"weeks": 2}),
    )
    resolve_director_events(run_dir)

    assert _active_ids(run_dir, "Y2021-W01-begin") == {wrap.event_id}
    assert _active_ids(run_dir, "Y2021-W02-begin") == set()


def test_private_and_personal_visibility_hide_context_from_others(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    for visibility in ("private", "personal"):
        create_director_event(
            run_dir, _event("pressure", visibility=visibility, description=f"{visibility} note")
        )
    resolve_director_events(run_dir)
    inputs = load_active_director_inputs(run_dir, time="Y2020-W01-begin")

    assert len(director_prompt_context(inputs, "Lin")) == 2
    assert director_prompt_context(inputs, "Mina") == []


def test_same_named_incidents_get_distinct_sign_up_names(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    for _ in range(2):
        create_director_event(
            run_dir, _event("campus_incident", targets=[], description="The bell rings early.")
        )
    resolve_director_events(run_dir)
    inputs = load_active_director_inputs(run_dir, time="Y2020-W01-begin")

    names = [r["event_name"].lower() for r in director_public_events(inputs, year=2020, week=1)]

    assert len(names) == 2 and len(set(names)) == 2


def test_an_encounter_never_pairs_a_character_with_herself(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    create_director_event(
        run_dir, _event("arranged_encounter", targets=["Lin", "Lin"], locations=["library"])
    )
    resolve_director_events(run_dir)
    inputs = load_active_director_inputs(run_dir, time="Y2020-W01-begin")

    plans, skipped = plan_arranged_encounters(
        inputs,
        known_characters={"Lin", "Mina"},
        busy_days={},
        valid_locations=["library"],
        n_days=5,
    )

    assert plans == []
    assert "at least two characters" in skipped[0].reason


def test_unreadable_stored_timing_is_skipped_not_fatal(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    good = create_director_event(run_dir, _event("rumor"))
    bad = create_director_event(run_dir, _event("opportunity"))
    resolve_director_events(run_dir)
    # Simulate an event stored before timing was validated.
    events_path = run_dir / "director" / "events.jsonl"
    rows = _read_jsonl(events_path)
    for row in rows:
        if row["event_id"] == bad.event_id:
            row["timing"] = "whenever"
    events_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    assert _active_ids(run_dir, "Y2020-W01-begin") == {good.event_id}
    assert pending_arrivals(run_dir, time="Y2020-W01-begin", known_characters=set()) == []


def test_arrival_from_an_event_that_was_never_resolved_is_ignored(tmp_path) -> None:
    run_dir = _make_world(tmp_path, names=("Lin",))
    create_director_event(run_dir, _event("arrival", targets=["Mina"], timing="Y2020-W00-begin"))
    resolve_director_events(run_dir)
    create_director_event(run_dir, _event("arrival", targets=["Kai"], timing="Y2020-W00-begin"))

    arrivals = pending_arrivals(run_dir, time="Y2020-W01-begin", known_characters={"Lin"})

    assert arrivals == ["Mina"]


# Character entry ----------------------------------------------------------------------


def test_entry_records_use_the_template_start_and_the_profile_uses_the_joining_year(
    tmp_path,
) -> None:
    run_dir = _make_world(tmp_path, names=("Lin",))

    add_character_to_world(
        run_dir,
        {
            "join_mode": "transfer_student",
            "character": _character("Kai"),
            "arrival_context": "Arrives before homeroom.",
            "known_character_hints": [{"name": "Lin", "context": "Met at admissions."}],
        },
        active_world=FakeActiveWorld(TimeState(2021, 3, Stage.BEGIN)),
    )

    persona = run_dir / "persona" / "Kai"
    assert (persona / "profile" / "year=2021.json").exists()
    assert not (persona / "profile" / "year=2020.json").exists()
    scratchpads = [
        persona / "memory" / "scratchpad" / "general.jsonl",
        persona / "memory" / "scratchpad" / "characters" / "Lin.jsonl",
        persona / "state.jsonl",
    ]
    for path in scratchpads:
        assert {row["time"] for row in _read_jsonl(path)} == {"Y2020-W00-begin"}, path
    arrival = _read_jsonl(run_dir / "director" / "events.jsonl")[0]
    assert arrival["timing"] == "Y2021-W03-begin"


def test_explicit_stage_and_request_location_take_precedence(tmp_path) -> None:
    run_dir = _make_world(tmp_path, names=("Lin",))
    world = FakeActiveWorld(TimeState(2020, 2, Stage.BEGIN))

    with pytest.raises(CharacterEntryError, match="PLAN"):
        add_character_to_world(
            run_dir,
            {"join_mode": "transfer_student", "character": _character("Kai")},
            current_stage="PLAN",
            active_world=world,
        )
    entry = add_character_to_world(
        run_dir,
        {
            "join_mode": "club_guest",
            "character": _character("Mina"),
            "starting_location": "library",
        },
        active_world=world,
    )

    events = {row["event_id"]: row for row in _read_jsonl(run_dir / "director" / "events.jsonl")}
    assert events[entry.arrival_event_id]["locations"] == ["library"]
    assert world.added == ["Mina"]


# Read model -----------------------------------------------------------------------------


def test_relationship_summaries_publish_the_summary_not_the_private_note(tmp_path) -> None:
    run_dir = _make_world(tmp_path)
    pads = run_dir / "persona" / "Lin" / "memory" / "scratchpad" / "characters"
    (pads / "Mina.jsonl").write_text(
        json.dumps(
            {
                "time": "Y2020-W01-plan",
                "summary": "Mina is friendly.",
                "content": "PRIVATE FULL NOTE: I suspect Mina started the rumor.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (pads / "Kai.jsonl").write_text(
        json.dumps({"time": "Y2020-W00-begin", "content": "x" * 900}) + "\n",
        encoding="utf-8",
    )

    snapshot = generate_visualization_snapshot(run_dir)

    summaries = {r["target"]: r["summary"] for r in snapshot["relationships"]}
    assert summaries["Mina"] == "Mina is friendly."
    assert "PRIVATE" not in json.dumps(snapshot)
    assert len(summaries["Kai"]) == 500 and summaries["Kai"].endswith("…")
