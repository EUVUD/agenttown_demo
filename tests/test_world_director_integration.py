"""World-level integration for director-world runs.

Each scenario runs in a fresh interpreter whose working directory is a temporary
copy of the data tree, because importing the legacy engine loads configuration
and creates ``logs/``. No model is called: model-calling methods are replaced by
recorders, and everything between them is the real code.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.support.fresh_interpreter import PROJECT_ROOT, run_in_fresh_interpreter

PRELUDE = r'''
import json
import logging
import shutil
from pathlib import Path

from src.config import get_world_config, load_config

load_config(Path(sys.path[0]) / "config.example.json")

from src.agents.role_agent import RoleAgent
from src.world.cleanup import clean_append_only_jsonl_before
from src.world.clock import Clock, Stage, TimeState
from src.world.director import create_director_event, resolve_director_events
from src.world.director_service import DirectorWorldService
from src.world.locations import get_location_store
from src.world.scheduling import MessageCenter
from src.world.template_world import add_character_to_world
from src.world.world import World


def character(name, role="student"):
    return {
        "name": name, "role": role, "gender": "female",
        "brief_introduction": f"{name} is new here.",
        "appearance_and_impression": "Short hair.", "personality": "Careful.",
        "motivation": "Settle in.",
    }


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l]


def make_world(run_dir, roster, *, year=2020, week=1):
    """A World shell: real helpers and agents, no model-calling construction."""
    world_name = run_dir.name
    clock = Clock(start_year=2020, start_week=0)
    clock.set_year(year)
    clock.set_week(week)
    msg_center = MessageCenter(world_name=world_name, clock=clock)
    w = World.__new__(World)
    w.clock = clock
    w.config = get_world_config()
    w.data_dir = world_name
    w.logger = logging.getLogger("integration")
    w.msg_center = msg_center
    w.location_store = get_location_store(world_name)
    w.no_context_engineering = False
    w.no_history = False
    w.parallel = False
    w._role_models = ["stub-model"]
    w.agents = [
        RoleAgent(n, clock=clock, msg_center=msg_center, model="stub-model", world_name=world_name)
        for n in roster
    ]
    w._name2agent = {a.name: a for a in w.agents}
    w._director_run_dir = w._detect_director_run_dir()
    w._director_inputs = []
    return w


def make_run(service, names=("Lin", "Mina")):
    run_dir = service.create_world(
        "school-classroom",
        {"world": {"class_name": "Class 2-3", "school_name": "North High"},
         "characters": [character(n) for n in names]},
        run_id="01010000",
    )
    base = {"timing": "Y2020-W01-begin", "intensity": 2, "duration": {"weeks": 1}}
    service.submit_director_event(run_dir, {**base, "type": "rumor", "targets": ["Lin"],
        "visibility": "class", "locations": ["classroom"], "description": "A rumor about Lin spreads."})
    service.submit_director_event(run_dir, {**base, "type": "pressure", "targets": ["Mina"],
        "visibility": "targeted", "locations": [], "description": "Mina's parents demand top marks."})
    service.submit_director_event(run_dir, {**base, "type": "arranged_encounter",
        "targets": ["Lin", "Mina"], "locations": ["library"], "description": "They reach for the same book."})
    service.submit_director_event(run_dir, {**base, "type": "campus_incident", "targets": [],
        "locations": ["playground"], "description": "A surprise fire drill empties the building.",
        "metadata": {"day": 2, "event_name": "Fire Drill"}})
    return run_dir
'''

WEEKLY_FLOW = r'''
service = DirectorWorldService()
run_dir = make_run(service)
# Another process adds Kai: persona files plus an arrival event, no live World handle.
service.add_character(run_dir, {"join_mode": "transfer_student", "character": character("Kai")})

w = make_world(run_dir, ["Lin", "Mina"])
assert w._director_run_dir == run_dir, w._director_run_dir

# --- week 1 begins: the newcomer is admitted before planning ------------------------
w._sync_director_roster()
assert sorted(w._name2agent) == ["Kai", "Lin", "Mina"], sorted(w._name2agent)
assert [a.name for a in w.agents] == ["Lin", "Mina", "Kai"]
assert json.loads((run_dir / "model_assignment.json").read_text())["Kai"] == "stub-model"
w._sync_director_roster()
assert len(w.agents) == 3, "roster sync must be idempotent"

w._load_director_inputs()
assert len(w._director_inputs) == 4, w._director_inputs
w._apply_director_prompt_context()
prompts = {n: a.dm.roleplay_prompt()[0]["content"] for n, a in w._name2agent.items()}
assert "A rumor about Lin spreads." in prompts["Lin"] and "top marks" not in prompts["Lin"]
assert "A rumor about Lin spreads." in prompts["Mina"] and "top marks" in prompts["Mina"]
assert "A rumor about Lin spreads." in prompts["Kai"] and "top marks" not in prompts["Kai"]
w._name2agent["Lin"].clear_on_week_start()
assert "World Developments" not in w._name2agent["Lin"].dm.roleplay_prompt()[0]["content"]

w.clock.set_stage(Stage.BEFORE_CONTACT)
public = w._director_public_events()
assert [(e.event_name, e.start_day) for e in public] == [("Fire Drill", 2)], public

w.clock.set_stage(Stage.AFTER_CONTACT)
w._schedule_director_encounters()
schedule = w._name2agent["Lin"].dm.get_schedule_for_day(2020, 1, 1)
assert schedule is not None and schedule.type == "encounter" and schedule.location == "library"
assert w._name2agent["Mina"].dm.get_schedule_for_day(2020, 1, 1).activity_id == schedule.activity_id

w.clock.set_stage(Stage.SETTLE)
w._write_director_snapshot()
snapshot = json.loads((run_dir / "visualization" / "current.json").read_text())
assert snapshot["time"] == "Y2020-W01-settle", snapshot["time"]
assert (run_dir / "visualization" / "snapshots" / "Y2020-W01-settle.json").exists()
kinds = sorted({row["kind"] for row in snapshot["director_applications"]})
assert kinds == ["encounter_candidate", "prompt_context", "public_event"], kinds
assert {c["name"] for c in snapshot["characters"]} == {"Kai", "Lin", "Mina"}

# --- resume: director inputs survive, this week's applications are redone ----------
before = {
    name: (run_dir / name).read_text()
    for name in ("director/events.jsonl", "director/results.jsonl", "visualization/timeline.jsonl")
}
clean_append_only_jsonl_before(world_name=run_dir.name, start_time=TimeState(2020, 1, Stage.BEGIN))
for name, text in before.items():
    assert (run_dir / name).read_text() == text, name
assert not (run_dir / "director" / "applications.jsonl").exists(), "week-1 applications should be trimmed"

# --- a newcomer joining later keeps her seed records through a resume ---------------
w.clock.set_week(3)
w.position_store = __import__("src.world.position_application", fromlist=["x"]).get_position_store(run_dir.name)
entry = service.add_character(
    run_dir,
    {"join_mode": "transfer_student", "character": character("Zoe"),
     "arrival_context": "Arrives before homeroom.",
     "known_character_hints": [{"name": "Lin", "context": "Met at admissions."}]},
    active_world=w,
)
assert "Zoe" in w._name2agent and entry.inserted_stage == "BEGIN"
# The map was loaded before she joined; her new home must now be a valid place.
assert w.location_store.is_valid("home/Zoe")
assert json.loads((run_dir / "model_assignment.json").read_text())["Zoe"] == "stub-model"
positions = {p["name"]: p for p in json.loads((run_dir / "positions.json").read_text())["positions"]}
assert "Zoe" in positions["School classroom/student"]["occupied_by"], positions
clean_append_only_jsonl_before(world_name=run_dir.name, start_time=TimeState(2020, 2, Stage.BEGIN))
persona = run_dir / "persona" / "Zoe"
assert read_jsonl(persona / "state.jsonl")[0]["content"]["assets"]["deposit"] == 0
assert read_jsonl(persona / "memory" / "scratchpad" / "general.jsonl")
assert read_jsonl(persona / "memory" / "scratchpad" / "characters" / "Lin.jsonl")
assert w._name2agent["Zoe"].dm.read_state()["vitality"] == 80

# --- a newcomer in the next year reads her own year's profile -----------------------
w.clock.set_year(2021)
w.clock.set_week(1)
service.add_character(run_dir, {"join_mode": "transfer_student", "character": character("Mia")}, active_world=w)
assert (run_dir / "persona" / "Mia" / "profile" / "year=2021.json").exists()
assert w._name2agent["Mia"].dm.read_profile()["name"] == "Mia"
assert w._name2agent["Mia"].dm.read_state()["assets"]["deposit"] == 0
assert json.loads((run_dir / "visualization" / "current.json").read_text())["time"] == "Y2021-W01-begin"

# --- a restart after a cross-process add assigns a model instead of failing -----------
add_character_to_world(run_dir, {"join_mode": "transfer_student", "character": character("Ned")})
assignment = w._load_or_assign_models(["Lin", "Mina", "Kai", "Zoe", "Mia", "Ned"])
assert assignment["Ned"] == "stub-model"
assert json.loads((run_dir / "model_assignment.json").read_text())["Ned"] == "stub-model"

# --- unsafe boundary: no roster change mid-week -------------------------------------
w.clock.set_stage(Stage.ACTIVITY)
try:
    w.add_agent_from_data("Ned")
except RuntimeError as exc:
    assert "ACTIVITY" in str(exc), exc
else:
    raise AssertionError("add_agent_from_data must refuse mid-week insertion")
assert "Ned" not in w._name2agent

print("SCENARIO OK")
'''

STEP_DRIVES_HOOKS = r'''
import src.world.god as god

service = DirectorWorldService()
run_dir = make_run(service)
service.add_character(run_dir, {"join_mode": "transfer_student", "character": character("Kai")})
w = make_world(run_dir, ["Lin", "Mina"])
w.clock.set_week(1)

plan_seen, signup_seen, god_calls = {}, {}, []
w._before_week_start = lambda: None
w._build_today_activities_all_types = lambda: ([], [], [], [])
god.generate_public_events = lambda **kw: god_calls.append(kw) or []
god.god_generate_encounter_events = lambda **kw: []
# Agents are created by the roster sync, so stub the class methods.
for name in ("plan", "contact", "finalize_contact", "review", "settle_week"):
    setattr(RoleAgent, name, lambda self, *a, **k: None)
RoleAgent.plan = lambda self: plan_seen.setdefault(self.name, list(self.dm.world_context))
RoleAgent.signup_public_events = lambda self, events: signup_seen.setdefault(self.name, [e.event_name for e in events]) and []

w.step()

assert sorted(plan_seen) == ["Kai", "Lin", "Mina"], plan_seen  # newcomer admitted before PLAN
assert any("A rumor about Lin spreads." in line for line in plan_seen["Kai"]), plan_seen["Kai"]
assert any("top marks" in line for line in plan_seen["Mina"]) and not any("top marks" in l for l in plan_seen["Lin"])
assert all("Fire Drill" in names for names in signup_seen.values()) and len(signup_seen) == 3, signup_seen
(call,) = god_calls
assert "fire drill" in call["existing_event_names"] and "Fire Drill" in call["previous_events"], call
lin_schedule = w._name2agent["Lin"].dm.get_schedule_for_day(2020, 1, 1)
assert lin_schedule is not None and lin_schedule.type == "encounter" and lin_schedule.location == "library"
snapshot = json.loads((run_dir / "visualization" / "current.json").read_text())
assert snapshot["time"] == "Y2020-W01-settle", snapshot["time"]
assert {r["kind"] for r in snapshot["director_applications"]} == {"encounter_candidate", "prompt_context", "public_event"}

# A second week clears last week's context and keeps the roster stable.
w.clock.set_week(2)
plan_seen.clear()
w.step()
assert sorted(plan_seen) == ["Kai", "Lin", "Mina"] and all(lines == [] for lines in plan_seen.values()), plan_seen
print("SCENARIO OK")
'''

ROSTER_EDGE_CASES = r'''
service = DirectorWorldService()
run_dir = service.create_world(
    "school-classroom",
    {"world": {"class_name": "Class 2-3", "school_name": "North High"},
     "characters": [character("Lin"), character("Mina")]},
    run_id="01010000",
)
# Mina has persona files but is not on the roster (as if a cap excluded her) and no
# arrival event names her. Kai joined properly. Ghost has an arrival but no files.
# Halfway has an arrival but lost her profile. Zed's arrival was never resolved.
service.add_character(run_dir, {"join_mode": "transfer_student", "character": character("Kai")})
create_director_event(run_dir, {"type": "arrival", "timing": "Y2020-W00-begin", "targets": ["Ghost"],
                                "locations": ["classroom"], "description": "Ghost joins."})
service.add_character(run_dir, {"join_mode": "transfer_student", "character": character("Halfway")})
shutil.rmtree(run_dir / "persona" / "Halfway" / "profile")
add_character_to_world(run_dir, {"join_mode": "transfer_student", "character": character("Zed")})

w = make_world(run_dir, ["Lin"])
w._sync_director_roster()

assert sorted(w._name2agent) == ["Kai", "Lin", "Zed"], sorted(w._name2agent)
assert "Mina" not in w._name2agent
results = {r["event_id"] for r in read_jsonl(run_dir / "director" / "results.jsonl")}
assert len(results) == 4, "the sync must resolve pending events"
print("SCENARIO OK")
'''

LEGACY_RUN_UNTOUCHED = r'''
# A legacy run directory has persona files but no template_meta.json.
run_dir = Path("data") / "school_01010000"
legacy_name = "丛雪薇"
shutil.copytree(
    Path(sys.path[0]) / "data" / "school" / "persona" / legacy_name,
    run_dir / "persona" / legacy_name,
)
(run_dir / "model_assignment.json").write_text(json.dumps({legacy_name: "m"}), encoding="utf-8")

def tree():
    return sorted(str(p) for p in run_dir.rglob("*"))

w = make_world(run_dir, [])
w._role_models = ["m"]
before = tree()
assert w._director_run_dir is None

w._sync_director_roster()
w._load_director_inputs()
w._apply_director_prompt_context()
assert w._director_public_events() == []
w._schedule_director_encounters()
w._write_director_snapshot()
assert tree() == before, sorted(set(tree()) ^ set(before))
assert w._director_inputs == []

# The roster check on restart stays strict for legacy runs.
try:
    w._load_or_assign_models([legacy_name, "Bob"])
except ValueError as exc:
    assert "Bob" in str(exc), exc
else:
    raise AssertionError("legacy runs must keep rejecting an incomplete model assignment")
assert json.loads((run_dir / "model_assignment.json").read_text()) == {legacy_name: "m"}

# Legacy prompts carry no trace of the director section.
agent = RoleAgent(legacy_name, clock=w.clock, msg_center=w.msg_center, model="m", world_name=run_dir.name)
assert "World Developments" not in agent.dm.roleplay_prompt()[0]["content"]
print("SCENARIO OK")
'''


def _run(scenario: str, tmp_path: Path) -> None:
    shutil.copytree(
        PROJECT_ROOT / "data" / "world_templates",
        tmp_path / "data" / "world_templates",
    )

    completed = run_in_fresh_interpreter(PRELUDE + scenario, cwd=tmp_path)

    assert completed.returncode == 0 and "SCENARIO OK" in completed.stdout, (
        f"stdout:\n{completed.stdout[-2000:]}\nstderr:\n{completed.stderr[-4000:]}"
    )


@pytest.mark.parametrize(
    "scenario",
    [WEEKLY_FLOW, STEP_DRIVES_HOOKS, ROSTER_EDGE_CASES, LEGACY_RUN_UNTOUCHED],
    ids=["weekly-flow", "step-drives-hooks", "roster-edge-cases", "legacy-run-untouched"],
)
def test_director_run_scenarios(scenario: str, tmp_path: Path) -> None:
    _run(scenario, tmp_path)
