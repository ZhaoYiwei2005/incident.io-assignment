from datetime import datetime, timedelta, timezone

import pytest

from scheduler.models import (
    Entry,
    InputError,
    Schedule,
    format_time,
    parse_overrides,
    parse_time,
)

UTC = timezone.utc


# --- parse_time / format_time -------------------------------------------------


def test_parse_time_with_z_suffix():
    assert parse_time("2026-11-06T17:00:00Z", "t") == datetime(2026, 11, 6, 17, tzinfo=UTC)


def test_parse_time_converts_other_offsets_to_utc():
    # 18:00 at UTC+1 is 17:00 UTC.
    parsed = parse_time("2026-11-06T18:00:00+01:00", "t")
    assert parsed == datetime(2026, 11, 6, 17, tzinfo=UTC)
    assert parsed.tzinfo == UTC


def test_parse_time_rejects_missing_timezone():
    with pytest.raises(InputError, match="no timezone"):
        parse_time("2026-11-06T17:00:00", "t")


@pytest.mark.parametrize("bad", ["not a time", "2026-13-01T00:00:00Z", "", 123, None])
def test_parse_time_rejects_invalid_values(bad):
    with pytest.raises(InputError, match="t:"):
        parse_time(bad, "t")


def test_format_time_uses_z_suffix():
    assert format_time(datetime(2026, 11, 6, 17, tzinfo=UTC)) == "2026-11-06T17:00:00Z"


def test_format_time_converts_to_utc():
    plus_one = timezone(timedelta(hours=1))
    assert format_time(datetime(2026, 11, 6, 18, tzinfo=plus_one)) == "2026-11-06T17:00:00Z"


def test_parse_and_format_round_trip():
    text = "2026-11-09T22:00:00Z"
    assert format_time(parse_time(text, "t")) == text


# --- Entry --------------------------------------------------------------------

OVERRIDE_JSON = {
    "user": "charlie",
    "start_at": "2026-11-09T17:00:00Z",
    "end_at": "2026-11-09T22:00:00Z",
}


def test_entry_covers_is_half_open():
    entry = Entry.from_json(OVERRIDE_JSON, "o")
    assert entry.covers(entry.start)  # start is included
    assert entry.covers(entry.end - timedelta(seconds=1))
    assert not entry.covers(entry.end)  # end is excluded
    assert not entry.covers(entry.start - timedelta(seconds=1))


def test_entry_json_round_trip():
    entry = Entry.from_json(OVERRIDE_JSON, "o")
    assert entry == Entry(
        "charlie",
        datetime(2026, 11, 9, 17, tzinfo=UTC),
        datetime(2026, 11, 9, 22, tzinfo=UTC),
    )
    assert entry.to_json() == OVERRIDE_JSON


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"end_at": "2026-11-09T17:00:00Z"}, "start_at must be before end_at"),
        ({"end_at": "2026-11-09T16:00:00Z"}, "start_at must be before end_at"),
        ({"user": ""}, "o.user"),
        ({"user": 42}, "o.user"),
        ({"start_at": "yesterday"}, "o.start_at"),
    ],
)
def test_entry_rejects_invalid_fields(changes, message):
    with pytest.raises(InputError, match=message):
        Entry.from_json({**OVERRIDE_JSON, **changes}, "o")


def test_entry_rejects_missing_field():
    data = {k: v for k, v in OVERRIDE_JSON.items() if k != "end_at"}
    with pytest.raises(InputError, match="missing required field 'end_at'"):
        Entry.from_json(data, "o")


def test_entry_rejects_non_object():
    with pytest.raises(InputError, match="expected a JSON object"):
        Entry.from_json(["charlie"], "o")


# --- Schedule -----------------------------------------------------------------

SCHEDULE_JSON = {
    "users": ["alice", "bob", "charlie"],
    "handover_start_at": "2026-11-06T17:00:00Z",
    "handover_interval_days": 7,
}


def test_schedule_from_json():
    assert Schedule.from_json(SCHEDULE_JSON) == Schedule(
        users=("alice", "bob", "charlie"),
        handover_start=datetime(2026, 11, 6, 17, tzinfo=UTC),
        interval=timedelta(days=7),
    )


def test_schedule_accepts_fractional_interval():
    schedule = Schedule.from_json({**SCHEDULE_JSON, "handover_interval_days": 0.5})
    assert schedule.interval == timedelta(hours=12)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"users": []}, "schedule.users"),
        ({"users": "alice"}, "schedule.users"),
        ({"users": ["alice", ""]}, "schedule.users"),
        ({"handover_interval_days": 0}, "handover_interval_days"),
        ({"handover_interval_days": -7}, "handover_interval_days"),
        ({"handover_interval_days": "7"}, "handover_interval_days"),
        ({"handover_interval_days": True}, "handover_interval_days"),
        ({"handover_start_at": "2026-11-06T17:00:00"}, "no timezone"),
    ],
)
def test_schedule_rejects_invalid_fields(changes, message):
    with pytest.raises(InputError, match=message):
        Schedule.from_json({**SCHEDULE_JSON, **changes})


def test_schedule_rejects_missing_field():
    data = {k: v for k, v in SCHEDULE_JSON.items() if k != "users"}
    with pytest.raises(InputError, match="missing required field 'users'"):
        Schedule.from_json(data)


# --- parse_overrides ------------------------------------------------------------


def test_parse_overrides_accepts_empty_list():
    assert parse_overrides([]) == []


def test_parse_overrides_rejects_non_list():
    with pytest.raises(InputError, match="expected a JSON array"):
        parse_overrides(OVERRIDE_JSON)


def test_parse_overrides_error_names_the_bad_item():
    bad = {**OVERRIDE_JSON, "user": ""}
    with pytest.raises(InputError, match=r"overrides\[1\]\.user"):
        parse_overrides([OVERRIDE_JSON, bad])
