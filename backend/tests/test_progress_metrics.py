"""Estimated 1RM, volume, trends, decline detection and personal-record rules (pure Python)."""
from datetime import date, timedelta

import pytest

from app.engine.metrics import (
    SessionPerformance,
    SetPerformance,
    VolumeTotals,
    detect_decline,
    estimate_1rm,
    performance_score,
    session_volume,
    set_volume,
    trend_direction,
    week_start,
    working_sets,
)
from app.engine.records import REPS, VOLUME, WEIGHT, detect_records

D0 = date(2026, 9, 1)


def sess(i, sets, sid=None):
    return SessionPerformance(D0 + timedelta(days=7 * i), tuple(SetPerformance(w, r) for w, r in sets), sid or i + 1)


# ------------------------------------------------------------------ 1RM and volume
@pytest.mark.parametrize("w,r,expected", [(100, 1, 100.0), (100, 5, 116.7), (80, 10, 106.7), (60, 12, 84.0)])
def test_epley_estimate(w, r, expected):
    assert estimate_1rm(w, r) == expected


@pytest.mark.parametrize("w,r", [(None, 5), (0, 5), (100, 0), (100, 13), (-5, 5)])
def test_estimate_not_applicable(w, r):
    assert estimate_1rm(w, r) is None


def test_volume_is_weight_times_reps_and_bodyweight_has_none():
    assert set_volume(SetPerformance(80, 10)) == 800
    assert set_volume(SetPerformance(None, 20)) == 0 and set_volume(SetPerformance(0, 20)) == 0
    assert session_volume([SetPerformance(80, 10), SetPerformance(82.5, 8), SetPerformance(None, 5)]) == 1460


def test_volume_totals_count_sets_and_reps_for_bodyweight_too():
    t = VolumeTotals()
    t.add([SetPerformance(None, 10), SetPerformance(50, 5), SetPerformance(50, 0)])
    assert (t.sets, t.reps, t.volume_kg) == (2, 15, 250)


def test_week_starts_on_monday():
    assert week_start(date(2026, 10, 7)) == date(2026, 10, 5)  # a Wednesday
    assert week_start(date(2026, 10, 5)) == date(2026, 10, 5)
    assert week_start(date(2026, 10, 11)) == date(2026, 10, 5)


def test_working_sets_drop_lighter_sets():
    sets = [SetPerformance(w, 5) for w in (40, 60, 80, 80)]
    assert [s.weight_kg for s in working_sets(sets)] == [80, 80]


# ------------------------------------------------------------------ scores, trend, decline
def test_score_uses_best_estimated_1rm_for_weighted_and_average_reps_for_bodyweight():
    assert performance_score(sess(0, [(100, 5), (100, 4)])) == 116.7
    assert performance_score(sess(0, [(None, 10), (None, 8)])) == 9


def test_trend_directions():
    assert trend_direction([100, 101, 103, 106, 108, 110])[0] == "improving"
    assert trend_direction([110, 108, 105, 100, 98, 95])[0] == "declining"
    assert trend_direction([100, 100.5, 100, 99.8, 100.2, 100])[0] == "steady"
    assert trend_direction([100, 105]) == ("insufficient_data", None)


def test_decline_rule():
    assert detect_decline([90, 91, 100, 100, 100, 100]).level == "mild"
    assert detect_decline([80, 82, 100, 100, 100, 100]).level == "marked"
    assert detect_decline([90, 100, 100, 100, 100]) is None  # only one recent session is low
    assert detect_decline([96, 97, 100, 100, 100]) is None  # within normal variation
    assert detect_decline([50, 50, 100]) is None  # not enough history


# ------------------------------------------------------------------ personal records
def kinds(events):
    return sorted((e.record_type, e.value) for e in events)


def test_first_session_is_a_baseline_with_no_records():
    assert detect_records([sess(0, [(80, 10)])]) == []


def test_weight_pr():
    ev = detect_records([sess(0, [(80, 10)] * 3), sess(1, [(82.5, 8), (80, 8)])])
    w = next(e for e in ev if e.record_type == WEIGHT)
    assert (w.value, w.reps, w.previous_value) == (82.5, 8, 80)


def test_a_new_heaviest_weight_is_not_also_a_rep_pr():
    ev = detect_records([sess(0, [(80, 10)]), sess(1, [(82.5, 8)])])
    assert [e.record_type for e in ev] == [WEIGHT]


def test_rep_pr_at_the_same_weight():
    ev = detect_records([sess(0, [(80, 10)]), sess(1, [(80, 11), (80, 9)])])
    r = next(e for e in ev if e.record_type == REPS)
    assert (r.value, r.weight_kg, r.previous_value) == (11, 80, 10)


def test_equal_reps_is_not_a_record():
    assert not [e for e in detect_records([sess(0, [(80, 10)]), sess(1, [(80, 10)])]) if e.record_type == REPS]


def test_more_reps_at_a_lighter_weight_than_a_heavier_set_with_equal_reps_is_not_a_rep_pr():
    ev = detect_records([sess(0, [(80, 10)]), sess(1, [(75, 10)])])
    assert not [e for e in ev if e.record_type == REPS]


def test_warm_up_sets_never_create_rep_prs():
    ev = detect_records([sess(0, [(80, 10)]), sess(1, [(30, 25), (80, 10)])])
    assert not [e for e in ev if e.record_type == REPS]


def test_volume_pr():
    ev = detect_records([sess(0, [(80, 10)] * 3), sess(1, [(80, 10)] * 4)])
    v = next(e for e in ev if e.record_type == VOLUME)
    assert (v.value, v.previous_value) == (3200, 2400)


def test_no_volume_pr_when_volume_drops():
    assert not [e for e in detect_records([sess(0, [(80, 10)] * 4), sess(1, [(80, 10)] * 3)]) if e.record_type == VOLUME]


def test_bodyweight_rep_pr_and_no_volume_pr():
    ev = detect_records([sess(0, [(None, 10)] * 3), sess(1, [(None, 12), (None, 10)])])
    assert [e.record_type for e in ev] == [REPS] and ev[0].value == 12 and ev[0].weight_kg is None


def test_going_from_bodyweight_to_weighted_is_not_a_weight_pr():
    ev = detect_records([sess(0, [(None, 10)]), sess(1, [(10, 10)])])
    assert not [e for e in ev if e.record_type == WEIGHT]


def test_records_carry_the_session_and_date():
    ev = detect_records([sess(0, [(80, 10)]), sess(1, [(85, 5)], sid=77)])
    assert ev[0].session_id == 77 and ev[0].achieved_on == D0 + timedelta(days=7)


def test_replay_is_chronological_so_a_later_lower_lift_is_not_a_record():
    ev = detect_records([sess(0, [(90, 5)]), sess(1, [(80, 5)]), sess(2, [(85, 5)])])
    assert not [e for e in ev if e.record_type == WEIGHT]
