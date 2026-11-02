from scheduler.core import clip, merge_adjacent, overlay, render_schedule, rotation_shifts
from tests.helpers import BRIEF, e, t, weekly


def render(schedule, overrides, frm, until):
    return render_schedule(schedule, overrides, t(frm), t(until))


# --- The brief's example (golden test) --------------------------------------------


def test_example_from_the_brief():
    overrides = [e("charlie", "11-09 17:00", "11-09 22:00")]
    assert render(BRIEF, overrides, "11-06 17:00", "11-20 17:00") == [
        e("alice", "11-06 17:00", "11-09 17:00"),
        e("charlie", "11-09 17:00", "11-09 22:00"),
        e("alice", "11-09 22:00", "11-13 17:00"),
        e("bob", "11-13 17:00", "11-20 17:00"),
    ]


# --- Step 1: rotation_shifts ----------------------------------------------------------


def test_rotation_cycles_through_users_and_wraps_around():
    assert rotation_shifts(BRIEF, t("11-06 17:00"), t("12-04 17:00")) == [
        e("alice", "11-06 17:00", "11-13 17:00"),
        e("bob", "11-13 17:00", "11-20 17:00"),
        e("charlie", "11-20 17:00", "11-27 17:00"),
        e("alice", "11-27 17:00", "12-04 17:00"),
    ]


def test_rotation_starts_with_the_shift_containing_frm_unclipped():
    assert rotation_shifts(BRIEF, t("11-15 09:00"), t("11-16 09:00")) == [
        e("bob", "11-13 17:00", "11-20 17:00"),
    ]


def test_rotation_frm_exactly_at_handover_belongs_to_the_next_user():
    # Half-open intervals: alice's shift ends at 13 Nov 17:00, bob's starts then.
    assert rotation_shifts(BRIEF, t("11-13 17:00"), t("11-14 17:00")) == [
        e("bob", "11-13 17:00", "11-20 17:00"),
    ]


def test_rotation_never_starts_before_handover_start():
    assert rotation_shifts(BRIEF, t("11-01 00:00"), t("11-08 00:00")) == [
        e("alice", "11-06 17:00", "11-13 17:00"),
    ]


def test_rotation_is_empty_when_window_ends_before_handover_start():
    assert rotation_shifts(BRIEF, t("11-01 00:00"), t("11-06 17:00")) == []


# --- Step 2: overlay -------------------------------------------------------------------

ALICE_WEEK = [e("alice", "11-06 17:00", "11-13 17:00")]
TWO_WEEKS = [e("alice", "11-06 17:00", "11-13 17:00"), e("bob", "11-13 17:00", "11-20 17:00")]


def test_overlay_with_no_top_returns_base():
    assert overlay(base=TWO_WEEKS, top=[]) == TWO_WEEKS


def test_overlay_splits_a_shift_around_an_override():
    assert overlay(base=ALICE_WEEK, top=[e("charlie", "11-09 17:00", "11-09 22:00")]) == [
        e("alice", "11-06 17:00", "11-09 17:00"),
        e("charlie", "11-09 17:00", "11-09 22:00"),
        e("alice", "11-09 22:00", "11-13 17:00"),
    ]


def test_overlay_override_spanning_a_handover_cuts_both_shifts():
    # overlay cuts at every change point, including the 13 Nov handover underneath
    # charlie, so charlie comes out in two pieces. merge_adjacent joins them later.
    assert overlay(base=TWO_WEEKS, top=[e("charlie", "11-12 09:00", "11-14 09:00")]) == [
        e("alice", "11-06 17:00", "11-12 09:00"),
        e("charlie", "11-12 09:00", "11-13 17:00"),
        e("charlie", "11-13 17:00", "11-14 09:00"),
        e("bob", "11-14 09:00", "11-20 17:00"),
    ]


def test_overlay_back_to_back_overrides():
    top = [e("charlie", "11-08 09:00", "11-08 12:00"), e("dave", "11-08 12:00", "11-08 15:00")]
    assert overlay(base=ALICE_WEEK, top=top) == [
        e("alice", "11-06 17:00", "11-08 09:00"),
        e("charlie", "11-08 09:00", "11-08 12:00"),
        e("dave", "11-08 12:00", "11-08 15:00"),
        e("alice", "11-08 15:00", "11-13 17:00"),
    ]


def test_overlay_override_covering_a_whole_shift_replaces_it():
    top = [e("charlie", "11-06 17:00", "11-13 17:00")]
    assert overlay(base=TWO_WEEKS, top=top) == [
        e("charlie", "11-06 17:00", "11-13 17:00"),
        e("bob", "11-13 17:00", "11-20 17:00"),
    ]


