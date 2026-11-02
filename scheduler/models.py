"""Data types for the scheduler, and conversion to and from the brief's JSON formats.

This is the only module that deals with raw JSON values and timestamp strings.
Input is parsed and validated here on the way in, and formatted here on the way out,
so the rest of the code works purely with typed objects and UTC datetimes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class InputError(ValueError):
    """Raised when user-supplied input (a file or a flag) is invalid."""


# --- Timestamps -------------------------------------------------------------


def parse_time(value: Any, field: str) -> datetime:
    """Parse an ISO 8601 timestamp that includes a timezone into a UTC datetime."""
    if not isinstance(value, str):
        raise InputError(f"{field}: expected a timestamp string, got {value!r}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise InputError(f"{field}: invalid timestamp {value!r}") from None
    if parsed.tzinfo is None:
        raise InputError(f"{field}: timestamp {value!r} has no timezone (e.g. add 'Z')")
    return parsed.astimezone(timezone.utc)


def format_time(dt: datetime) -> str:
    """Format a datetime in UTC the same way as the brief, e.g. 2026-11-06T17:00:00Z."""
    return dt.astimezone(timezone.utc).strftime(TIME_FORMAT)


# --- Types --------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One person on call over the half-open interval [start, end).

    Used both for overrides (input) and for the rendered schedule (output),
    since they have exactly the same shape.
    """

    user: str
    start: datetime
    end: datetime

    def covers(self, t: datetime) -> bool:
        """Whether instant t falls inside this entry (start inclusive, end exclusive)."""
        return self.start <= t < self.end

    @classmethod
    def from_json(cls, data: Any, where: str) -> "Entry":
        """Build an Entry from {"user", "start_at", "end_at"}, validating every field."""
        user = _get(data, "user", where)
        if not _is_name(user):
            raise InputError(f"{where}.user: expected a non-empty string, got {user!r}")
        start = parse_time(_get(data, "start_at", where), f"{where}.start_at")
        end = parse_time(_get(data, "end_at", where), f"{where}.end_at")
        if start >= end:
            raise InputError(f"{where}: start_at must be before end_at")
        return cls(user, start, end)

    def to_json(self) -> dict[str, str]:
        """Convert to the brief's output format."""
        return {
            "user": self.user,
            "start_at": format_time(self.start),
            "end_at": format_time(self.end),
        }


@dataclass(frozen=True)
class Schedule:
    """A rotation: users take turns, each covering one interval, starting at handover_start."""

    users: tuple[str, ...]
    handover_start: datetime
    interval: timedelta

    @classmethod
    def from_json(cls, data: Any) -> "Schedule":
        """Build a Schedule from the brief's schedule JSON, validating every field."""
        users = _get(data, "users", "schedule")
        if not isinstance(users, list) or not users or not all(map(_is_name, users)):
            raise InputError("schedule.users: expected a non-empty list of user names")

        start = parse_time(
            _get(data, "handover_start_at", "schedule"), "schedule.handover_start_at"
        )

        days = _get(data, "handover_interval_days", "schedule")
        # bool is a subclass of int in Python, so rule it out explicitly (true == 1 day).
        if isinstance(days, bool) or not isinstance(days, (int, float)) or days <= 0:
            raise InputError(
                f"schedule.handover_interval_days: expected a positive number, got {days!r}"
            )

        return cls(tuple(users), start, timedelta(days=days))


def parse_overrides(data: Any) -> list[Entry]:
    """Build the list of overrides from the overrides JSON (an array of entries)."""
    if not isinstance(data, list):
        raise InputError("overrides: expected a JSON array")
    return [Entry.from_json(item, f"overrides[{i}]") for i, item in enumerate(data)]


# --- Helpers ------------------------------------------------------------------


def _get(data: Any, key: str, where: str) -> Any:
    """Fetch a required key from a JSON object, with a clear error if it's missing."""
    if not isinstance(data, dict):
        raise InputError(f"{where}: expected a JSON object, got {type(data).__name__}")
    if key not in data:
        raise InputError(f"{where}: missing required field {key!r}")
    return data[key]


def _is_name(value: Any) -> bool:
    """Whether value is usable as a user name (a non-empty string)."""
    return isinstance(value, str) and value.strip() != ""
