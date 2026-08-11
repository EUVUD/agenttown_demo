from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any


class UnexpectedPromptError(LookupError):
    """Raised when a fake LLM receives a prompt that was not scripted."""


class FakeClock:
    """A clock whose time advances only through explicit test actions."""

    def __init__(self, current_time: datetime) -> None:
        self._current_time = self._require_timezone_aware(current_time)

    def now(self) -> datetime:
        return self._current_time

    def set(self, current_time: datetime) -> None:
        self._current_time = self._require_timezone_aware(current_time)

    def advance(self, duration: timedelta) -> None:
        self._current_time += duration

    @staticmethod
    def _require_timezone_aware(current_time: datetime) -> datetime:
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("FakeClock requires a timezone-aware datetime")
        return current_time


class FakeLLM:
    """A scripted LLM substitute that records exact prompt requests."""

    def __init__(self, scripted_responses: Mapping[str, Any]) -> None:
        self._scripted_responses = deepcopy(dict(scripted_responses))
        self._calls: list[str] = []

    @property
    def calls(self) -> list[str]:
        return list(self._calls)

    def complete(self, prompt: str) -> Any:
        self._calls.append(prompt)
        if prompt not in self._scripted_responses:
            raise UnexpectedPromptError(f"Unexpected fake LLM prompt: {prompt!r}")
        return deepcopy(self._scripted_responses[prompt])
