"""Shorthands so tests read like timelines, e.g. e("alice", "11-06 17:00", "11-09 17:00")."""

from datetime import datetime, timedelta, timezone

from scheduler.models import Entry, Schedule


def t(when: str) -> datetime:
    """A UTC instant in 2026, written as "MM-DD HH:MM"."""
    return datetime.strptime(f"2026-{when}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def e(user: str, start: str, end: str) -> Entry:
    """An Entry from "MM-DD HH:MM" start and end times."""
    return Entry(user, t(start), t(end))


def weekly(*users: str, start: str = "11-06 17:00") -> Schedule:
    """A schedule that hands over every 7 days, like the brief's example."""
    return Schedule(tuple(users), t(start), timedelta(days=7))


# The schedule from the brief: alice -> bob -> charlie, weekly from Fri 6 Nov 17:00.
BRIEF = weekly("alice", "bob", "charlie")
