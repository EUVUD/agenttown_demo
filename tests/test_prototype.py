"""Offline, deterministic tests for the fast prototype loop."""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.request
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

import pytest

from prototype import boundary
from prototype.engine import Game, NotFound, load_blueprint
from prototype.llm import (
    AnthropicProvider,
    FakeProvider,
    LLMError,
    LLMRequest,
    OpenAICompatibleProvider,
    Provider,
    extract_json,
    provider_from_env,
)
from prototype.store import Store
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


NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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
        with NO_PROXY.open(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        assert post("/api/session", {})["state"]["time"]["day"] == 1
        assert post("/api/message", {"text": "你好", "client_id": "x"})["result"]["reply"]["text"]
        assert post("/api/advance", {})["state"]["time"]["slot"] == 2
        with NO_PROXY.open(base + "/", timeout=10) as response:
            assert response.status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


# Resumable catch-up --------------------------------------------------------------------


def fail_on_call(task: str, call: int):
    """A script that raises a provider error on the given call of `task`, then behaves."""
    seen = {"calls": 0}

    def script(request: LLMRequest) -> str:
        seen["calls"] += 1
        if seen["calls"] == call:
            raise LLMError("provider unreachable: simulated outage")
        return FakeProvider().complete(request)

    return script


def count_kinds(snap: dict) -> dict[str, int]:
    kinds = [event["kind"] for event in snap["timeline"]]
    return {kind: kinds.count(kind) for kind in set(kinds)}


def test_catch_up_resumes_after_the_letter_fails_instead_of_repeating_the_absence(tmp_path) -> None:
    game, world, clock = make_game(tmp_path, ScriptedProvider({"letter": fail_on_call("letter", 1)}))
    clock.now += timedelta(days=10)

    with pytest.raises(LLMError):
        game.open_session(world)
    report = game.open_session(world)

    snap = game.snapshot(world)
    assert (report["days_away"], report["simulated_days"], report["slept"]) == (10, 7, True)
    assert snap["time"]["day"] == 8
    assert count_kinds(snap)["offscreen_day"] == 7 and count_kinds(snap)["sleep"] == 1
    assert [letter["id"] for letter in snap["letters"]] == [report["letter_id"]]
    assert game.open_session(world)["simulated_days"] == 0


def test_catch_up_resumes_from_the_day_that_failed(tmp_path) -> None:
    game, world, clock = make_game(
        tmp_path, ScriptedProvider({"offscreen_day": fail_on_call("offscreen_day", 3)})
    )
    clock.now += timedelta(days=5)

    with pytest.raises(LLMError):
        game.open_session(world)
    assert game.snapshot(world)["time"]["day"] == 3  # two days were committed
    report = game.open_session(world)

    snap = game.snapshot(world)
    assert (report["days_away"], report["simulated_days"], report["slept"]) == (5, 5, False)
    assert snap["time"]["day"] == 6
    assert count_kinds(snap)["offscreen_day"] == 5
    assert len(snap["letters"]) == 1


def test_a_late_retry_also_catches_up_the_days_that_passed_meanwhile(tmp_path) -> None:
    game, world, clock = make_game(tmp_path, ScriptedProvider({"letter": fail_on_call("letter", 1)}))
    clock.now += timedelta(days=3)
    with pytest.raises(LLMError):
        game.open_session(world)

    clock.now += timedelta(days=1)
    report = game.open_session(world)

    snap = game.snapshot(world)
    assert (report["days_away"], report["simulated_days"]) == (4, 4)
    assert snap["time"]["day"] == 5
    assert len(snap["letters"]) == 2


# Secrets stay out of every client response -------------------------------------------------


def all_secrets() -> list[str]:
    return [npc["hidden"] for npc in load_blueprint()["npcs"]]


def test_snapshot_carries_no_npc_secrets_unless_the_caller_opts_in(tmp_path) -> None:
    game, world, _ = make_game(tmp_path)

    default = game.snapshot(world)
    developer = game.snapshot(world, include_debug=True)

    assert "debug" not in default
    assert not any(secret in json.dumps(default, ensure_ascii=False) for secret in all_secrets())
    assert {npc["hidden"] for npc in developer["debug"]["npcs"]} == set(all_secrets())


@contextmanager
def running_server(game: Game, **options):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(game, **options))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def fetch(base: str, path: str, body: dict | None = None) -> str:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"content-type": "application/json"},
        method="GET" if data is None else "POST",
    )
    with NO_PROXY.open(request, timeout=10) as response:
        return response.read().decode("utf-8")


