from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventId:
    """A playable-runtime event identifier backed by UUIDv7."""

    value: uuid.UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, uuid.UUID):
            raise ValueError("EventId requires a UUID value")
        if self.value.version != 7:
            raise ValueError("EventId requires a UUIDv7 value")

    @classmethod
    def new(cls) -> EventId:
        try:
            uuid7 = uuid.uuid7
        except AttributeError as error:
            raise RuntimeError("EventId.new requires Python 3.14 uuid.uuid7") from error
        return cls(uuid7())

    @classmethod
    def from_string(cls, value: str) -> EventId:
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("EventId requires a canonical UUIDv7 string") from error
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)
