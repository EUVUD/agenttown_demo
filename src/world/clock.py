from __future__ import annotations

import functools
from dataclasses import dataclass
from enum import IntEnum

from src.config import get_config


def _time_config() -> dict:
    """Return the ``world.time`` config section.

    Resolved lazily so importing this module has no side effects: ``Stage`` and
    ``TimeState`` parsing/ordering need no configuration, and callers that only
    use them (tests, read models, the director layer) must not trigger a
    config load.
    """
    return get_config()["world"]["time"]


class Stage(IntEnum):
    """Ordered phases within a single simulated week."""

    BEGIN = 0
    PLAN = 1
    BEFORE_CONTACT = 2  # God Model events + Agent responses
    CONTACT = 3
    AFTER_CONTACT = 4  # Settle activities from the CONTACT stage
    ACTIVITY = 5
    REVIEW = 6
    SETTLE = 7


@functools.total_ordering
@dataclass
class TimeState:
    year: int
    week: int
    stage: Stage
    day: int = 0
    slot: int = 0

    def __str__(self) -> str:
        """Convert this TimeState to its string representation.

        - ACTIVITY stage: "Y{year}-W{week}-activity-D{day}"
        - CONTACT stage:  "Y{year}-W{week}-contact-S{slot}"
        - Other stages:   "Y{year}-W{week}-{stage}"
        """
        parts = [f"Y{self.year}", f"W{self.week:02d}", self.stage.name.lower()]
        if self.stage == Stage.CONTACT:
            parts.append(f"S{self.slot}")
        elif self.stage == Stage.ACTIVITY:
            parts.append(f"D{self.day}")
        return "-".join(parts)

    def repr_week(self) -> str:
        """Return week-level string representation: Y{year}-W{week}."""
        return f"Y{self.year}-W{self.week:02d}"

    @classmethod
    def from_string(cls, s: str) -> TimeState:
        """Parse a TimeState object back from its string representation.

        Supported formats:
        - "Y{year}-W{week}-{stage}" (e.g. "Y2025-W01-plan")
        - "Y{year}-W{week}-{stage}-D{day}" (e.g. "Y2025-W01-activity-D3")
        - "Y{year}-W{week}-{stage}-S{slot}" (e.g. "Y2025-W01-contact-S6")
        """
        parts = s.split("-")

        if len(parts) < 3:
            raise ValueError(
                f"Invalid TimeState string: expected at least 3 parts (Y, W, Stage). Got: {s}"
            )

        # 1. Parse Year
        if not parts[0].startswith("Y"):
            raise ValueError(
                f"Invalid TimeState string: missing 'Y' prefix. Got: {parts[0]}"
            )
        year = int(parts[0][1:])

        # 2. Parse Week
        if not parts[1].startswith("W"):
            raise ValueError(
                f"Invalid TimeState string: missing 'W' prefix. Got: {parts[1]}"
            )
        week = int(parts[1][1:])

        # 3. Parse Stage / Day / Slot
        stage: Stage
        day = 0
        slot = 0

        p2 = parts[2]

        stage = Stage[p2.upper()]
        extras = parts[3:]
        for part in extras:
            if part.startswith("D"):
                day = int(part[1:])
            elif part.startswith("S"):
                slot = int(part[1:])

        return cls(year=year, week=week, stage=stage, day=day, slot=slot)

    def __eq__(self, other: object) -> bool:
        """Return True if all time components are equal."""
        if not isinstance(other, TimeState):
            return NotImplemented
        return (
            self.year == other.year
            and self.week == other.week
            and self.stage == other.stage
            and self.day == other.day
            and self.slot == other.slot
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, TimeState):
            return NotImplemented

        if self.year != other.year:
            return self.year < other.year

        if self.week != other.week:
            return self.week < other.week

        if self.stage != other.stage:
            return self.stage < other.stage

        if self.stage == Stage.CONTACT:
            if self.slot != other.slot:
                return self.slot < other.slot
        elif self.stage == Stage.ACTIVITY:
            if self.day != other.day:
                return self.day < other.day

        return False

    @staticmethod
    def get_year_begin(year: int) -> str:
        """Return the year-begin time string: Y{year}-W00-begin.

        This represents the start of a year, before any week has begun.
        Used for Return/Advantage calculations where we need a baseline
        before the first reward is calculated.
        """
        return f"Y{year}-W00-begin"

    def minus_x_weeks(self, x: int) -> TimeState:
        """Return the BEGIN of (current_week - x + 1).

        Args:
            x: Number of weeks. Must be >= 1.
               x=1 → current week's BEGIN
               x=2 → previous week's BEGIN
        """
        assert x >= 1, f"minus_x_weeks requires x >= 1, got {x}"

        year = self.year
        week = self.week - (x - 1)

        while week <= 0:
            year -= 1
            week += _time_config()["n_week"]

        return TimeState(year=year, week=week, stage=Stage.BEGIN)


