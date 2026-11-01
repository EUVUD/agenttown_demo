from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from server.domain import EventId, TimeSlot, Version, WorldDay, WorldTime
from tests.support.fresh_interpreter import legacy_modules_loaded_by


UUID7_TEXT = "0194fdcb-1c47-7a09-b52c-561154de0b4a"


def test_world_time_advances_from_final_slot_to_next_day() -> None:
    time = WorldTime(day=WorldDay(1), slot=TimeSlot.SLOT_4)

    assert time.next() == WorldTime(day=WorldDay(2), slot=TimeSlot.SLOT_1)
    assert time.to_dict() == {"day": 1, "slot": 4}


def test_world_time_rejects_invalid_boundaries() -> None:
    with pytest.raises(ValueError, match="WorldDay"):
        WorldDay(0)

    with pytest.raises(ValueError, match="TimeSlot"):
        TimeSlot.from_int(5)

    with pytest.raises(ValueError, match="TimeSlot"):
        WorldTime.from_values(day=1, slot=0)


def test_world_time_sorts_by_day_then_slot() -> None:
    unordered = [
        WorldTime.from_values(day=2, slot=1),
        WorldTime.from_values(day=1, slot=4),
        WorldTime.from_values(day=1, slot=2),
    ]

    assert sorted(unordered) == [
        WorldTime.from_values(day=1, slot=2),
        WorldTime.from_values(day=1, slot=4),
        WorldTime.from_values(day=2, slot=1),
    ]


def test_event_id_uses_uuid7_and_detects_duplicate_values() -> None:
    first = EventId.from_string(UUID7_TEXT)
    duplicate = EventId.from_string(UUID7_TEXT)

    assert first == duplicate
    assert len({first, duplicate}) == 1
    assert str(first) == UUID7_TEXT
    assert EventId.new().value.version == 7


def test_event_id_rejects_non_uuid7_values() -> None:
    with pytest.raises(ValueError, match="UUIDv7"):
        EventId.from_string(str(uuid4()))


def test_version_advances_without_mutating_original() -> None:
    empty = Version(0)
    first = empty.next()

    assert empty.to_int() == 0
    assert first == Version(1)
    assert first.to_int() == 1


def test_version_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="Version"):
        Version(-1)


def test_domain_value_objects_are_immutable() -> None:
    day = WorldDay(1)

    with pytest.raises(FrozenInstanceError):
        day.value = 2  # type: ignore[misc]


def test_domain_import_does_not_load_legacy_runtime_modules() -> None:
    assert legacy_modules_loaded_by("import server.domain") == set()