def without_discoveries(out: dict) -> None:
    out["discoveries"] = []


@pytest.mark.parametrize("dev", [False, True])
@pytest.mark.parametrize("query", ["", "?debug=1"])
def test_every_route_reveals_secrets_only_to_an_opted_in_developer_session(tmp_path, dev, query) -> None:
    # No discoveries, so a secret can only reach a body through the debug payload.
    scripts = {"slot": edited(without_discoveries), "offscreen_day": edited(without_discoveries)}
    game, _, _ = make_game(tmp_path, ScriptedProvider(scripts))
    expected = dev and query == "?debug=1"

    with running_server(game, dev=dev) as base:
        bodies = [
            fetch(base, "/api/state" + query),
            fetch(base, "/api/session" + query, {}),
            fetch(base, "/api/message" + query, {"text": "你好", "client_id": "c1"}),
            fetch(base, "/api/advance" + query, {}),
            fetch(base, "/api/dev/away" + query, {"days": 1}),
        ]
        letter_id = json.loads(bodies[-1])["state"]["letters"][0]["id"]
        bodies.append(fetch(base, f"/api/letters/{letter_id}/read" + query, {}))
        bodies.append(fetch(base, "/api/world/new" + query, {}))

    for body in bodies:
        assert any(secret in body for secret in all_secrets()) is expected
        assert ('"debug"' in body) is expected


def test_the_dev_flag_reaches_the_server(tmp_path, monkeypatch) -> None:
    import prototype.__main__ as entry

    calls = []
    monkeypatch.setattr(entry, "provider_from_env", lambda choice: FakeProvider())
    monkeypatch.setattr(entry, "serve", lambda game, host, port, *, dev=False: calls.append(dev))

    assert entry.main(["--db", str(tmp_path / "w.db")]) == 0
    assert entry.main(["--db", str(tmp_path / "w.db"), "--dev"]) == 0
    assert calls == [False, True]


# Narrator text cannot carry a secret past the knowledge boundary ------------------------------

SECRET = next(npc["hidden"] for npc in load_blueprint()["npcs"] if npc["id"] == "zhou_yu")


def edited(task_output_fixer):
    """Wrap the fake model so one task's output is altered before it is returned."""

    def script(request: LLMRequest) -> str:
        out = json.loads(FakeProvider().complete(request))
        task_output_fixer(out)
        return json.dumps(out, ensure_ascii=False)

    return script


def leaky_scripts() -> dict:
    def slot(out: dict) -> None:
        out["memory"] = f"我偷偷听说：{SECRET}"
        out["discoveries"] = []
        out["relationship_changes"] = [{"npc": "xu_nian", "delta": 2, "reason": SECRET}]
        out["influence_decisions"] = [
            {**item, "reason": SECRET} for item in out["influence_decisions"]
        ]

    def offscreen(out: dict) -> None:
        slot(out)
        out["diary"] = f"今晚我想起来了：{SECRET}"
        out["focus"] = f"弄清楚：{SECRET}"

    def review(out: dict) -> None:
        out["diary"] = f"日记：{SECRET}"
        out["focus"] = SECRET
        out["letter"] = {"title": "秘密", "body": f"我知道了：{SECRET}"}

    def letter(out: dict) -> None:
        out["body"] = f"这几天我发现：{SECRET}"

    def chat(out: dict) -> None:
        out["reply"] = f"其实我知道一件事：{SECRET}"

    return {
        "slot": edited(slot),
        "offscreen_day": edited(offscreen),
        "review": edited(review),
        "letter": edited(letter),
        "chat": edited(chat),
    }


