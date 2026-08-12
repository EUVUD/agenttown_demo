from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class Version:
    """A non-negative aggregate version."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError("Version requires a non-negative integer")
        if self.value < 0:
            raise ValueError("Version requires a value >= 0")

    def next(self) -> Version:
        return Version(self.value + 1)

    def to_int(self) -> int:
        return self.value

    def __int__(self) -> int:
        return self.value