class Clock:
    """Discrete world clock: year → week → stage → day/slot.

    Keep it dumb and explicit. World drives it.
    """

    def __init__(self, *, start_year: int, start_week: int) -> None:
        self._year = start_year
        self._week = start_week
        self._stage: Stage = Stage.BEGIN
        self._day: int = 0
        self._slot: int = 0

    def set_year(self, year: int) -> None:
        self._year = year

    def set_week(self, week: int) -> None:
        self._week = week
        self._stage = Stage.BEGIN
        self._day = 0
        self._slot = 0

    def set_stage(self, stage: Stage) -> None:
        self._stage = stage
        # Reset granular fields when stage changes
        self._day = 0
        self._slot = 0

    def set_day(self, day: int) -> None:
        self._day = day

    def set_slot(self, slot: int) -> None:
        self._slot = slot

    def get_time(self) -> TimeState:
        return TimeState(self._year, self._week, self._stage, self._day, self._slot)

    # Utilities for contact stage -------------------------------------------
    def prev_contact_slot(self) -> TimeState:
        """Return CONTACT slot reference based on current stage.

        Rules:
        - If current stage is CONTACT:
            - slot > 1: same year/week, slot-1.
            - slot == 1: previous week's last contact slot (wrap year if needed).
        - If current stage is AFTER_CONTACT: return current week's last
          contact slot (Stage.CONTACT, slot=n_contact_slot).
        - Otherwise: invalid usage.
        """
        time_cfg = _time_config()
        n_slot = time_cfg["n_contact_slot"]
        n_week = time_cfg["n_week"]
        y, w, s = self._year, self._week, self._slot

        if self._stage == Stage.CONTACT:
            if s > 1:
                s = s - 1
            else:
                s = n_slot
                if w > 1:
                    w = w - 1
                else:
                    w = n_week
                    y = y - 1
            return TimeState(year=y, week=w, stage=Stage.CONTACT, slot=s)
        elif self._stage == Stage.AFTER_CONTACT:
            return TimeState(year=y, week=w, stage=Stage.CONTACT, slot=n_slot)
        else:
            raise AssertionError(
                "prev_contact_slot only valid at CONTACT/AFTER_CONTACT stage"
            )

    @property
    def year(self) -> int:
        return self._year

    @property
    def week(self) -> int:
        return self._week

    @property
    def stage(self) -> Stage:
        return self._stage