def test_narrator_text_cannot_smuggle_an_undiscovered_secret_into_protagonist_prompts(tmp_path) -> None:
    provider = ScriptedProvider(leaky_scripts())
    game, world, clock = make_game(tmp_path, provider)
    game.send_message(world, "要不要去找许念聊聊？")
    for _ in range(4):  # four slots, then the day review
        game.advance_slot(world)
    clock.now += timedelta(days=3)
    game.open_session(world)
    reply = game.send_message(world, "这几天还好吗？")

    voiced = [r for r in provider.requests if r.task in {"chat", "letter", "review"}]
    assert {r.task for r in voiced} == {"chat", "letter", "review"}
    for request in voiced:
        visible = request.system + request.prompt + json.dumps(request.context, ensure_ascii=False)
        assert not boundary.shares_secret(visible, SECRET), request.task
    snap = game.snapshot(world, include_debug=True)
    stored = json.dumps(
        [snap["debug"]["memories"], snap["debug"]["diaries"], snap["relationships"], snap["influences"]],
        ensure_ascii=False,
    )
    assert not boundary.shares_secret(stored, SECRET)
    assert not any(boundary.shares_secret(f"{l['title']} {l['body']}", SECRET) for l in snap["letters"])
    assert not boundary.shares_secret(reply["reply"]["text"], SECRET)
    assert snap["protagonist"]["known_facts"] == []


def test_blocked_leaks_are_recorded_on_the_event_that_produced_them(tmp_path) -> None:
    game, world, _ = make_game(tmp_path, ScriptedProvider(leaky_scripts()))

    game.advance_slot(world)

    with game._store() as store:
        (scene,) = store.list_events(world, kinds=("scene",))
    blocked = {item["field"] for item in scene["payload"]["meta"]["leak_blocked"]}
    assert {"memory", "relationship_reason"} <= blocked


def test_a_discovered_secret_may_appear_in_her_memory_and_prompts(tmp_path) -> None:
    def revealing(out: dict) -> None:
        out["memory"] = f"我终于知道了：{SECRET}"
        out["discoveries"] = [{"npc": "zhou_yu", "fact": SECRET}]

    provider = ScriptedProvider({"slot": edited(revealing)})
    game, world, _ = make_game(tmp_path, provider)

    game.advance_slot(world)
    game.send_message(world, "后来呢？")

    snap = game.snapshot(world, include_debug=True)
    assert [f["fact"] for f in snap["protagonist"]["known_facts"]] == [SECRET]
    assert SECRET in snap["debug"]["memories"][-1]["text"]
    chat = [r for r in provider.requests if r.task == "chat"][-1]
    assert SECRET in chat.prompt


# A world keeps the blueprint it was created with ----------------------------------------------


def test_a_world_keeps_the_blueprint_it_was_created_with(tmp_path) -> None:
    game, world, clock = make_game(tmp_path)
    original = game.snapshot(world)
    changed = load_blueprint()
    renamed_id = changed["npcs"][0]["id"]
    changed["npcs"][0]["id"] = "renamed_npc"
    changed["npcs"].append({**changed["npcs"][1], "id": "extra_npc", "name": "新同学"})
    changed["world"]["name"] = "改名后的世界"
    reopened = Game(tmp_path / "world.db", FakeProvider(), changed, clock=clock)

    snap = reopened.snapshot(world)
    reopened.advance_slot(world)
    reopened.send_message(world, "你好")

    assert snap["world"]["name"] == original["world"]["name"]
    assert [r["id"] for r in snap["relationships"]] == [r["id"] for r in original["relationships"]]
    assert renamed_id in {r["id"] for r in snap["relationships"]}
    fresh = reopened.new_world()
    assert reopened.current_world() == fresh
    new_ids = {r["id"] for r in reopened.snapshot(fresh)["relationships"]}
    assert {"renamed_npc", "extra_npc"} <= new_ids and renamed_id not in new_ids
    assert renamed_id in {r["id"] for r in reopened.snapshot(world)["relationships"]}


def test_a_world_from_an_unsupported_blueprint_version_is_reported_not_crashed(tmp_path) -> None:
    game, world, _ = make_game(tmp_path)
    stale = load_blueprint()
    stale["blueprint_version"] = 99
    with closing(sqlite3.connect(tmp_path / "world.db")) as conn, conn:
        conn.execute("UPDATE worlds SET blueprint = ? WHERE id = ?", (json.dumps(stale), world))
    reopened = Game(tmp_path / "world.db", FakeProvider(), load_blueprint(), clock=FixedClock())

    with pytest.raises(NotFound, match="blueprint"):
        reopened.snapshot(world)


