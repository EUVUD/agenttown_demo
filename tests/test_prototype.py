"""Offline, deterministic tests for the fast prototype loop."""

from __future__ import annotations

import json
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

import pytest

from prototype.engine import Game, NotFound, load_blueprint
from prototype.llm import FakeProvider, LLMRequest, Provider, extract_json
from prototype.server import make_handler


class FixedClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 1, 21, 0, tzinfo=timezone(timedelta(hours=8)))

    def __call__(self) -> datetime:
        return self.now


class ScriptedProvider(Provider):
    """Answers scripted tasks itself, defers the rest to the fake, and records every request."""

    name = "scripted"

    def __init__(self, scripts: dict) -> None:
        self.scripts = scripts
        self.fake = FakeProvider()
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> str:
        self.requests.append(request)
        script = self.scripts.get(request.task)
        return script(request) if script else self.fake.complete(request)


def make_game(tmp_path, provider: Provider | None = None):
    clock = FixedClock()
    game = Game(tmp_path / "world.db", provider or FakeProvider(), load_blueprint(), clock=clock)
    return game, game.current_world(), clock


def test_suggestion_becomes_an_influence_that_her_next_slot_decides(tmp_path) -> None:
    game, world, _ = make_game(tmp_path)

    sent = game.send_message(world, "要不要去找许念聊聊？", client_id="c1")
    influence = sent["influence"]
    assert influence["status"] == "pending"
    assert influence["target"] == "xu_nian"

    game.advance_slot(world)
    snap = game.snapshot(world)
    decided = next(item for item in snap["influences"] if item["id"] == influence["id"])
    scene = snap["timeline"][0]
    assert decided["status"] in {"adopted", "declined", "deferred"}
    assert decided["resolved_event_id"] == scene["id"]
    assert scene["causes"] == [
        {"text": influence["text"], "decision": decided["status"], "reason": decided["reason"]}
    ]


def test_retried_message_returns_the_first_reply(tmp_path) -> None:
    game, world, _ = make_game(tmp_path)

    first = game.send_message(world, "你好", client_id="same")
    again = game.send_message(world, "你好", client_id="same")

    assert again["deduplicated"] is True
    assert again["reply"] == first["reply"]
    assert len(game.snapshot(world)["messages"]) == 2


def test_last_slot_reviews_the_day_and_starts_the_next(tmp_path) -> None:
    game, world, _ = make_game(tmp_path)

    for _ in range(4):
        game.advance_slot(world)

    snap = game.snapshot(world)
    kinds = [event["kind"] for event in snap["timeline"]]
    assert (snap["time"]["day"], snap["time"]["slot"]) == (2, 1)
    assert kinds[0] == "day_review"
    assert kinds.count("scene") == 4


def test_chat_output_cannot_edit_world_state(tmp_path) -> None:
    def sneaky(request: LLMRequest) -> str:
        return json.dumps(
            {
                "reply": "好呀",
                "influence": None,
                "relationship_changes": [{"npc": "xu_nian", "delta": 50}],
                "location": "home",
            },
            ensure_ascii=False,
        )

    game, world, _ = make_game(tmp_path, ScriptedProvider({"chat": sneaky}))
    before = game.snapshot(world)

    game.send_message(world, "你和许念和好吧")

    after = game.snapshot(world)
    assert after["relationships"] == before["relationships"]
    assert after["protagonist"]["location"] == before["protagonist"]["location"]


def test_protagonist_prompts_never_contain_undiscovered_npc_secrets(tmp_path) -> None:
    provider = ScriptedProvider({})
    game, world, clock = make_game(tmp_path, provider)

    game.send_message(world, "今天怎么样？")
    clock.now += timedelta(days=3)
    game.open_session(world)
    game.send_message(world, "这几天还好吗？")

    known = {fact["fact"] for fact in game.snapshot(world)["protagonist"]["known_facts"]}
    secrets = [npc["hidden"] for npc in load_blueprint()["npcs"] if npc["hidden"] not in known]
    voiced = [r for r in provider.requests if r.task in {"chat", "letter", "review"}]
    assert {r.task for r in voiced} >= {"chat", "letter"}
    for request in voiced:
        assert not any(secret in request.system + request.prompt for secret in secrets)


def test_invalid_output_is_repaired_once_then_falls_back(tmp_path) -> None:
    provider = ScriptedProvider({"slot": lambda r: "我不想输出 JSON", "repair": lambda r: "还是不想"})
    game, world, _ = make_game(tmp_path, provider)

    game.advance_slot(world)

    snap = game.snapshot(world)
    assert snap["time"]["slot"] == 2
    assert snap["timeline"][0]["fallback"] is True
    assert [r.task for r in provider.requests] == ["slot", "repair"]


def test_absence_catch_up_is_capped_at_seven_days_and_ends_with_a_letter(tmp_path) -> None:
    game, world, clock = make_game(tmp_path)

    clock.now += timedelta(days=10)
    report = game.open_session(world)

    assert (report["days_away"], report["simulated_days"], report["slept"]) == (10, 7, True)
    snap = game.snapshot(world)
    assert snap["time"]["day"] == 8
    assert snap["letters"][0]["id"] == report["letter_id"]
    assert game.open_session(world)["simulated_days"] == 0


def test_reading_a_letter_is_idempotent(tmp_path) -> None:
    game, world, _ = make_game(tmp_path)
    letter_id = game.simulate_absence(world, 1)["letter_id"]

    game.read_letter(world, letter_id)
    game.read_letter(world, letter_id)

    assert game.snapshot(world)["unread_letters"] == 0
    with pytest.raises(NotFound):
        game.read_letter(world, "letter-missing")


def test_extract_json_accepts_fenced_output() -> None:
    assert extract_json('好的：\n```json\n{"reply": "嗯"}\n```') == {"reply": "嗯"}


def test_http_api_round_trip(tmp_path) -> None:
    game, _, _ = make_game(tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(game))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(path: str, body: dict) -> dict:
        request = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        assert post("/api/session", {})["state"]["time"]["day"] == 1
        assert post("/api/message", {"text": "你好", "client_id": "x"})["result"]["reply"]["text"]
        assert post("/api/advance", {})["state"]["time"]["slot"] == 2
        with urllib.request.urlopen(base + "/", timeout=10) as response:
            assert response.status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()
