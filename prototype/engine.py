"""Game rules for the Tomorrow's Reply prototype.

The player never edits world state. Chat can only leave a pending influence on the
protagonist; her own slot decisions adopt, decline or defer it, and every change
records the influences and events that caused it. Callers must serialize writes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from prototype import prompts
from prototype.llm import InvalidModelOutput, LLMRequest, Provider, complete_json
from prototype.store import Store, new_id

BLUEPRINT_PATH = Path(__file__).with_name("world.json")
MAX_CATCH_UP_DAYS = 7
MAX_RELATIONSHIP_DELTA = 10
MAX_MEMORIES = 40
MAX_DIARIES = 14
DECISIONS = ("adopted", "declined", "deferred")
OPEN_INFLUENCE = ("pending", "deferred")
STORY_EVENT_KINDS = ("scene", "offscreen_day", "day_review")


class NotFound(LookupError):
    """The requested world or letter does not exist."""


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
        self._npcs = {npc["id"]: npc for npc in self.blueprint["npcs"]}
        self._locations = {loc["id"]: loc for loc in self.blueprint["locations"]}
        self._slots_per_day = len(self.blueprint["slots"])
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
        with self._store() as store, store.tx():
            store.create_world(world_id, self.blueprint, self._initial_state(now), now)
            store.append_event(
                world_id,
                day=1,
                slot=1,
                kind="world_start",
                title="新学期开始",
                summary=self.blueprint["world"]["setting"],
                payload={},
                causes=[],
                now=now,
            )
        return world_id

    # Sessions and offline catch-up ---------------------------------------------

    def open_session(self, world_id: str) -> dict:
        """Catch up on real days missed since the last visit (one game day per real day)."""
        now = self.clock()
        state = self._load_state(world_id)
        last_seen = datetime.fromisoformat(state["last_seen_at"]).astimezone(now.tzinfo)
        days_away = max((now.date() - last_seen.date()).days, 0)
        report = {"days_away": days_away, "simulated_days": 0, "slept": False, "letter_id": None}
        if days_away:
            report.update(self._catch_up(world_id, days_away))
        self._touch(world_id, now)
        return report

    def simulate_absence(self, world_id: str, days: int) -> dict:
        """Developer shortcut: pretend the player left `days` real days ago."""
        if not 1 <= days <= 30:
            raise ValueError("days must be between 1 and 30")
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
        hero = state["protagonist"]
        request = LLMRequest(
            task="chat",
            system=prompts.protagonist_system(self.blueprint),
            prompt=prompts.chat_prompt(self.blueprint, state, history, text),
            context={
                "text": text,
                "npcs": [{"id": npc["id"], "name": npc["name"]} for npc in self.blueprint["npcs"]],
                "location_name": self._locations[hero["location"]]["name"],
            },
            max_tokens=800,
        )
        try:
            out, meta = complete_json(
                self.provider, request, self._validate_chat, salvage=self._salvage_chat
            )
        except InvalidModelOutput as exc:
            out = {"reply": "……（她盯着屏幕看了很久，最后什么也没回。）", "influence": None}
            meta = {"fallback": True, "error": str(exc)}

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
        day, slot = state["day"], state["slot"]
        with self._store() as store:
            recent = store.list_events(world_id, limit=6, kinds=STORY_EVENT_KINDS)
            earlier_scenes = store.events_for_day(world_id, day, "scene")
            chat_count = store.count_messages(world_id, day=day, role="player")

        request = LLMRequest(
            task="slot",
            system=prompts.narrator_system(self.blueprint),
            prompt=prompts.slot_prompt(self.blueprint, state, recent),
            context=self._fake_context(state),
        )
        try:
            out, meta = complete_json(self.provider, request, self._validate_slot)
        except InvalidModelOutput as exc:
            out, meta = self._fallback_slot(state), {"fallback": True, "error": str(exc)}

        review = None
        if slot == self._slots_per_day:
            scenes = [self._scene_view(e) for e in earlier_scenes]
            scenes.append({"slot_label": self._slot_label(slot), "title": out["title"], "summary": out["scene"]})
            review = self._review_day(state, scenes, chat_count)

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
        with self._store() as store, store.tx():
            try:
                store.mark_letter_read(world_id, letter_id, self.clock())
            except LookupError as exc:
                raise NotFound(str(exc)) from None
        return {"letter_id": letter_id}

    # Read model -----------------------------------------------------------------

    def snapshot(self, world_id: str) -> dict:
        state = self._load_state(world_id)
        with self._store() as store:
            events = store.list_events(world_id, limit=60)
            messages = store.recent_messages(world_id, 80)
            letters = store.list_letters(world_id)
        hero = state["protagonist"]
        influences = {item["id"]: item for item in state["influences"]}
        slot = self.blueprint["slots"][state["slot"] - 1]
        return {
            "world": {
                "id": world_id,
                "name": self.blueprint["world"]["name"],
                "premise": self.blueprint["world"]["premise"],
            },
            "llm": self.provider.label,
            "time": {"day": state["day"], "slot": state["slot"], "label": slot["label"], "hint": slot["hint"]},
            "slots": [item["label"] for item in self.blueprint["slots"]],
            "protagonist": {
                "name": self.blueprint["protagonist"]["name"],
                "role": self.blueprint["protagonist"]["role"],
                "mood": hero["mood"],
                "location": self._locations[hero["location"]]["name"],
                "focus": hero["focus"],
                "known_facts": [
                    {"npc": self._npcs[fact["npc"]]["name"], "fact": fact["fact"], "day": fact["day"]}
                    for fact in hero["known_facts"]
                ],
            },
            "relationships": [
                {
                    "id": npc_id,
                    "name": self._npcs[npc_id]["name"],
                    "role": self._npcs[npc_id]["role"],
                    "affinity": rel["affinity"],
                    "note": rel["note"],
                    "last_reason": rel["last_reason"],
                }
                for npc_id, rel in state["relationships"].items()
            ],
            "influences": [
                {
                    **item,
                    "target_name": self._npcs[item["target"]]["name"] if item.get("target") else None,
                }
                for item in state["influences"]
            ],
            "timeline": [self._timeline_entry(event, influences) for event in events],
            "messages": [
                {"id": m["id"], "role": m["role"], "text": m["text"], "day": m["day"], "slot": m["slot"]}
                for m in messages
            ],
            "letters": letters,
            "unread_letters": sum(1 for letter in letters if not letter["read"]),
            "debug": {
                "npcs": [
                    {
                        "name": npc["name"],
                        "role": npc["role"],
                        "hidden": npc["hidden"],
                        "location": self._locations[state["npcs"][npc["id"]]["location"]]["name"],
                        "status": state["npcs"][npc["id"]]["status"],
                    }
                    for npc in self.blueprint["npcs"]
                ],
                "memories": hero["memories"][-8:],
                "diaries": state["diaries"][-3:],
            },
        }

    # Internals ------------------------------------------------------------------

    def _store(self) -> Store:
        return Store(self.db_path)

    def _load_state(self, world_id: str) -> dict:
        with self._store() as store:
            try:
                return store.load_state(world_id)
            except LookupError as exc:
                raise NotFound(str(exc)) from None

    def _touch(self, world_id: str, now: datetime) -> None:
        state = self._load_state(world_id)
        state["last_seen_at"] = now.isoformat()
        with self._store() as store, store.tx():
            store.save_state(world_id, state)

    def _initial_state(self, now: datetime) -> dict:
        p = self.blueprint["protagonist"]
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
                for npc in self.blueprint["npcs"]
            },
            "relationships": {
                npc["id"]: {
                    "affinity": npc["affinity"],
                    "note": npc["relationship"],
                    "last_reason": "",
                    "last_event_id": None,
                }
                for npc in self.blueprint["npcs"]
            },
            "influences": [],
            "last_seen_at": now.isoformat(),
        }

    def _catch_up(self, world_id: str, days_away: int) -> dict:
        simulated = min(days_away, MAX_CATCH_UP_DAYS)
        event_ids, diaries = [], []
        for _ in range(simulated):
            event_id, diary = self._simulate_offscreen_day(world_id)
            event_ids.append(event_id)
            diaries.append(diary)
        slept = days_away > simulated
        if slept:
            state = self._load_state(world_id)
            with self._store() as store, store.tx():
                event_ids.append(
                    store.append_event(
                        world_id,
                        day=state["day"],
                        slot=state["slot"],
                        kind="sleep",
                        title="世界进入休眠",
                        summary=f"笔友离开了{days_away}天。补算{simulated}天之后，这个世界停下来等你回来。",
                        payload={"days_away": days_away},
                        causes=[],
                        now=self.clock(),
                    )
                )
        letter_id = self._write_absence_letter(world_id, days_away, slept, diaries, event_ids)
        return {"simulated_days": simulated, "slept": slept, "letter_id": letter_id, "event_ids": event_ids}

    def _simulate_offscreen_day(self, world_id: str) -> tuple[str, dict]:
        state = self._load_state(world_id)
        day, slot = state["day"], state["slot"]
        with self._store() as store:
            recent = store.list_events(world_id, limit=6, kinds=STORY_EVENT_KINDS)
        request = LLMRequest(
            task="offscreen_day",
            system=prompts.narrator_system(self.blueprint),
            prompt=prompts.offscreen_prompt(self.blueprint, state, recent),
            context=self._fake_context(state),
            max_tokens=1800,
        )
        try:
            out, meta = complete_json(self.provider, request, self._validate_offscreen)
        except InvalidModelOutput as exc:
            out = self._fallback_offscreen(state)
            meta = {"fallback": True, "error": str(exc)}

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
            state["protagonist"]["location"] = self.blueprint["protagonist"]["home_location"]
            self._end_day(state, out["diary"], out.get("focus"), event_id)
            store.save_state(world_id, state)
        return event_id, {"day": day, "text": out["diary"]}

    def _write_absence_letter(
        self, world_id: str, days_away: int, slept: bool, diaries: list[dict], event_ids: list[str]
    ) -> str:
        state = self._load_state(world_id)
        request = LLMRequest(
            task="letter",
            system=prompts.protagonist_system(self.blueprint),
            prompt=prompts.absence_letter_prompt(self.blueprint, state, days_away, slept, diaries),
            context={"days_away": days_away, "slept": slept, "diaries": diaries},
            max_tokens=1200,
        )
        try:
            out, _ = complete_json(self.provider, request, self._validate_letter)
        except InvalidModelOutput:
            out = {"title": "你回来了", "body": "好久不见。这几天的事，一时不知道从哪说起……不过你回来了就好。"}
        with self._store() as store, store.tx():
            return store.add_letter(
                world_id,
                day=state["day"],
                title=out["title"],
                body=out["body"],
                causes=[{"kind": "event", "id": event_id} for event_id in event_ids],
                now=self.clock(),
            )

    def _review_day(
        self, state: Mapping[str, Any], scenes: list[dict], chat_count: int
    ) -> tuple[dict, dict]:
        request = LLMRequest(
            task="review",
            system=prompts.narrator_system(self.blueprint),
            prompt=prompts.review_prompt(self.blueprint, state, scenes, chat_count),
            context={"day": state["day"], "scenes": scenes, "chat_count": chat_count},
        )
        try:
            return complete_json(self.provider, request, self._validate_review)
        except InvalidModelOutput as exc:
            summary = "；".join(scene["title"] for scene in scenes) or "平常的一天"
            fallback = {"summary": summary, "diary": "", "focus": None, "letter": None}
            return fallback, {"fallback": True, "error": str(exc)}

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

    def _timeline_entry(self, event: Mapping[str, Any], influences: Mapping[str, Any]) -> dict:
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
            "slot_label": self._slot_label(event["slot"]),
            "kind": event["kind"],
            "title": event["title"],
            "summary": event["summary"],
            "location": self._locations.get(payload.get("location"), {}).get("name"),
            "with": [self._npcs[npc_id]["name"] for npc_id in payload.get("with", []) if npc_id in self._npcs],
            "highlights": [item["title"] for item in payload.get("highlights", [])],
            "causes": causes,
            "fallback": bool(payload.get("meta", {}).get("fallback")),
        }

    def _scene_view(self, event: Mapping[str, Any]) -> dict:
        return {"slot_label": self._slot_label(event["slot"]), "title": event["title"], "summary": event["summary"]}

    def _slot_label(self, slot: int) -> str:
        return self.blueprint["slots"][slot - 1]["label"]

    def _fake_context(self, state: Mapping[str, Any]) -> dict:
        return {
            "day": state["day"],
            "slot": state["slot"],
            "slot_label": self._slot_label(state["slot"]),
            "protagonist": self.blueprint["protagonist"]["name"],
            "locations": [{"id": loc["id"], "name": loc["name"]} for loc in self.blueprint["locations"]],
            "npcs": [
                {
                    "id": npc["id"],
                    "name": npc["name"],
                    "hidden": npc["hidden"],
                    "location": state["npcs"][npc["id"]]["location"],
                }
                for npc in self.blueprint["npcs"]
            ],
            "pending": [
                {"id": item["id"], "text": item["text"], "target": item.get("target")}
                for item in state["influences"]
                if item["status"] in OPEN_INFLUENCE
            ],
        }

    def _fallback_slot(self, state: Mapping[str, Any]) -> dict:
        label = self._slot_label(state["slot"])
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

    def _fallback_offscreen(self, state: Mapping[str, Any]) -> dict:
        return {
            "summary": f"第{state['day']}天平平常常地过去了。",
            "highlights": [],
            "diary": "今天没什么特别的。",
            "mood": None,
            "memory": None,
            "focus": None,
            "relationship_changes": [],
            "influence_decisions": [],
            "discoveries": [],
            "npc_updates": [],
        }

    # Validation: drop anything the contract does not allow -----------------------

    def _validate_chat(self, obj: Mapping[str, Any]) -> dict:
        # Only a reply, an optional influence and a mood survive; any other field
        # (relationship edits, location changes, ...) is dropped on purpose.
        result = {"reply": _text(obj, "reply", 600), "influence": None}
        influence = obj.get("influence")
        if isinstance(influence, Mapping) and str(influence.get("text") or "").strip():
            target = influence.get("target")
            result["influence"] = {
                "text": _clip(str(influence["text"]).strip(), 80),
                "target": target if target in self._npcs else None,
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

    def _validate_slot(self, obj: Mapping[str, Any]) -> dict:
        location = obj.get("location")
        if location not in self._locations:
            raise ValueError(f"unknown location: {location!r}")
        return {
            "location": location,
            "with": [npc_id for npc_id in _list(obj.get("with")) if npc_id in self._npcs],
            "title": _text(obj, "title", 24),
            "scene": _text(obj, "scene", 600),
            "mood": _optional_text(obj, "mood", 12),
            "memory": _optional_text(obj, "memory", 120),
            **self._validate_effects(obj),
        }

    def _validate_offscreen(self, obj: Mapping[str, Any]) -> dict:
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
            **self._validate_effects(obj),
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

    def _validate_effects(self, obj: Mapping[str, Any]) -> dict:
        changes = []
        for item in _list(obj.get("relationship_changes")):
            if not isinstance(item, Mapping) or item.get("npc") not in self._npcs:
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
            if isinstance(item, Mapping) and item.get("npc") in self._npcs and str(item.get("fact") or "").strip()
        ]
        npc_updates = [
            {"npc": item["npc"], "location": item["location"], "status": _clip(str(item.get("status") or ""), 20)}
            for item in _list(obj.get("npc_updates"))
            if isinstance(item, Mapping) and item.get("npc") in self._npcs and item.get("location") in self._locations
        ]
        return {
            "relationship_changes": changes,
            "influence_decisions": decisions,
            "discoveries": discoveries,
            "npc_updates": npc_updates,
        }


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