# More ways narrator text must not carry a secret ------------------------------------------------

XU_NIAN_SECRET = next(npc["hidden"] for npc in load_blueprint()["npcs"] if npc["id"] == "xu_nian")


def prompts_seen(provider: ScriptedProvider, tasks=("chat", "letter", "review")) -> list[str]:
    return [
        r.system + r.prompt + json.dumps(r.context, ensure_ascii=False)
        for r in provider.requests
        if r.task in tasks
    ]


def test_a_dropped_misattributed_discovery_does_not_unlock_its_person(tmp_path) -> None:
    def misattributed(out: dict) -> None:
        out["discoveries"] = [{"npc": "xu_nian", "fact": SECRET}]  # zhou_yu's secret filed under xu_nian
        out["memory"] = f"我听见：{XU_NIAN_SECRET}"
        out["relationship_changes"] = [{"npc": "xu_nian", "delta": 1, "reason": XU_NIAN_SECRET}]

    provider = ScriptedProvider({"slot": edited(misattributed)})
    game, world, _ = make_game(tmp_path, provider)

    game.advance_slot(world)
    game.send_message(world, "后来呢？")

    snap = game.snapshot(world, include_debug=True)
    assert snap["protagonist"]["known_facts"] == []
    assert snap["debug"]["memories"] == []
    assert not any(boundary.shares_secret(r["last_reason"], XU_NIAN_SECRET) for r in snap["relationships"])
    for text in prompts_seen(provider, ("chat",)):
        assert not boundary.shares_secret(text, SECRET) and not boundary.shares_secret(text, XU_NIAN_SECRET)


def test_chained_discoveries_cannot_launder_a_secret_into_known_facts(tmp_path) -> None:
    def chained(out: dict) -> None:
        out["discoveries"] = [
            {"npc": "zhou_yu", "fact": XU_NIAN_SECRET},
            {"npc": "xu_nian", "fact": SECRET},
        ]

    game, world, _ = make_game(tmp_path, ScriptedProvider({"slot": edited(chained)}))

    game.advance_slot(world)

    assert game.snapshot(world)["protagonist"]["known_facts"] == []


def test_an_unrelated_discovery_does_not_switch_the_screen_off(tmp_path) -> None:
    calls = {"n": 0}

    def trivia_then_secret(out: dict) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            out["discoveries"] = [{"npc": "zhou_yu", "fact": "周屿今天忘了带伞，借了她的。"}]
        else:
            out["discoveries"] = []
            out["memory"] = f"我总觉得：{SECRET}"
            out["influence_decisions"] = [{**d, "reason": SECRET} for d in out["influence_decisions"]]

    provider = ScriptedProvider({"slot": edited(trivia_then_secret)})
    game, world, _ = make_game(tmp_path, provider)

    game.advance_slot(world)
    game.advance_slot(world)
    game.send_message(world, "你怎么了？")

    snap = game.snapshot(world, include_debug=True)
    assert not any(boundary.shares_secret(m["text"], SECRET) for m in snap["debug"]["memories"])
    assert all(not boundary.shares_secret(text, SECRET) for text in prompts_seen(provider, ("chat",)))


def test_an_offscreen_diary_may_mention_a_secret_it_discovers(tmp_path) -> None:
    def reveals(out: dict) -> None:
        out["discoveries"] = [{"npc": "zhou_yu", "fact": SECRET}]
        out["diary"] = f"我终于弄明白了：{SECRET}"

    game, world, clock = make_game(tmp_path, ScriptedProvider({"offscreen_day": edited(reveals)}))
    clock.now += timedelta(days=1)

    game.open_session(world)

    snap = game.snapshot(world, include_debug=True)
    assert SECRET in snap["debug"]["diaries"][-1]["text"]
    assert [f["fact"] for f in snap["protagonist"]["known_facts"]] == [SECRET]


