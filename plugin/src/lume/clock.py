"""Clock seam - injected so date-stamping is deterministic and testable.

The engine never calls `datetime.date.today()` directly; it asks an injected
Clock. Production uses SystemClock; tests inject FixedClock.
"""
import datetime
from typing import Protocol


class Clock(Protocol):
    def today(self) -> datetime.date: ...


class SystemClock:
    """Real wall-clock date."""

    def today(self) -> datetime.date:
        return datetime.date.today()


class FixedClock:
    """A clock pinned to a fixed date - for deterministic tests."""

    def __init__(self, date: datetime.date) -> None:
        self._date = date

    def today(self) -> datetime.date:
        return self._date
