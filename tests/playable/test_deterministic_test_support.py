from __future__ import annotations

import json
import socket
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes import FakeClock, FakeLLM, UnexpectedPromptError
from tests.support.school_fixture import load_school_fixture


def test_fake_clock_only_uses_explicit_timezone_aware_time() -> None:
    start = datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)

    clock.advance(timedelta(minutes=20))
    assert clock.now() == datetime(2026, 8, 11, 9, 20, tzinfo=timezone.utc)

    replacement = datetime(2026, 8, 12, 9, 30, tzinfo=timezone(timedelta(hours=8)))
    clock.set(replacement)
    assert clock.now() == replacement

    with pytest.raises(ValueError, match="timezone-aware"):
        FakeClock(datetime(2026, 8, 11, 9, 0))


def test_fake_llm_records_calls_and_returns_independent_scripted_data() -> None:
    scripted_response = {
        "action": "attend_class",
        "participants": ["protagonist", "npc-01"],
    }
    fake_llm = FakeLLM({"arrival": scripted_response})

    first_response = fake_llm.complete("arrival")
    first_response["participants"].append("unexpected")
    second_response = fake_llm.complete("arrival")

    assert second_response == scripted_response
    assert fake_llm.calls == ["arrival", "arrival"]

    with pytest.raises(UnexpectedPromptError, match="departure"):
        fake_llm.complete("departure")

    assert fake_llm.calls == ["arrival", "arrival", "departure"]


def test_school_fixture_has_small_stable_shape_and_fresh_values() -> None:
    first_fixture = load_school_fixture()
    second_fixture = load_school_fixture()

    assert first_fixture["protagonist"]["id"] == "protagonist"
    assert len(first_fixture["npcs"]) == 6
    assert len(first_fixture["locations"]) == 5

    first_fixture["npcs"][0]["name"] = "mutated"
    assert second_fixture["npcs"][0]["name"] != "mutated"


def test_temporary_database_is_file_backed_and_enforces_foreign_keys(
    temporary_database: Any, tmp_path: Path
) -> None:
    assert temporary_database.path.name == "world.sqlite3"
    assert tmp_path in temporary_database.path.parents
    assert temporary_database.path.exists()
    assert temporary_database.connection.execute("PRAGMA foreign_keys").fetchone() == (1,)

    temporary_database.connection.execute(
        "CREATE TABLE probe_entry (message TEXT NOT NULL)"
    )
    temporary_database.connection.execute(
        "INSERT INTO probe_entry (message) VALUES (?)", ("ready",)
    )
    temporary_database.connection.commit()

    with sqlite3.connect(temporary_database.path) as verification_connection:
        rows = verification_connection.execute(
            "SELECT message FROM probe_entry"
        ).fetchall()

    assert rows == [("ready",)]


def test_same_scripted_inputs_produce_same_normalized_output_and_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "create_connection", _forbid_network)

    first_outcome = _run_deterministic_probe(tmp_path / "first")
    second_outcome = _run_deterministic_probe(tmp_path / "second")

    assert first_outcome == second_outcome
    assert first_outcome["rows"] == [
        ("2026-08-11T09:00:00+00:00", "protagonist", '{"action":"attend_class"}')
    ]


def _run_deterministic_probe(directory: Path) -> dict[str, Any]:
    directory.mkdir()
    school = load_school_fixture()
    clock = FakeClock(datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc))
    fake_llm = FakeLLM({"protagonist arrives": {"action": "attend_class"}})
    response = fake_llm.complete("protagonist arrives")
    normalized_response = json.dumps(response, sort_keys=True, separators=(",", ":"))

    with sqlite3.connect(directory / "world.sqlite3") as connection:
        connection.execute(
            "CREATE TABLE probe_event (occurred_at TEXT, actor_id TEXT, response TEXT)"
        )
        connection.execute(
            "INSERT INTO probe_event VALUES (?, ?, ?)",
            (clock.now().isoformat(), school["protagonist"]["id"], normalized_response),
        )
        rows = connection.execute(
            "SELECT occurred_at, actor_id, response FROM probe_event ORDER BY rowid"
        ).fetchall()

    return {
        "time": clock.now().isoformat(),
        "actor": school["protagonist"]["id"],
        "response": normalized_response,
        "rows": rows,
    }


def _forbid_network(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("deterministic test support must not use the network")