def test_scene_text_that_copies_a_secret_is_kept_out_of_the_review_prompt(tmp_path) -> None:
    def copies(out: dict) -> None:
        out["title"] = SECRET[:20]
        out["scene"] = f"她听见有人说：{SECRET}"
        out["discoveries"] = []

    provider = ScriptedProvider({"slot": edited(copies)})
    game, world, _ = make_game(tmp_path, provider)

    for _ in range(4):
        game.advance_slot(world)

    (review,) = [r for r in provider.requests if r.task == "review"]
    assert not boundary.shares_secret(review.prompt + json.dumps(review.context, ensure_ascii=False), SECRET)


def test_review_output_and_letters_are_screened_before_they_are_stored(tmp_path) -> None:
    provider = ScriptedProvider(leaky_scripts())
    game, world, clock = make_game(tmp_path, provider)
    for _ in range(4):
        game.advance_slot(world)
    game.send_message(world, "今天怎么样？")  # right after the review: its diary is now in the prompt

    snap = game.snapshot(world, include_debug=True)
    assert all(not boundary.shares_secret(d["text"], SECRET) for d in snap["debug"]["diaries"])
    assert snap["letters"] == []  # the review letter that copied the secret was dropped
    assert all(not boundary.shares_secret(text, SECRET) for text in prompts_seen(provider, ("chat",)))


def test_letters_whose_title_copies_a_secret_are_replaced_or_dropped(tmp_path) -> None:
    def title_leaks(out: dict) -> None:
        out["title"] = SECRET[:20]

    def review_letter(out: dict) -> None:
        out["letter"] = {"title": SECRET[:20], "body": "今天很平常。"}

    provider = ScriptedProvider({"letter": edited(title_leaks), "review": edited(review_letter)})
    game, world, clock = make_game(tmp_path, provider)
    for _ in range(4):
        game.advance_slot(world)
    clock.now += timedelta(days=2)
    game.open_session(world)

    letters = game.snapshot(world)["letters"]
    assert len(letters) == 1  # the review letter was dropped; the absence letter is the plain fallback
    assert not boundary.shares_secret(letters[0]["title"] + letters[0]["body"], SECRET)


def test_blocked_leaks_are_audited_on_every_kind_of_event_and_on_the_chat_reply(tmp_path) -> None:
    game, world, clock = make_game(tmp_path, ScriptedProvider(leaky_scripts()))
    for _ in range(4):
        game.advance_slot(world)
    clock.now += timedelta(days=2)
    game.open_session(world)
    reply = game.send_message(world, "这几天还好吗？")

    with game._store() as store:
        events = store.list_events(world, limit=60)
        messages = store.recent_messages(world, 10)
    for kind in ("scene", "day_review", "offscreen_day"):
        blocked = [e["payload"]["meta"].get("leak_blocked") for e in events if e["kind"] == kind]
        assert blocked and all(blocked), kind
    reply_meta = next(m["meta"] for m in messages if m["id"] == reply["reply"]["id"])
    assert reply_meta["leak_blocked"] == [{"field": "reply", "npc": "zhou_yu"}]


def test_mood_and_influence_text_cannot_carry_a_secret(tmp_path) -> None:
    def slot(out: dict) -> None:
        out["mood"] = SECRET[:12]
        out["discoveries"] = []

    def chat(out: dict) -> None:
        out["mood"] = SECRET[:12]
        out["influence"] = {"text": SECRET[:30], "target": None}

    provider = ScriptedProvider({"slot": edited(slot), "chat": edited(chat)})
    game, world, _ = make_game(tmp_path, provider)

    game.advance_slot(world)
    sent = game.send_message(world, "要不要去找许念聊聊？")
    game.send_message(world, "还好吗？")

    snap = game.snapshot(world)
    assert not boundary.shares_secret(snap["protagonist"]["mood"], SECRET)
    assert sent["influence"] is None and snap["influences"] == []
    assert all(not boundary.shares_secret(text, SECRET) for text in prompts_seen(provider, ("chat",)))


# Catch-up details ---------------------------------------------------------------------------------


