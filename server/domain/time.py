from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


@dataclass(frozen=True, order=True, slots=True)
class WorldDay:
    """A positive user-facing playable world day."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError("WorldDay requires a positive integer")
        if self.value < 1:
            raise ValueError("WorldDay requires a value >= 1")

    def next(self) -> WorldDay:
        return WorldDay(self.value + 1)

    def to_int(self) -> int:
        return self.value

    def __int__(self) -> int:
        return self.value


class TimeSlot(IntEnum):
    """The four ordered playable slots inside one world day."""

    SLOT_1 = 1
    SLOT_2 = 2
    SLOT_3 = 3
    SLOT_4 = 4

    @classmethod
    def from_int(cls, value: int) -> TimeSlot:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("TimeSlot requires an integer from 1 through 4")
        try:
            return cls(value)
        except ValueError:
            raise ValueError("TimeSlot requires an integer from 1 through 4") from None

    def to_int(self) -> int:
        return int(self)


@dataclass(frozen=True, order=True, slots=True)
class WorldTime:
    """A comparable playable moment: world day plus slot."""

    day: WorldDay
    slot: TimeSlot

    def __post_init__(self) -> None:
        if not isinstance(self.day, WorldDay):
            raise ValueError("WorldTime requires a WorldDay")
        if not isinstance(self.slot, TimeSlot):
            raise ValueError("WorldTime requires a TimeSlot")

    @classmethod
    def from_values(cls, *, day: int, slot: int) -> WorldTime:
        return cls(day=WorldDay(day), slot=TimeSlot.from_int(slot))

    def next(self) -> WorldTime:
        if self.slot == TimeSlot.SLOT_4:
            return WorldTime(day=self.day.next(), slot=TimeSlot.SLOT_1)
        return WorldTime(day=self.day, slot=TimeSlot.from_int(self.slot.to_int() + 1))

    def to_dict(self) -> dict[str, int]:
        return {
            "day": self.day.to_int(),
            "slot": self.slot.to_int(),
        }