if __name__ == "__main__":
    print("--- 1. Test TimeState string conversion (__str__) ---")
    t1 = TimeState(2025, 1, Stage.PLAN)
    t1_bc = TimeState(2025, 1, Stage.BEFORE_CONTACT)
    t2 = TimeState(2025, 1, Stage.ACTIVITY, day=3)
    t3 = TimeState(2025, 1, Stage.ACTIVITY, day=3, slot=5)
    t4 = TimeState(2025, 1, Stage.REVIEW, slot=2)  # day is None

    print(t1)
    print(t1_bc)
    print(t2)
    print(t3)
    print(t4)

    print("\n--- 2. Test TimeState comparison (logical order) ---")
    # Create in chronological order
    ts1 = TimeState(2025, 1, Stage.PLAN)
    ts1_bc = TimeState(2025, 1, Stage.BEFORE_CONTACT)
    ts2 = TimeState(2025, 1, Stage.CONTACT)
    ts3 = TimeState(2025, 1, Stage.ACTIVITY)  # day=None, slot=None

    ts4 = TimeState(2025, 1, Stage.ACTIVITY, day=1, slot=1)
    # ts5 = TimeState(2025, 1, Stage.ACTIVITY, day=1, slot=2)
    ts6 = TimeState(2025, 1, Stage.ACTIVITY, day=2, slot=1)
    ts7 = TimeState(2025, 1, Stage.REVIEW)
    ts8 = TimeState(2025, 2, Stage.PLAN)
    ts9 = TimeState(2026, 1, Stage.PLAN)

    print(f"[{ts1}] < [{ts1_bc}] (PLAN < BEFORE_CONTACT): {ts1 < ts1_bc}")
    print(f"[{ts1_bc}] < [{ts2}] (BEFORE_CONTACT < CONTACT): {ts1_bc < ts2}")
    print(f"[{ts2}] < [{ts3}] (different stage): {ts2 < ts3}")
    print(f"[{ts3}] < [{ts4}] (None day < day 1): {ts3 < ts4}")
    # print(f"[{ts4}] < [{ts5}] (different slot): {ts4 < ts5}")
    # print(f"[{ts5}] < [{ts6}] (different day): {ts5 < ts6}")
    print(f"[{ts6}] < [{ts7}] (different stage): {ts6 < ts7}")
    print(f"[{ts7}] < [{ts8}] (different week): {ts7 < ts8}")
    print(f"[{ts8}] < [{ts9}] (different year): {ts8 < ts9}")

    # Test > and ==
    print(f"[{ts9}] > [{ts1}] (different year): {ts9 > ts1}")
    t_eq1 = TimeState(2030, 10, Stage.PLAN)
    t_eq2 = TimeState(2030, 10, Stage.PLAN)
    print(f"[{t_eq1}] == [{t_eq2}] (equal): {t_eq1 == t_eq2}")
    print(f"[{t_eq1}] != [{ts1}] (not equal): {t_eq1 != ts1}")

    print("\n--- 3. Test list sorting ---")
    # Create an unsorted list
    shuffled_list = [ts8, ts1, ts9, ts3, ts7, ts4, ts2, ts6, ts1_bc]

    print("Before sort:")
    for t in shuffled_list:
        print(f"  {t}")

    # Sort
    sorted_list = sorted(shuffled_list)

    print("\nAfter sort:")
    for t in sorted_list:
        print(f"  {t}")

    # Verify order
    assert sorted_list == [ts1, ts1_bc, ts2, ts3, ts4, ts6, ts7, ts8, ts9]
    print("\nSort verification passed!")

    print("\n--- 4. Test from_string (new/old formats) ---")
    s_plan = "Y2025-W01-plan"
    s_bc = "Y2025-W01-before_contact"
    s_act = "Y2025-W01-activity-D3"
    s_con = "Y2025-W01-contact-S6"
    s_sum = "Y2025-W01-review"
    s_full = "Y2030-W50-activity-D1-S5"

    t_plan = TimeState.from_string(s_plan)
    t_bc = TimeState.from_string(s_bc)
    t_act = TimeState.from_string(s_act)
    t_con = TimeState.from_string(s_con)
    t_sum = TimeState.from_string(s_sum)
    t_full = TimeState.from_string(s_full)

    print(f"'{s_plan}' -> {t_plan}")
    print(f"'{s_bc}' -> {t_bc}")
    print(f"'{s_act}'  -> {t_act}")
    print(f"'{s_con}'  -> {t_con}")
    print(f"'{s_sum}'  -> {t_sum}")
    print(f"'{s_full}' -> {t_full}")

    # Verify
    assert t_plan == TimeState(2025, 1, Stage.PLAN, 0, 0)
    assert t_bc == TimeState(2025, 1, Stage.BEFORE_CONTACT, 0, 0)
    assert t_act == TimeState(2025, 1, Stage.ACTIVITY, 3, 0)
    assert t_con == TimeState(2025, 1, Stage.CONTACT, 0, 6)
    assert t_sum == TimeState(2025, 1, Stage.REVIEW, 0, 0)
    assert t_full == TimeState(2030, 50, Stage.ACTIVITY, 1, 5)

    # Verify round-trip
    # Note: t_full loses slot on round-trip because __str__ for ACTIVITY stage is lossy
    assert str(t_plan) == s_plan
    assert str(t_bc) == s_bc
    assert str(t_act) == "Y2025-W01-activity-D3"
    assert str(t_con) == s_con
    assert str(t_sum) == s_sum
    assert str(t_full) == "Y2030-W50-activity-D1"  # lossy: slot dropped

    print("\nfrom_string parsing verification passed!")