def test_a_resumed_letter_keeps_the_plans_diaries_and_causes(tmp_path) -> None:
    provider = ScriptedProvider({"letter": fail_on_call("letter", 1)})
    game, world, clock = make_game(tmp_path, provider)
    clock.now += timedelta(days=3)
    with pytest.raises(LLMError):
        game.open_session(world)

    report = game.open_session(world)

    (letter_request, retry) = [r for r in provider.requests if r.task == "letter"]
    assert len(retry.context["diaries"]) == 3 and retry.context["diaries"] == letter_request.context["diaries"]
    (letter,) = game.snapshot(world)["letters"]
    assert len(letter["causes"]) == 3 and len(report["event_ids"]) == 3
    assert [c["id"] for c in letter["causes"]] == report["event_ids"]


def test_chatting_between_a_failure_and_the_retry_keeps_the_plan_intact(tmp_path) -> None:
    game, world, clock = make_game(tmp_path, ScriptedProvider({"letter": fail_on_call("letter", 1)}))
    clock.now += timedelta(days=3)
    with pytest.raises(LLMError):
        game.open_session(world)

    game.send_message(world, "你好")
    report = game.open_session(world)

    assert (report["days_away"], report["simulated_days"]) == (3, 3)
    assert game.snapshot(world)["time"]["day"] == 4
    assert game.open_session(world)["simulated_days"] == 0


@pytest.mark.parametrize("step", ["day", "sleep", "letter"])
def test_each_catch_up_step_commits_atomically(tmp_path, monkeypatch, step) -> None:
    game, world, clock = make_game(tmp_path)
    clock.now += timedelta(days=10)
    real_save, armed = Store.save_state, {"fire": True}

    def due(state: dict) -> bool:
        plan = state.get("catch_up")
        if step == "day":
            return plan is not None and plan["done"] == 1
        if step == "sleep":
            return plan is not None and plan["sleep_written"]
        return plan is None and state["day"] == 8

    def flaky(self, world_id, state):
        if armed["fire"] and due(state):
            armed["fire"] = False
            raise RuntimeError("disk full")
        return real_save(self, world_id, state)

    monkeypatch.setattr(Store, "save_state", flaky)
    with pytest.raises(RuntimeError, match="disk full"):
        game.open_session(world)
    partial = count_kinds(game.snapshot(world))
    assert partial.get("offscreen_day", 0) == (0 if step == "day" else 7)
    assert partial.get("sleep", 0) == (0 if step in ("day", "sleep") else 1)
    assert game.snapshot(world)["letters"] == []

    game.open_session(world)

    snap = game.snapshot(world)
    assert snap["time"]["day"] == 8
    assert count_kinds(snap)["offscreen_day"] == 7 and count_kinds(snap)["sleep"] == 1
    assert len(snap["letters"]) == 1


def test_a_catch_up_that_makes_no_progress_fails_instead_of_looping(tmp_path, monkeypatch) -> None:
    game, world, clock = make_game(tmp_path)
    clock.now += timedelta(days=2)
    monkeypatch.setattr(Game, "_simulate_offscreen_day", lambda self, world_id: None)

    with pytest.raises(RuntimeError, match="no progress"):
        game.open_session(world)


def test_simulate_absence_finishes_a_pending_catch_up_first(tmp_path) -> None:
    game, world, clock = make_game(
        tmp_path, ScriptedProvider({"offscreen_day": fail_on_call("offscreen_day", 2)})
    )
    clock.now += timedelta(days=3)
    with pytest.raises(LLMError):
        game.open_session(world)

    report = game.simulate_absence(world, 2)

    # The pending 3 days were finished first; the report covers the 2 new days.
    assert (report["days_away"], report["simulated_days"]) == (2, 2)
    snap = game.snapshot(world)
    assert snap["time"]["day"] == 6
    assert count_kinds(snap)["offscreen_day"] == 5 and len(snap["letters"]) == 2


def test_a_clock_that_changed_between_naive_and_aware_does_not_wedge_the_plan(tmp_path) -> None:
    naive = datetime(2026, 9, 1, 21, 0)
    first = Game(tmp_path / "world.db", FakeProvider(), load_blueprint(), clock=lambda: naive)
    world = first.current_world()  # last_seen_at is stored without a time zone
    aware = FixedClock()
    aware.now = naive.astimezone() + timedelta(days=3)  # a naive value means local time
    second = Game(tmp_path / "world.db", FakeProvider(), load_blueprint(), clock=aware)

    report = second.open_session(world)

    assert report["simulated_days"] == 3
    assert second.open_session(world)["simulated_days"] == 0


