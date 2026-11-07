"""Game rules for the Marginalia prototype.

The player never edits world state. Chat can only leave a pending influence on the
protagonist; her own slot decisions adopt, decline or defer it, and every change
records the influences and events that caused it. Callers must serialize writes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Callable, Mapping

from prototype import boundary, prompts
from prototype.llm import InvalidModelOutput, LLMRequest, Provider, complete_json
from prototype.store import Store, new_id

BLUEPRINT_PATH = Path(__file__).with_name("world.json")
MAX_CATCH_UP_DAYS = 7
MAX_RELATIONSHIP_DELTA = 10
MAX_MEMORIES = 40
MAX_DIARIES = 14
SUPPORTED_BLUEPRINT_VERSIONS = (1,)
CHAT_FALLBACK_REPLY = "……（她盯着屏幕看了很久，最后什么也没回。）"
DIARY_FALLBACK = "今天没什么特别的。"
LETTER_FALLBACK = {"title": "你回来了", "body": "好久不见。这几天的事，一时不知道从哪说起……不过你回来了就好。"}
DECISIONS = ("adopted", "declined", "deferred")
OPEN_INFLUENCE = ("pending", "deferred")
STORY_EVENT_KINDS = ("scene", "offscreen_day", "day_review")


class NotFound(LookupError):
    """The requested world or letter does not exist."""


@dataclass(frozen=True)
class WorldBlueprint:
    """One world's own copy of the blueprint, with the lookups the rules need.

    A world keeps the blueprint it was created from, so editing `world.json`
    later changes new worlds only.
    """

    data: Mapping[str, Any]
    npcs: Mapping[str, Mapping[str, Any]]
    locations: Mapping[str, Mapping[str, Any]]

    @classmethod
    def of(cls, data: Mapping[str, Any]) -> WorldBlueprint:
        data = dict(data)
        return cls(
            data=data,
            npcs={npc["id"]: npc for npc in data["npcs"]},
            locations={loc["id"]: loc for loc in data["locations"]},
        )

    @property
    def slot_count(self) -> int:
        return len(self.data["slots"])

    def slot_label(self, slot: int) -> str:
        return self.data["slots"][slot - 1]["label"]


def load_blueprint(path: str | Path = BLUEPRINT_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def local_now() -> datetime:
    return datetime.now().astimezone()


class Game:
    def __init__(
        self,
        db_path: str | Path,
        provider: Provider,
        blueprint: Mapping[str, Any] | None = None,
        *,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.db_path = Path(db_path)
        self.provider = provider
        self.blueprint = dict(blueprint or load_blueprint())
        self.clock = clock
        _require_supported(self.blueprint)
        self._current = WorldBlueprint.of(self.blueprint)  # used for new worlds only
        self._blueprints: dict[str, WorldBlueprint] = {}
        with self._store() as store:
            store.migrate()

    # World lifecycle -----------------------------------------------------------

    def current_world(self) -> str:
        with self._store() as store:
            world_id = store.latest_world_id()
        return world_id or self.new_world()

    def new_world(self) -> str:
        now = self.clock()
        world_id = new_id("world")
        bp = self._current
        with self._store() as store, store.tx():
            store.create_world(world_id, bp.data, self._initial_state(bp, now), now)
            store.append_event(
                world_id,
                day=1,
                slot=1,
                kind="world_start",
                title="新学期开始",
                summary=bp.data["world"]["setting"],
                payload={},
                causes=[],
                now=now,
            )
        self._blueprints[world_id] = bp
        return world_id

    # Sessions and offline catch-up ---------------------------------------------

    def open_session(self, world_id: str) -> dict:
        """Catch up on real days missed since the last visit (one game day per real day).

        Catch-up is resumable. Its plan is stored in the world state before the first
        model call and updated in the same transaction as every day it commits, so a
        provider error part way through leaves a plan that the next call finishes
        instead of simulating the absence again.
        """
        self._bp(world_id)  # fail on an unreadable world before anything is written
        now = self.clock()
        report: dict[str, Any] = {"days_away": 0, "simulated_days": 0, "slept": False, "letter_id": None}
        while True:
            state = self._load_state(world_id)
            plan = state.get("catch_up")
            if plan is None:
                last_seen = _aware(datetime.fromisoformat(state["last_seen_at"])).astimezone(now.tzinfo)
                days_away = max((now.date() - last_seen.date()).days, 0)
                if not days_away:
                    break
                plan = self._begin_catch_up(world_id, state, days_away, now)
            part = self._run_catch_up(world_id)
            if "catch_up" in self._load_state(world_id):
                raise RuntimeError("catch-up did not finish; refusing to repeat it")
            report["days_away"] += part["days_away"]
            report["simulated_days"] += part["simulated_days"]
            report["slept"] = report["slept"] or part["slept"]
            report["letter_id"] = part["letter_id"]
            report["event_ids"] = [*report.get("event_ids", []), *part["event_ids"]]
        self._touch(world_id, now)
        return report

    def simulate_absence(self, world_id: str, days: int) -> dict:
        """Developer shortcut: pretend the player left `days` real days ago."""
        if not 1 <= days <= 30:
            raise ValueError("days must be between 1 and 30")
        self._bp(world_id)
        if "catch_up" in self._load_state(world_id):
            self.open_session(world_id)  # a pending catch-up is finished first, never skipped
        state = self._load_state(world_id)
        state["last_seen_at"] = (self.clock() - timedelta(days=days)).isoformat()
        with self._store() as store, store.tx():
            store.save_state(world_id, state)
        return self.open_session(world_id)

    # Commands ------------------------------------------------------------------

    def send_message(self, world_id: str, text: str, client_id: str | None = None) -> dict:
        text = text.strip()
        if not text:
            raise ValueError("message is empty")
        if len(text) > 500:
            raise ValueError("message is longer than 500 characters")
        with self._store() as store:
            if client_id:
                existing = store.find_message_by_client_id(world_id, client_id)
                if existing is not None:
                    reply = store.find_reply(existing["id"])
                    return {
                        "message_id": existing["id"],
                        "reply": {"id": reply["id"], "text": reply["text"]} if reply else None,
                        "influence": None,
                        "deduplicated": True,
                    }
            history = store.recent_messages(world_id, 12)
        state = self._load_state(world_id)
        bp = self._bp(world_id)
        hero = state["protagonist"]
        request = LLMRequest(
            task="chat",
            system=prompts.protagonist_system(bp.data),
            prompt=prompts.chat_prompt(bp.data, state, history, text),
            context={
                "text": text,
                "npcs": [{"id": npc["id"], "name": npc["name"]} for npc in bp.data["npcs"]],
                "location_name": bp.locations[hero["location"]]["name"],
            },
            max_tokens=800,
        )
        try:
            out, meta = complete_json(
                self.provider, request, partial(self._validate_chat, bp), salvage=self._salvage_chat
            )
        except InvalidModelOutput as exc:
            out = {"reply": CHAT_FALLBACK_REPLY, "influence": None}
            meta = {"fallback": True, "error": str(exc)}
        screen = boundary.Screen.for_state(bp.npcs, state)
        out = dict(out)
        if screen.check(out["reply"], "reply") is None:
            out["reply"] = CHAT_FALLBACK_REPLY
        if out.get("mood") and screen.check(out["mood"], "mood") is None:
            del out["mood"]
        if out["influence"] and screen.check(out["influence"]["text"], "influence") is None:
            out["influence"] = None
        if blocked := screen.drain():
            meta = {**meta, "leak_blocked": blocked}

        now = self.clock()
        day, slot = state["day"], state["slot"]
        influence = None
        with self._store() as store, store.tx():
            message_id = store.add_message(
                world_id, role="player", text=text, day=day, slot=slot, now=now, client_id=client_id
            )
            reply_id = store.add_message(
                world_id,
                role="protagonist",
                text=out["reply"],
                day=day,
                slot=slot,
                now=now,
                reply_to=message_id,
                meta=meta,
            )
            if out["influence"]:
                influence = {
                    "id": new_id("inf"),
                    **out["influence"],
                    "status": "pending",
                    "reason": "",
                    "message_id": message_id,
                    "day": day,
                    "slot": slot,
                    "resolved_event_id": None,
                }
                state["influences"].append(influence)
            if out.get("mood"):
                hero["mood"] = out["mood"]
            state["last_seen_at"] = now.isoformat()
            store.save_state(world_id, state)
        return {
            "message_id": message_id,
            "reply": {"id": reply_id, "text": out["reply"]},
            "influence": influence,
            "deduplicated": False,
        }

    def advance_slot(self, world_id: str) -> dict:
        """Resolve the current slot; the last slot of a day also reviews the day."""
        state = self._load_state(world_id)
        bp = self._bp(world_id)
        day, slot = state["day"], state["slot"]
        with self._store() as store:
            recent = store.list_events(world_id, limit=6, kinds=STORY_EVENT_KINDS)
            earlier_scenes = store.events_for_day(world_id, day, "scene")
            chat_count = store.count_messages(world_id, day=day, role="player")

        request = LLMRequest(
            task="slot",
            system=prompts.narrator_system(bp.data),
            prompt=prompts.slot_prompt(bp.data, state, recent),
            context=self._fake_context(bp, state),
        )
        try:
            out, meta = complete_json(self.provider, request, partial(self._validate_slot, bp))
        except InvalidModelOutput as exc:
            out, meta = self._fallback_slot(bp, state), {"fallback": True, "error": str(exc)}
        screen, discoveries = boundary.Screen.for_output(bp.npcs, state, out["discoveries"])
        out = self._screen_effects(screen, out, discoveries)
        if blocked := screen.drain():
            meta = {**meta, "leak_blocked": blocked}

        review = None
        if slot == bp.slot_count:
            scenes = [self._scene_view(bp, e) for e in earlier_scenes]
            scenes.append({"slot_label": bp.slot_label(slot), "title": out["title"], "summary": out["scene"]})
            review = self._review_day(bp, state, scenes, chat_count, screen)

        now = self.clock()
        letter_id = None
        with self._store() as store, store.tx():
            causes = self._influence_causes(state, out["influence_decisions"])
            scene_id = store.append_event(
                world_id,
                day=day,
                slot=slot,
                kind="scene",
                title=out["title"],
                summary=out["scene"],
                payload={
                    "location": out["location"],
                    "with": out["with"],
                    "relationship_changes": out["relationship_changes"],
                    "influence_decisions": out["influence_decisions"],
                    "discoveries": out["discoveries"],
                    "meta": meta,
                },
                causes=causes,
                now=now,
            )
            self._apply_effects(state, out, scene_id)
            state["protagonist"]["location"] = out["location"]
            event_ids = [scene_id]
            if review is None:
                state["slot"] += 1
            else:
                review_out, review_meta = review
                day_scene_ids = [e["id"] for e in earlier_scenes] + [scene_id]
                review_id = store.append_event(
                    world_id,
                    day=day,
                    slot=slot,
                    kind="day_review",
                    title=f"第{day}天",
                    summary=review_out["summary"],
                    payload={"diary": review_out["diary"], "meta": review_meta},
                    causes=[{"kind": "event", "id": event_id} for event_id in day_scene_ids],
                    now=now,
                )
                event_ids.append(review_id)
                self._end_day(state, review_out["diary"], review_out["focus"], review_id)
                if review_out["letter"]:
                    letter_id = store.add_letter(
                        world_id,
                        day=day,
                        title=review_out["letter"]["title"],
                        body=review_out["letter"]["body"],
                        causes=[{"kind": "event", "id": review_id}],
                        now=now,
                    )
            state["last_seen_at"] = now.isoformat()
            store.save_state(world_id, state)
        return {"event_ids": event_ids, "letter_id": letter_id}

    def read_letter(self, world_id: str, letter_id: str) -> dict:
        self._bp(world_id)
        with self._store() as store, store.tx():
            try:
                store.mark_letter_read(world_id, letter_id, self.clock())
            except LookupError as exc:
                raise NotFound(str(exc)) from None
        return {"letter_id": letter_id}

    # Read model -----------------------------------------------------------------

    def snapshot(self, world_id: str, *, include_debug: bool = False) -> dict:
        """The read model for clients.

        `include_debug` adds the developer view, which carries every NPC's hidden
        secret. Only a caller that has decided to expose it should pass True.
        """
        state = self._load_state(world_id)
        bp = self._bp(world_id)
        with self._store() as store:
            events = store.list_events(world_id, limit=60)
            messages = store.recent_messages(world_id, 80)
            letters = store.list_letters(world_id)
        hero = state["protagonist"]
        influences = {item["id"]: item for item in state["influences"]}
        slot = bp.data["slots"][state["slot"] - 1]
        snapshot = {
            "world": {
                "id": world_id,
                "name": bp.data["world"]["name"],
                "premise": bp.data["world"]["premise"],
            },
            "llm": self.provider.label,
            "time": {"day": state["day"], "slot": state["slot"], "label": slot["label"], "hint": slot["hint"]},
            "slots": [item["label"] for item in bp.data["slots"]],
            "protagonist": {
                "name": bp.data["protagonist"]["name"],
                "role": bp.data["protagonist"]["role"],
                "mood": hero["mood"],
                "location": bp.locations[hero["location"]]["name"],
                "focus": hero["focus"],
                "known_facts": [
                    {"npc": bp.npcs[fact["npc"]]["name"], "fact": fact["fact"], "day": fact["day"]}
                    for fact in hero["known_facts"]
                ],
            },
            "relationships": [
                {
                    "id": npc_id,
                    "name": bp.npcs[npc_id]["name"],
                    "role": bp.npcs[npc_id]["role"],
                    "affinity": rel["affinity"],
                    "note": rel["note"],
                    "last_reason": rel["last_reason"],
                }
                for npc_id, rel in state["relationships"].items()
            ],
            "influences": [
                {
                    **item,
                    "target_name": bp.npcs[item["target"]]["name"] if item.get("target") else None,
                }
                for item in state["influences"]
            ],
            "timeline": [self._timeline_entry(bp, event, influences) for event in events],
            "messages": [
                {"id": m["id"], "role": m["role"], "text": m["text"], "day": m["day"], "slot": m["slot"]}
                for m in messages
            ],
            "letters": letters,
            "unread_letters": sum(1 for letter in letters if not letter["read"]),
        }
        if include_debug:
            snapshot["debug"] = {
                "npcs": [
                    {
                        "name": npc["name"],
                        "role": npc["role"],
                        "hidden": npc["hidden"],
                        "location": bp.locations[state["npcs"][npc["id"]]["location"]]["name"],
                        "status": state["npcs"][npc["id"]]["status"],
                    }
                    for npc in bp.data["npcs"]
                ],
                "memories": hero["memories"][-8:],
                "diaries": state["diaries"][-3:],
            }
        return snapshot

    # Internals ------------------------------------------------------------------

    def _store(self) -> Store:
        return Store(self.db_path)

    def _load_state(self, world_id: str) -> dict:
        with self._store() as store:
            try:
                return store.load_state(world_id)
            except LookupError as exc:
                raise NotFound(str(exc)) from None

    def _bp(self, world_id: str) -> WorldBlueprint:
        """The blueprint stored with this world, read once and cached."""
        cached = self._blueprints.get(world_id)
        if cached is None:
            with self._store() as store:
                try:
                    raw = store.load_blueprint(world_id)
                except LookupError as exc:
                    raise NotFound(str(exc)) from None
            if (version := _blueprint_version(raw)) not in SUPPORTED_BLUEPRINT_VERSIONS:
                raise NotFound(
                    f"world {world_id} uses blueprint version {version}, which this build "
                    "cannot read; start a new world"
                )
            cached = self._blueprints[world_id] = WorldBlueprint.of(raw)
        return cached

    def _touch(self, world_id: str, now: datetime) -> None:
        state = self._load_state(world_id)
        state["last_seen_at"] = now.isoformat()
        with self._store() as store, store.tx():
            store.save_state(world_id, state)

    def _initial_state(self, bp: WorldBlueprint, now: datetime) -> dict:
        p = bp.data["protagonist"]
        return {
            "day": 1,
            "slot": 1,
            "protagonist": {
                "location": p["start_location"],
                "mood": p.get("start_mood", "平静"),
                "focus": p["goals"][0],
                "memories": [],
                "known_facts": [],
            },
            "diaries": [],
            "npcs": {
                npc["id"]: {"location": npc["start_location"], "status": ""}
                for npc in bp.data["npcs"]
            },
            "relationships": {
                npc["id"]: {
                    "affinity": npc["affinity"],
                    "note": npc["relationship"],
                    "last_reason": "",
                    "last_event_id": None,
                }
                for npc in bp.data["npcs"]
            },
            "influences": [],
            "last_seen_at": now.isoformat(),
        }

    def _begin_catch_up(self, world_id: str, state: dict, days_away: int, anchor: datetime) -> dict:
        """Record the catch-up plan before any model call so a failure can be resumed."""
        target = min(days_away, MAX_CATCH_UP_DAYS)
        state["catch_up"] = {
            "anchor": anchor.isoformat(),
            "days_away": days_away,
            "target": target,
            "done": 0,
            "slept": days_away > target,
            "sleep_written": False,
            "event_ids": [],
            "diaries": [],
        }
        with self._store() as store, store.tx():
            store.save_state(world_id, state)
        return state["catch_up"]

    def _run_catch_up(self, world_id: str) -> dict:
        """Finish the stored plan: remaining days, then the sleep event, then the letter."""
        plan = self._load_state(world_id)["catch_up"]
        while plan["done"] < plan["target"]:
            self._simulate_offscreen_day(world_id)
            advanced = self._load_state(world_id)["catch_up"]
            if advanced["done"] <= plan["done"]:
                raise RuntimeError("catch-up made no progress; refusing to repeat a day")
            plan = advanced
        if plan["slept"] and not plan["sleep_written"]:
            self._write_sleep_event(world_id)
            plan = self._load_state(world_id)["catch_up"]
        letter_id = self._write_absence_letter(world_id)
        return {
            "days_away": plan["days_away"],
            "simulated_days": plan["target"],
            "slept": plan["slept"],
            "letter_id": letter_id,
            "event_ids": plan["event_ids"],
        }

    def _write_sleep_event(self, world_id: str) -> None:
        state = self._load_state(world_id)
        plan = state["catch_up"]
        with self._store() as store, store.tx():
            plan["event_ids"].append(
                store.append_event(
                    world_id,
                    day=state["day"],
                    slot=state["slot"],
                    kind="sleep",
                    title="世界进入休眠",
                    summary=f"笔友离开了{plan['days_away']}天。补算{plan['target']}天之后，这个世界停下来等你回来。",
                    payload={"days_away": plan["days_away"]},
                    causes=[],
                    now=self.clock(),
                )
            )
            plan["sleep_written"] = True
            store.save_state(world_id, state)

    def _simulate_offscreen_day(self, world_id: str) -> None:
        state = self._load_state(world_id)
        bp = self._bp(world_id)
        day, slot = state["day"], state["slot"]
        with self._store() as store:
            recent = store.list_events(world_id, limit=6, kinds=STORY_EVENT_KINDS)
        request = LLMRequest(
            task="offscreen_day",
            system=prompts.narrator_system(bp.data),
            prompt=prompts.offscreen_prompt(bp.data, state, recent),
            context=self._fake_context(bp, state),
            max_tokens=1800,
        )
        try:
            out, meta = complete_json(self.provider, request, partial(self._validate_offscreen, bp))
        except InvalidModelOutput as exc:
            out = self._fallback_offscreen(state)
            meta = {"fallback": True, "error": str(exc)}
        screen, discoveries = boundary.Screen.for_output(bp.npcs, state, out["discoveries"])
        out = self._screen_effects(screen, out, discoveries)
        out = {
            **out,
            "diary": screen.check(out["diary"], "diary") or DIARY_FALLBACK,
            "focus": screen.check(out.get("focus"), "focus"),
        }
        if blocked := screen.drain():
            meta = {**meta, "leak_blocked": blocked}

        with self._store() as store, store.tx():
            event_id = store.append_event(
                world_id,
                day=day,
                slot=slot,
                kind="offscreen_day",
                title=out["highlights"][0]["title"] if out["highlights"] else "平常的一天",
                summary=out["summary"],
                payload={
                    "highlights": out["highlights"],
                    "diary": out["diary"],
                    "relationship_changes": out["relationship_changes"],
                    "influence_decisions": out["influence_decisions"],
                    "discoveries": out["discoveries"],
                    "meta": meta,
                },
                causes=self._influence_causes(state, out["influence_decisions"]),
                now=self.clock(),
            )
            self._apply_effects(state, out, event_id)
            state["protagonist"]["location"] = bp.data["protagonist"]["home_location"]
            self._end_day(state, out["diary"], out.get("focus"), event_id)
            plan = state["catch_up"]
            plan["done"] += 1
            plan["event_ids"].append(event_id)
            plan["diaries"].append({"day": day, "text": out["diary"]})
            store.save_state(world_id, state)

    def _write_absence_letter(self, world_id: str) -> str:
        """Write the letter and finish the plan in one transaction."""
        state = self._load_state(world_id)
        bp = self._bp(world_id)
        plan = state["catch_up"]
        request = LLMRequest(
            task="letter",
            system=prompts.protagonist_system(bp.data),
            prompt=prompts.absence_letter_prompt(
                bp.data, state, plan["days_away"], plan["slept"], plan["diaries"]
            ),
            context={"days_away": plan["days_away"], "slept": plan["slept"], "diaries": plan["diaries"]},
            max_tokens=1200,
        )
        try:
            out, _ = complete_json(self.provider, request, self._validate_letter)
        except InvalidModelOutput:
            out = dict(LETTER_FALLBACK)
        screen = boundary.Screen.for_state(bp.npcs, state)
        if self._screen_letter(screen, out, "absence_letter") is None:
            out = dict(LETTER_FALLBACK)
        with self._store() as store, store.tx():
            current = store.load_state(world_id)
            letter_id = store.add_letter(
                world_id,
                day=current["day"],
                title=out["title"],
                body=out["body"],
                causes=[{"kind": "event", "id": event_id} for event_id in plan["event_ids"]],
                now=self.clock(),
            )
            anchor = _aware(datetime.fromisoformat(plan["anchor"]))
            last_seen = _aware(datetime.fromisoformat(current["last_seen_at"]))
            current["last_seen_at"] = max(anchor, last_seen).isoformat()
            del current["catch_up"]
            store.save_state(world_id, current)
        return letter_id

    def _review_day(
        self,
        bp: WorldBlueprint,
        state: Mapping[str, Any],
        scenes: list[dict],
        chat_count: int,
        screen: boundary.Screen,
    ) -> tuple[dict, dict]:
        # The review is written in her voice, so it sees scene text only when that
        # text carries no secret she has not discovered.
        safe_scenes = [
            {
                **scene,
                "title": screen.check(scene["title"], "scene_title") or "（略）",
                "summary": screen.check(scene["summary"], "scene") or "",
            }
            for scene in scenes
        ]
        request = LLMRequest(
            task="review",
            system=prompts.narrator_system(bp.data),
            prompt=prompts.review_prompt(bp.data, state, safe_scenes, chat_count),
            context={"day": state["day"], "scenes": safe_scenes, "chat_count": chat_count},
        )
        try:
            out, meta = complete_json(self.provider, request, self._validate_review)
        except InvalidModelOutput as exc:
            summary = "；".join(scene["title"] for scene in safe_scenes) or "平常的一天"
            out = {"summary": summary, "diary": "", "focus": None, "letter": None}
            meta = {"fallback": True, "error": str(exc)}
        out = {
            **out,
            "diary": screen.check(out["diary"], "diary") or "",
            "focus": screen.check(out["focus"], "focus"),
            "letter": self._screen_letter(screen, out["letter"], "review_letter"),
        }
        if blocked := screen.drain():
            meta = {**meta, "leak_blocked": blocked}
        return out, meta

    @staticmethod
    def _screen_letter(screen: boundary.Screen, letter: dict | None, field: str) -> dict | None:
        """The letter, or None when its title or body carries a protected secret."""
        if letter is None:
            return None
        clean = screen.check(letter["title"], f"{field}_title") and screen.check(letter["body"], f"{field}_body")
        return letter if clean else None

    @staticmethod
    def _screen_effects(
        screen: boundary.Screen, out: Mapping[str, Any], discoveries: list[dict]
    ) -> dict:
        """Remove protected secrets from the text the narrator wrote for her to keep."""
        return {
            **out,
            "mood": screen.check(out.get("mood"), "mood"),
            "memory": screen.check(out.get("memory"), "memory"),
            "relationship_changes": [
                {**change, "reason": screen.check(change["reason"], "relationship_reason") or ""}
                for change in out["relationship_changes"]
            ],
            "influence_decisions": [
                {**decision, "reason": screen.check(decision["reason"], "decision_reason") or ""}
                for decision in out["influence_decisions"]
            ],
            "discoveries": discoveries,
        }

    def _apply_effects(self, state: dict, out: Mapping[str, Any], event_id: str) -> None:
        hero = state["protagonist"]
        open_items = {item["id"]: item for item in state["influences"] if item["status"] in OPEN_INFLUENCE}
        for decision in out["influence_decisions"]:
            item = open_items.get(decision["id"])
            if item is None:
                continue
            item["status"] = decision["decision"]
            item["reason"] = decision["reason"]
            item["resolved_event_id"] = event_id
        for change in out["relationship_changes"]:
            rel = state["relationships"][change["npc"]]
            rel["affinity"] = max(0, min(100, rel["affinity"] + change["delta"]))
            rel["last_reason"] = change["reason"]
            rel["last_event_id"] = event_id
        known = {fact["fact"] for fact in hero["known_facts"]}
        for discovery in out["discoveries"]:
            if discovery["fact"] not in known:
                hero["known_facts"].append({**discovery, "day": state["day"], "event_id": event_id})
        for update in out["npc_updates"]:
            state["npcs"][update["npc"]] = {"location": update["location"], "status": update["status"]}
        if out.get("mood"):
            hero["mood"] = out["mood"]
        if out.get("memory"):
            hero["memories"].append({"day": state["day"], "slot": state["slot"], "text": out["memory"], "event_id": event_id})
            del hero["memories"][:-MAX_MEMORIES]

    def _end_day(self, state: dict, diary: str, focus: str | None, event_id: str) -> None:
        if diary:
            state["diaries"].append({"day": state["day"], "text": diary, "event_id": event_id})
            del state["diaries"][:-MAX_DIARIES]
        if focus:
            state["protagonist"]["focus"] = focus
        state["day"] += 1
        state["slot"] = 1

    def _influence_causes(self, state: Mapping[str, Any], decisions: list[dict]) -> list[dict]:
        open_ids = {item["id"] for item in state["influences"] if item["status"] in OPEN_INFLUENCE}
        return [
            {"kind": "influence", "id": decision["id"], "decision": decision["decision"]}
            for decision in decisions
            if decision["id"] in open_ids
        ]

    def _timeline_entry(self, bp: WorldBlueprint, event: Mapping[str, Any], influences: Mapping[str, Any]) -> dict:
        causes = []
        for cause in event["causes"]:
            item = influences.get(cause["id"]) if cause["kind"] == "influence" else None
            if item is not None:
                causes.append(
                    {"text": item["text"], "decision": cause.get("decision", item["status"]), "reason": item["reason"]}
                )
        payload = event["payload"]
        return {
            "id": event["id"],
            "day": event["day"],
            "slot": event["slot"],
            "slot_label": bp.slot_label(event["slot"]),
            "kind": event["kind"],
            "title": event["title"],
            "summary": event["summary"],
            "location": bp.locations.get(payload.get("location"), {}).get("name"),
            "with": [bp.npcs[npc_id]["name"] for npc_id in payload.get("with", []) if npc_id in bp.npcs],
            "highlights": [item["title"] for item in payload.get("highlights", [])],
            "causes": causes,
            "fallback": bool(payload.get("meta", {}).get("fallback")),
        }

    @staticmethod
    def _scene_view(bp: WorldBlueprint, event: Mapping[str, Any]) -> dict:
        return {"slot_label": bp.slot_label(event["slot"]), "title": event["title"], "summary": event["summary"]}

    @staticmethod
    def _fake_context(bp: WorldBlueprint, state: Mapping[str, Any]) -> dict:
        return {
            "day": state["day"],
            "slot": state["slot"],
            "slot_label": bp.slot_label(state["slot"]),
            "protagonist": bp.data["protagonist"]["name"],
            "locations": [{"id": loc["id"], "name": loc["name"]} for loc in bp.data["locations"]],
            "npcs": [
                {
                    "id": npc["id"],
                    "name": npc["name"],
                    "hidden": npc["hidden"],
                    "location": state["npcs"][npc["id"]]["location"],
                }
                for npc in bp.data["npcs"]
            ],
            "pending": [
                {"id": item["id"], "text": item["text"], "target": item.get("target")}
                for item in state["influences"]
                if item["status"] in OPEN_INFLUENCE
            ],
        }

    @staticmethod
    def _fallback_slot(bp: WorldBlueprint, state: Mapping[str, Any]) -> dict:
        label = bp.slot_label(state["slot"])
        return {
            "location": state["protagonist"]["location"],
            "with": [],
            "title": f"平常的{label}",
            "scene": f"{label}平平常常地过去了。",
            "mood": None,
            "memory": None,
            "relationship_changes": [],
            "influence_decisions": [],
            "discoveries": [],
            "npc_updates": [],
        }

    @staticmethod
    def _fallback_offscreen(state: Mapping[str, Any]) -> dict:
        return {
            "summary": f"第{state['day']}天平平常常地过去了。",
            "highlights": [],
            "diary": DIARY_FALLBACK,
            "mood": None,
            "memory": None,
            "focus": None,
            "relationship_changes": [],
            "influence_decisions": [],
            "discoveries": [],
            "npc_updates": [],
        }

    # Validation: drop anything the contract does not allow -----------------------

    @staticmethod
    def _validate_chat(bp: WorldBlueprint, obj: Mapping[str, Any]) -> dict:
        # Only a reply, an optional influence and a mood survive; any other field
        # (relationship edits, location changes, ...) is dropped on purpose.
        result = {"reply": _text(obj, "reply", 600), "influence": None}
        influence = obj.get("influence")
        if isinstance(influence, Mapping) and str(influence.get("text") or "").strip():
            target = influence.get("target")
            result["influence"] = {
                "text": _clip(str(influence["text"]).strip(), 80),
                "target": target if target in bp.npcs else None,
            }
        mood = _optional_text(obj, "mood", 12)
        if mood:
            result["mood"] = mood
        return result

    @staticmethod
    def _salvage_chat(raw: str) -> dict | None:
        text = raw.strip()
        if text and "{" not in text:
            return {"reply": _clip(text, 600), "influence": None}
        return None

    def _validate_slot(self, bp: WorldBlueprint, obj: Mapping[str, Any]) -> dict:
        location = obj.get("location")
        if location not in bp.locations:
            raise ValueError(f"unknown location: {location!r}")
        return {
            "location": location,
            "with": [npc_id for npc_id in _list(obj.get("with")) if npc_id in bp.npcs],
            "title": _text(obj, "title", 24),
            "scene": _text(obj, "scene", 600),
            "mood": _optional_text(obj, "mood", 12),
            "memory": _optional_text(obj, "memory", 120),
            **self._validate_effects(bp, obj),
        }

    def _validate_offscreen(self, bp: WorldBlueprint, obj: Mapping[str, Any]) -> dict:
        highlights = []
        for item in _list(obj.get("highlights"))[:3]:
            if isinstance(item, Mapping) and str(item.get("title") or "").strip():
                highlights.append({"title": _clip(str(item["title"]).strip(), 24)})
        return {
            "summary": _text(obj, "summary", 400),
            "highlights": highlights,
            "diary": _text(obj, "diary", 400),
            "mood": _optional_text(obj, "mood", 12),
            "memory": _optional_text(obj, "memory", 120),
            "focus": _optional_text(obj, "focus", 60),
            **self._validate_effects(bp, obj),
        }

    def _validate_review(self, obj: Mapping[str, Any]) -> dict:
        letter = obj.get("letter")
        if isinstance(letter, Mapping) and str(letter.get("body") or "").strip():
            letter = self._validate_letter(letter)
        else:
            letter = None
        return {
            "summary": _text(obj, "summary", 300),
            "diary": _optional_text(obj, "diary", 400) or "",
            "focus": _optional_text(obj, "focus", 60),
            "letter": letter,
        }

    @staticmethod
    def _validate_letter(obj: Mapping[str, Any]) -> dict:
        return {"title": _optional_text(obj, "title", 30) or "无题", "body": _text(obj, "body", 1500)}

    @staticmethod
    def _validate_effects(bp: WorldBlueprint, obj: Mapping[str, Any]) -> dict:
        changes = []
        for item in _list(obj.get("relationship_changes")):
            if not isinstance(item, Mapping) or item.get("npc") not in bp.npcs:
                continue
            try:
                delta = int(item.get("delta", 0))
            except (TypeError, ValueError):
                continue
            delta = max(-MAX_RELATIONSHIP_DELTA, min(MAX_RELATIONSHIP_DELTA, delta))
            if delta:
                changes.append({"npc": item["npc"], "delta": delta, "reason": _clip(str(item.get("reason") or ""), 80)})
        decisions = [
            {"id": item["id"], "decision": item["decision"], "reason": _clip(str(item.get("reason") or ""), 100)}
            for item in _list(obj.get("influence_decisions"))
            if isinstance(item, Mapping) and isinstance(item.get("id"), str) and item.get("decision") in DECISIONS
        ]
        discoveries = [
            {"npc": item["npc"], "fact": _clip(str(item["fact"]).strip(), 100)}
            for item in _list(obj.get("discoveries"))
            if isinstance(item, Mapping) and item.get("npc") in bp.npcs and str(item.get("fact") or "").strip()
        ]
        npc_updates = [
            {"npc": item["npc"], "location": item["location"], "status": _clip(str(item.get("status") or ""), 20)}
            for item in _list(obj.get("npc_updates"))
            if isinstance(item, Mapping) and item.get("npc") in bp.npcs and item.get("location") in bp.locations
        ]
        return {
            "relationship_changes": changes,
            "influence_decisions": decisions,
            "discoveries": discoveries,
            "npc_updates": npc_updates,
        }


def _blueprint_version(raw: Mapping[str, Any]) -> Any:
    return raw.get("blueprint_version", 1)


def _require_supported(raw: Mapping[str, Any]) -> None:
    if (version := _blueprint_version(raw)) not in SUPPORTED_BLUEPRINT_VERSIONS:
        raise ValueError(
            f"unsupported blueprint_version {version!r}; this build reads {SUPPORTED_BLUEPRINT_VERSIONS}"
        )


def _aware(moment: datetime) -> datetime:
    """Treat a naive datetime as local time so aware and naive values compare."""
    return moment if moment.tzinfo is not None else moment.astimezone()


def _text(obj: Mapping[str, Any], key: str, limit: int) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing text field: {key}")
    return _clip(value.strip(), limit)


def _optional_text(obj: Mapping[str, Any], key: str, limit: int) -> str | None:
    value = obj.get(key)
    return _clip(value.strip(), limit) if isinstance(value, str) and value.strip() else None


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
