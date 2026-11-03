"""The scheduling algorithm: a pipeline of small, pure functions over lists of Entry.

    rotation_shifts -> overlay -> clip -> merge_adjacent

Every Entry is a half-open interval [start, end) (see Entry.covers), so
back-to-back entries never overlap. Nothing here does any I/O.
"""

from datetime import datetime

from scheduler.models import Entry, Schedule


def render_schedule(
    schedule: Schedule, overrides: list[Entry], frm: datetime, until: datetime) -> list[Entry]:
    """The final on-call timeline between frm and until."""
    shifts = rotation_shifts(schedule, frm, until)  # 1. project the rotation
    timeline = overlay(base=shifts, top=overrides)  # 2. overrides win where they apply
    timeline = clip(timeline, frm, until)  # 3. truncate to the window
    return merge_adjacent(timeline)  # 4. join same-user neighbours


def rotation_shifts(schedule: Schedule, frm: datetime, until: datetime) -> list[Entry]:
    """The rotation's shifts that overlap [frm, until), in order and not yet clipped."""
    users, start, interval = schedule.users, schedule.handover_start, schedule.interval

    # Index of the shift containing frm (timedelta // timedelta gives a whole number).
    # max(0, ...) because nobody is on call before the schedule starts.
    k = max(0, (frm - start) // interval)

    shifts = []
    while start + k * interval < until:
        user = users[k % len(users)]  # % wraps back round to the first user
        shifts.append(Entry(user, start + k * interval, start + (k + 1) * interval))
        k += 1
    return shifts


def overlay(base: list[Entry], top: list[Entry]) -> list[Entry]:
    """Combine two layers: wherever top has someone on call they win, elsewhere base applies.

    Who is on call can only change where some entry starts or ends. So between each
    pair of consecutive change points it's constant, and checking the first instant
    of that segment is enough.
    """
    points = sorted({t for entry in base + top for t in (entry.start, entry.end)})

    timeline = []
    for a, b in zip(points, points[1:]):
        user = _user_at(top, a) or _user_at(base, a)
        if user is not None:  # someone is on call here
            timeline.append(Entry(user, a, b))
    return timeline


def clip(entries: list[Entry], frm: datetime, until: datetime) -> list[Entry]:
    """Trim entries to [frm, until), dropping any that fall entirely outside it."""
    clipped = []
    for entry in entries:
        start, end = max(entry.start, frm), min(entry.end, until)
        if start < end:
            clipped.append(Entry(entry.user, start, end))
    return clipped


def merge_adjacent(entries: list[Entry]) -> list[Entry]:
    """Join consecutive entries for the same user that touch. Expects entries in time order."""
    merged: list[Entry] = []
    for entry in entries:
        previous = merged[-1] if merged else None
        if previous and previous.user == entry.user and previous.end == entry.start:
            merged[-1] = Entry(entry.user, previous.start, entry.end)
        else:
            merged.append(entry)
    return merged


def _user_at(layer: list[Entry], t: datetime) -> str | None:
    """Who is on call at instant t in this layer, or None if nobody is."""
    for entry in layer:
        if entry.covers(t):
            return entry.user
    return None