def test_activity_after_a_failure_is_not_rolled_back_by_finishing_the_plan(tmp_path) -> None:
    game, world, clock = make_game(tmp_path, ScriptedProvider({"letter": fail_on_call("letter", 1)}))
    clock.now += timedelta(days=3)
    with pytest.raises(LLMError):
        game.open_session(world)

    clock.now += timedelta(days=1)
    game.send_message(world, "对不起，我回来了")  # she saw you today
    report = game.open_session(world)

    assert (report["days_away"], report["simulated_days"]) == (3, 3)
    assert game.snapshot(world)["time"]["day"] == 4


def test_the_dev_flag_reaches_the_request_handler(tmp_path, monkeypatch) -> None:
    import prototype.server as server

    handlers = []

    class FakeHttpd:
        def __init__(self, address, handler):
            handlers.append(handler)

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    monkeypatch.setattr(server, "ThreadingHTTPServer", FakeHttpd)
    game, _, _ = make_game(tmp_path)

    server.serve(game, "127.0.0.1", 0)
    server.serve(game, "127.0.0.1", 0, dev=True)

    assert [h.dev_enabled for h in handlers] == [False, True]


def test_an_unreadable_world_is_reported_before_anything_is_written(tmp_path) -> None:
    game, world, clock = make_game(tmp_path)
    stale = load_blueprint()
    stale["blueprint_version"] = 99
    with closing(sqlite3.connect(tmp_path / "world.db")) as conn, conn:
        conn.execute("UPDATE worlds SET blueprint = ? WHERE id = ?", (json.dumps(stale), world))
        before = conn.execute("SELECT version, state FROM worlds WHERE id = ?", (world,)).fetchone()
    reopened = Game(tmp_path / "world.db", FakeProvider(), load_blueprint(), clock=clock)
    clock.now += timedelta(days=3)

    for call in (
        lambda: reopened.open_session(world),
        lambda: reopened.simulate_absence(world, 2),
        lambda: reopened.read_letter(world, "letter-x"),
    ):
        with pytest.raises(NotFound, match="blueprint"):
            call()

    with closing(sqlite3.connect(tmp_path / "world.db")) as conn:
        assert conn.execute("SELECT version, state FROM worlds WHERE id = ?", (world,)).fetchone() == before


def test_a_blueprint_this_build_cannot_read_is_rejected_at_start(tmp_path) -> None:
    future = load_blueprint()
    future["blueprint_version"] = 2

    with pytest.raises(ValueError, match="blueprint_version"):
        Game(tmp_path / "world.db", FakeProvider(), future)


# Provider selection from the environment -----------------------------------------------------


def test_marginalia_variables_select_the_provider_and_model() -> None:
    provider = provider_from_env(
        env={"MARGINALIA_LLM": "openai", "MARGINALIA_MODEL": "m1", "OPENAI_API_KEY": "k"}
    )

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "m1"


def test_the_old_agenttown_variables_still_select_the_provider_and_model() -> None:
    provider = provider_from_env(
        env={"AGENTTOWN_LLM": "anthropic", "AGENTTOWN_MODEL": "m0", "ANTHROPIC_API_KEY": "k"}
    )

    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "m0"


def test_marginalia_variables_win_over_the_old_names() -> None:
    provider = provider_from_env(
        env={
            "MARGINALIA_LLM": "anthropic",
            "AGENTTOWN_LLM": "fake",
            "MARGINALIA_MODEL": "new",
            "AGENTTOWN_MODEL": "old",
            "ANTHROPIC_API_KEY": "k",
        }
    )

    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "new"


def test_a_missing_openai_model_names_the_marginalia_variable() -> None:
    with pytest.raises(LLMError, match="MARGINALIA_MODEL"):
        provider_from_env(env={"MARGINALIA_LLM": "openai", "OPENAI_API_KEY": "k"})
