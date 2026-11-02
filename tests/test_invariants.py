"""Property tests: rules that must hold for ANY valid input, checked on random inputs.

The example tests in test_core.py check cases we thought of. These generate many
random schedules, overrides and windows (seeded, so every failure is reproducible
with its seed) and check that the output always obeys the rules below.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest

from scheduler.core import render_schedule
from scheduler.models import Entry, Schedule

BASE = datetime(2026, 11, 1, tzinfo=timezone.utc)
USERS = ["alice", "bob", "charlie", "dave"]


def hours(n: int) -> datetime:
    return BASE + timedelta(hours=n)


def random_case(rng: random.Random):
    """A random schedule, non-overlapping overrides and window, all on whole hours."""
    schedule = Schedule(
        users=tuple(rng.sample(USERS, rng.randint(1, len(USERS)))),
        handover_start=hours(rng.randint(0, 48)),
        interval=timedelta(hours=rng.choice([1, 12, 24, 36, 168])),
    )

    # Overrides: sort distinct random points and pair them up (p0,p1), (p2,p3), ...
    # so they can't overlap. Starting at handover_start matches the brief's assumption.
    first = int((schedule.handover_start - BASE) / timedelta(hours=1))
    points = sorted(rng.sample(range(first, first + 24 * 30), 2 * rng.randint(0, 8)))
    overrides = [
        Entry(rng.choice(USERS + ["zoe"]), hours(a), hours(b))
        for a, b in zip(points[::2], points[1::2])
    ]

    frm = hours(rng.randint(0, 24 * 25))
    until = frm + timedelta(hours=rng.randint(1, 24 * 21))
    return schedule, overrides, frm, until


def expected_user_at(schedule: Schedule, overrides: list[Entry], t: datetime) -> str | None:
    """Who should be on call at instant t, straight from the brief's definition.

    This answers for ONE instant, without building any intervals, so it's an
    independent check on the pipeline's output.
    """
    for override in overrides:
        if override.covers(t):
            return override.user
    if t < schedule.handover_start:
        return None
    shifts_elapsed = (t - schedule.handover_start) // schedule.interval
    return schedule.users[shifts_elapsed % len(schedule.users)]


def actual_user_at(entries: list[Entry], t: datetime) -> str | None:
    """Who the rendered output says is on call at instant t."""
    return next((entry.user for entry in entries if entry.covers(t)), None)


@pytest.mark.parametrize("seed", range(200))
def test_output_obeys_invariants(seed):
    rng = random.Random(seed)
    schedule, overrides, frm, until = random_case(rng)

    entries = render_schedule(schedule, overrides, frm, until)

    for entry in entries:
        assert entry.start < entry.end, "no empty or backwards entries"
        assert frm <= entry.start and entry.end <= until, "everything inside the window"

    for previous, current in zip(entries, entries[1:]):
        assert previous.end <= current.start, "sorted, with no overlaps"
        assert not (previous.user == current.user and previous.end == current.start), (
            "same-user neighbours are merged"
        )

    # The output agrees with the definition at every interesting instant
    # (every boundary) plus random ones. This also catches gaps and wrong users.
    boundaries = {frm, schedule.handover_start}
    boundaries |= {t for e in overrides + entries for t in (e.start, e.end)}
    samples = {t for t in boundaries if frm <= t < until}
    samples |= {frm + (until - frm) * rng.random() for _ in range(20)}

    for t in samples:
        assert actual_user_at(entries, t) == expected_user_at(schedule, overrides, t), t