def test_overlay_override_where_base_has_nobody_still_applies():
    top = [e("charlie", "11-20 17:00", "11-21 17:00")]
    assert overlay(base=ALICE_WEEK, top=top) == ALICE_WEEK + top


# --- Step 3: clip ----------------------------------------------------------------------


def test_clip_trims_entries_overlapping_the_window_edges():
    assert clip(TWO_WEEKS, t("11-10 00:00"), t("11-15 00:00")) == [
        e("alice", "11-10 00:00", "11-13 17:00"),
        e("bob", "11-13 17:00", "11-15 00:00"),
    ]


def test_clip_drops_entries_outside_the_window():
    # alice's shift ends exactly at frm, so nothing of it is inside [frm, until).
    assert clip(TWO_WEEKS, t("11-13 17:00"), t("11-14 00:00")) == [
        e("bob", "11-13 17:00", "11-14 00:00"),
    ]


# --- Step 4: merge_adjacent ------------------------------------------------------------


def test_merge_joins_touching_entries_for_the_same_user():
    entries = [e("alice", "11-06 17:00", "11-08 09:00"), e("alice", "11-08 09:00", "11-13 17:00")]
    assert merge_adjacent(entries) == ALICE_WEEK


def test_merge_keeps_different_users_separate():
    assert merge_adjacent(TWO_WEEKS) == TWO_WEEKS


def test_merge_keeps_same_user_separate_when_there_is_a_gap():
    entries = [e("alice", "11-06 17:00", "11-07 17:00"), e("alice", "11-08 17:00", "11-09 17:00")]
    assert merge_adjacent(entries) == entries


# --- The whole pipeline: edge cases ------------------------------------------------------


def test_window_starting_before_the_schedule_begins_at_handover_start():
    assert render(BRIEF, [], "11-01 00:00", "11-10 00:00") == [
        e("alice", "11-06 17:00", "11-10 00:00"),
    ]


def test_window_edges_inside_shifts_truncate_them():
    assert render(BRIEF, [], "11-10 00:00", "11-15 00:00") == [
        e("alice", "11-10 00:00", "11-13 17:00"),
        e("bob", "11-13 17:00", "11-15 00:00"),
    ]


def test_override_spanning_a_handover():
    overrides = [e("charlie", "11-12 09:00", "11-14 09:00")]
    assert render(BRIEF, overrides, "11-06 17:00", "11-20 17:00") == [
        e("alice", "11-06 17:00", "11-12 09:00"),
        e("charlie", "11-12 09:00", "11-14 09:00"),
        e("bob", "11-14 09:00", "11-20 17:00"),
    ]


def test_override_partly_outside_the_window_is_truncated():
    overrides = [e("charlie", "11-09 17:00", "11-10 17:00")]
    assert render(BRIEF, overrides, "11-10 00:00", "11-11 00:00") == [
        e("charlie", "11-10 00:00", "11-10 17:00"),
        e("alice", "11-10 17:00", "11-11 00:00"),
    ]


def test_override_entirely_outside_the_window_has_no_effect():
    overrides = [e("charlie", "11-20 17:00", "11-21 17:00")]
    assert render(BRIEF, overrides, "11-06 17:00", "11-13 17:00") == [
        e("alice", "11-06 17:00", "11-13 17:00"),
    ]


def test_override_by_the_scheduled_user_merges_into_one_entry():
    overrides = [e("alice", "11-09 17:00", "11-09 22:00")]
    assert render(BRIEF, overrides, "11-06 17:00", "11-13 17:00") == [
        e("alice", "11-06 17:00", "11-13 17:00"),
    ]


def test_override_running_into_the_same_users_shift_merges():
    # bob covers the end of alice's week, then his own week starts.
    overrides = [e("bob", "11-12 17:00", "11-13 17:00")]
    assert render(BRIEF, overrides, "11-06 17:00", "11-20 17:00") == [
        e("alice", "11-06 17:00", "11-12 17:00"),
        e("bob", "11-12 17:00", "11-20 17:00"),
    ]


def test_override_covering_the_whole_window():
    overrides = [e("charlie", "11-01 00:00", "11-30 00:00")]
    assert render(BRIEF, overrides, "11-10 00:00", "11-20 00:00") == [
        e("charlie", "11-10 00:00", "11-20 00:00"),
    ]


def test_single_user_schedule_is_one_continuous_entry():
    assert render(weekly("alice"), [], "11-06 17:00", "11-27 17:00") == [
        e("alice", "11-06 17:00", "11-27 17:00"),
    ]
