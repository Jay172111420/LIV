"""ProgressionEngine rules, in isolation: no database, no HTTP."""
import random
from datetime import date, timedelta

import pytest

from app.engine.metrics import SessionPerformance, SetPerformance
from app.engine.progression import (
    DEFAULT_INCREMENTS_KG,
    IMPERIAL_INCREMENTS_KG,
    Action,
    PreviousOutcome,
    ProgressionEngine,
    ProgressionInput,
    ProgressionStrategy,
    default_increment_kg,
    equipment_category,
)

TODAY = date(2026, 10, 6)
engine = ProgressionEngine()


def sess(days_ago, weight, reps, rir=None, rpe=None):
    return SessionPerformance(TODAY - timedelta(days=days_ago),
                              tuple(SetPerformance(weight, r, rir, rpe) for r in reps))


def rec(sessions, rep_min=8, rep_max=10, sets=3, **kw):
    kw.setdefault("increment_kg", 2.5)
    kw.setdefault("today", TODAY)
    return engine.recommend(ProgressionInput(sessions=sessions, rep_min=rep_min, rep_max=rep_max, sets=sets, **kw))


# ------------------------------------------------------------------ the spec's own examples
def test_top_of_range_on_every_set_adds_weight_and_returns_to_the_bottom_of_the_range():
    r = rec([sess(3, 80, [10, 10, 10])])
    assert (r.action, r.weight_kg, r.rep_min, r.rep_max, r.sets) == (Action.increase_weight, 82.5, 8, 10, 3)
    assert r.reps_goal == 8
    assert "top of your target range" in r.reason


def test_falling_short_of_the_range_maintains_the_weight():
    r = rec([sess(3, 80, [8, 7, 6])])
    assert r.action is Action.maintain and r.weight_kg == 80
    assert r.reps_goal == 8


# ------------------------------------------------------------------ double progression
def test_reps_first_within_the_range():
    r = rec([sess(3, 80, [9, 8, 8])])
    assert (r.action, r.weight_kg, r.reps_goal) == (Action.increase_reps, 80, 9)


def test_goal_never_exceeds_the_top_of_the_range():
    r = rec([sess(3, 80, [10, 10, 9])])
    assert r.action is Action.increase_reps and r.reps_goal == 10 and r.weight_kg == 80


def test_one_weak_set_is_a_mixed_session_not_a_failure():
    r = rec([sess(3, 80, [10, 10, 7])])
    assert r.action is Action.maintain and r.basis == "mixed_sets" and r.weight_kg == 80


def test_not_all_sets_completed_does_not_progress():
    r = rec([sess(3, 80, [10, 10])], sets=3)
    assert r.action is Action.maintain and r.basis == "short_on_sets" and r.weight_kg == 80


def test_extra_sets_beyond_the_prescription_are_fine():
    assert rec([sess(3, 80, [10, 10, 10, 10])], sets=3).action is Action.increase_weight


def test_warm_up_and_lighter_sets_are_ignored():
    s = SessionPerformance(TODAY - timedelta(days=3), tuple(SetPerformance(w, r) for w, r in
                           [(40, 12), (60, 10), (80, 10), (80, 10), (80, 10)]))
    r = rec([s])
    assert r.action is Action.increase_weight and r.weight_kg == 82.5


def test_only_the_heaviest_weight_counts_when_sets_differ():
    s = SessionPerformance(TODAY - timedelta(days=3), tuple(SetPerformance(w, r) for w, r in
                           [(82.5, 8), (82.5, 8), (80, 10)]))
    r = rec([s], sets=3)
    assert r.weight_kg == 82.5 and r.action is Action.maintain  # 2 of 3 sets at the top weight


# ------------------------------------------------------------------ weight progression
def test_weight_progression_adds_weight_once_the_target_reps_are_met():
    r = rec([sess(3, 100, [5, 5, 5])], rep_min=5, rep_max=5)
    assert r.strategy is ProgressionStrategy.weight_progression
    assert (r.action, r.weight_kg, r.reps_goal) == (Action.increase_weight, 102.5, 5)


def test_weight_progression_holds_when_a_set_misses():
    r = rec([sess(3, 100, [5, 5, 4])], rep_min=5, rep_max=5)
    assert r.action is Action.maintain and r.weight_kg == 100


def test_explicit_weight_progression_on_a_rep_range_uses_the_bottom_as_target():
    r = rec([sess(3, 60, [8, 8, 8])], strategy=ProgressionStrategy.weight_progression)
    assert r.action is Action.increase_weight and r.weight_kg == 62.5


def test_progression_is_weight_after_weight():
    w = 80.0
    for expected in (82.5, 85.0, 87.5):
        r = rec([sess(3, w, [10, 10, 10])])
        assert r.weight_kg == expected
        w = r.weight_kg


# ------------------------------------------------------------------ rep progression (bodyweight, timed)
def test_bodyweight_exercises_progress_by_reps_without_a_weight():
    r = rec([sess(3, None, [8, 8, 8])], rep_min=8, rep_max=20, is_bodyweight=True, category="bodyweight")
    assert r.strategy is ProgressionStrategy.rep_progression
    assert (r.action, r.weight_kg, r.reps_goal) == (Action.increase_reps, None, 9)
    assert r.increment_kg is None


def test_bodyweight_past_the_top_of_the_range_keeps_going_and_suggests_a_harder_variation():
    r = rec([sess(3, None, [20, 20, 20])], rep_min=8, rep_max=20, is_bodyweight=True, category="bodyweight")
    assert r.reps_goal == 21 and r.rep_min == 21 and "harder variation" in r.reason


def test_bodyweight_missing_the_minimum_holds_then_hints_at_an_easier_variation():
    one = rec([sess(3, None, [6, 5, 5])], rep_min=8, rep_max=15, is_bodyweight=True)
    assert one.action is Action.maintain and one.reps_goal == 8
    two = rec([sess(3, None, [6, 5, 5]), sess(6, None, [6, 5, 5])], rep_min=8, rep_max=15, is_bodyweight=True)
    assert "easier variation" in two.reason


def test_timed_exercises_progress_in_five_second_steps():
    r = rec([sess(3, None, [30, 30, 30])], rep_min=30, rep_max=60, is_timed=True, is_bodyweight=True)
    assert r.reps_goal == 35 and "seconds" in r.reason


def test_weighted_bodyweight_exercise_progresses_by_weight_when_a_load_was_logged():
    r = rec([sess(3, 10, [10, 10, 10])], rep_min=5, rep_max=10, is_bodyweight=True, category="bodyweight",
            increment_kg=1.0)
    assert r.action is Action.increase_weight and r.weight_kg == 11


# ------------------------------------------------------------------ hold and explicit strategy
def test_hold_strategy_keeps_the_target():
    r = rec([sess(3, 80, [10, 10, 10])], strategy=ProgressionStrategy.hold)
    assert (r.action, r.weight_kg, r.reps_goal) == (Action.hold, 80, None)


def test_no_weight_logged_for_a_weighted_exercise_holds_with_an_explanation():
    r = rec([sess(3, None, [10, 10, 10])], strategy=ProgressionStrategy.double_progression)
    assert r.action is Action.hold and r.weight_kg is None and "No weight was logged" in r.reason


# ------------------------------------------------------------------ RIR / RPE
def test_works_without_rir():
    assert rec([sess(3, 80, [10, 10, 10])]).action is Action.increase_weight


def test_very_easy_top_of_range_allows_a_bigger_jump():
    r = rec([sess(3, 80, [10, 10, 10], rir=4)])
    assert r.weight_kg == 85.0 and "reps in reserve" in r.reason and r.confidence == "low"


def test_big_jump_is_capped_at_ten_percent_of_the_weight_but_one_increment_is_always_allowed():
    light = rec([sess(3, 20, [10, 10, 10], rir=5)], increment_kg=5.0)
    assert light.weight_kg == 25.0  # a double step would be +10 (50%); capped back to one increment
    assert "bigger jump" not in light.reason
    heavy = rec([sess(3, 100, [10, 10, 10], rir=5)], increment_kg=5.0)
    assert heavy.weight_kg == 110.0  # +10 is exactly 10% of 100, so the double step is allowed


def test_one_rir_value_is_not_enough_to_trust():
    s = SessionPerformance(TODAY - timedelta(days=3), (SetPerformance(80, 10, rir=5), SetPerformance(80, 10),
                                                       SetPerformance(80, 10)))
    assert rec([s]).weight_kg == 82.5


def test_rpe_is_used_when_rir_is_missing():
    assert rec([sess(3, 80, [10, 10, 10], rpe=6)]).weight_kg == 85.0  # RPE 6 = 4 reps in reserve


def test_logged_rir_wins_over_rpe():
    s = SessionPerformance(TODAY - timedelta(days=3), tuple(SetPerformance(80, 10, rir=1, rpe=5) for _ in range(3)))
    assert rec([s]).weight_kg == 82.5


def test_easy_sets_below_the_top_still_get_a_small_weight_increase_suggestion():
    r = rec([sess(3, 80, [9, 9, 9], rir=4)])
    assert r.action is Action.increase_weight and r.weight_kg == 82.5 and r.basis == "easy_by_rir"


def test_rir_never_rescues_a_failed_session():
    r = rec([sess(3, 80, [7, 6, 6], rir=4)])
    assert r.action is Action.maintain and r.weight_kg == 80


def test_near_failure_top_sets_still_progress_with_a_warning_in_the_reason():
    r = rec([sess(3, 80, [10, 10, 10], rir=0)])
    assert r.weight_kg == 82.5 and "close to failure" in r.reason


# ------------------------------------------------------------------ no history
def test_first_time_has_no_weight_and_makes_no_numbers_up():
    r = rec([])
    assert r.action is Action.start and r.weight_kg is None and r.reps_goal is None
    assert (r.rep_min, r.rep_max, r.sets) == (8, 10, 3) and r.confidence == "low"
    assert "first logged session" in r.reason


def test_first_time_bodyweight_does_not_ask_for_a_weight():
    r = rec([], is_bodyweight=True, category="bodyweight")
    assert r.weight_kg is None and "weight you can lift" not in r.reason


def test_sessions_without_any_valid_sets_count_as_no_history():
    empty = SessionPerformance(TODAY, (SetPerformance(80, 0),))
    assert rec([empty]).action is Action.start


# ------------------------------------------------------------------ failure streaks
def test_two_misses_in_a_row_at_one_weight_reduces_it():
    r = rec([sess(3, 80, [7, 6, 6]), sess(6, 80, [7, 6, 6])])
    assert r.action is Action.reduce_weight and r.weight_kg == 75.0 and r.reps_goal == 8


def test_three_misses_deload_with_fewer_sets():
    r = rec([sess(3, 80, [7, 6, 6]), sess(6, 80, [7, 6, 6]), sess(9, 80, [7, 6, 6])])
    assert r.action is Action.deload and r.weight_kg == 72.5 and r.sets == 2


def test_a_miss_at_a_different_weight_is_not_a_streak():
    r = rec([sess(3, 75, [7, 6, 6]), sess(6, 80, [7, 6, 6])])
    assert r.action is Action.maintain and r.weight_kg == 75


def test_a_good_session_breaks_the_streak():
    r = rec([sess(3, 80, [8, 8, 8]), sess(6, 80, [7, 6, 6]), sess(9, 80, [7, 6, 6])])
    assert r.action is Action.increase_reps


def test_reductions_always_go_down_by_at_least_one_increment():
    r = rec([sess(3, 20, [7, 6, 6]), sess(6, 20, [7, 6, 6])], increment_kg=2.5)
    assert r.weight_kg == 17.5


def test_cannot_reduce_below_zero():
    r = rec([sess(3, 2, [7, 6, 6]), sess(6, 2, [7, 6, 6])], increment_kg=2.5)
    assert r.weight_kg >= 0


# ------------------------------------------------------------------ increments
@pytest.mark.parametrize("category,inc,expected", [
    ("barbell", None, 82.5), ("dumbbells", None, 81.0), ("machines", None, 82.5), ("kettlebell", None, 82.0),
    ("machines", 5.0, 85.0), ("dumbbells", 2.0, 82.0)])
def test_increment_depends_on_equipment_and_can_be_overridden(category, inc, expected):
    r = rec([sess(3, 80, [10, 10, 10])], category=category, increment_kg=inc)
    assert r.weight_kg == expected


def test_default_increments_are_not_one_universal_number():
    assert len(set(DEFAULT_INCREMENTS_KG.values())) > 2
    assert default_increment_kg("barbell", imperial=True) == IMPERIAL_INCREMENTS_KG["barbell"] == 2.27


@pytest.mark.parametrize("slugs,category", [
    (["barbell", "bench"], "barbell"), (["dumbbells", "bench"], "dumbbells"), (["machines"], "machines"),
    (["cable_machine"], "cable_machine"), (["kettlebell"], "kettlebell"), ([], "bodyweight"),
    (["pull_up_bar"], "bodyweight"), (["resistance_bands"], "bands")])
def test_equipment_category(slugs, category):
    assert equipment_category(slugs) == category


# ------------------------------------------------------------------ time away
def test_two_weeks_away_repeats_the_weight_instead_of_adding():
    r = rec([sess(15, 80, [10, 10, 10])])
    assert r.action is Action.hold and r.weight_kg == 80 and "15 days" in r.reason


def test_a_month_away_eases_back_in():
    r = rec([sess(30, 80, [10, 10, 10])])
    assert r.action is Action.reduce_weight and r.weight_kg == 72.5
    assert any(f.code == "returning_after_break" for f in r.flags)


# ------------------------------------------------------------------ decline
def decline_history():
    scores = [(3, 70, [8, 8, 8]), (6, 72.5, [8, 8, 8]), (9, 80, [9, 9, 9]), (12, 80, [9, 9, 9]),
              (15, 80, [9, 9, 9]), (18, 80, [9, 9, 9])]
    return [sess(d, w, r) for d, w, r in scores]


def test_a_decline_is_flagged_in_neutral_language_and_blocks_pushing_harder():
    r = rec(decline_history())
    flag = next(f for f in r.flags if f.code == "performance_decline")
    assert flag.message == "Your recent performance is below your normal trend."
    assert r.action is Action.hold
    text = (flag.message + (flag.detail or "")).lower()
    assert not any(w in text for w in ("ill", "sick", "injur", "diagnos", "disease"))


def test_a_clean_top_of_range_session_is_not_blocked_by_an_earlier_dip():
    history = decline_history()
    history[0] = sess(3, 70, [10, 10, 10])
    assert rec(history).action is Action.increase_weight


def test_decline_needs_enough_history():
    assert not rec(decline_history()[:3]).flags


def test_steady_performance_raises_no_flag():
    steady = [sess(d, 80, [9, 9, 9]) for d in (3, 6, 9, 12, 15)]
    assert not [f for f in rec(steady).flags if f.code == "performance_decline"]


# ------------------------------------------------------------------ overrides
def test_override_is_noted_but_the_recommendation_follows_what_was_actually_lifted():
    prev = PreviousOutcome("increase_weight", 82.5, 80.0, "ignored")
    r = rec([sess(3, 80, [10, 10, 10])], previous=prev)
    assert r.weight_kg == 82.5
    note = next(f for f in r.flags if f.code == "override_noted")
    assert "lighter" in note.message


def test_following_the_suggestion_adds_no_override_note():
    prev = PreviousOutcome("increase_weight", 82.5, 82.5, "accepted")
    assert not rec([sess(3, 82.5, [8, 8, 8])], previous=prev).flags


# ------------------------------------------------------------------ confidence
def test_confidence_grows_with_history():
    one = rec([sess(3, 80, [9, 9, 9])]).confidence
    two = rec([sess(3, 80, [9, 9, 9]), sess(6, 80, [9, 9, 9])]).confidence
    three = rec([sess(d, 80, [9, 9, 9]) for d in (3, 6, 9)]).confidence
    assert (one, two, three) == ("low", "medium", "high")


# ------------------------------------------------------------------ robustness
def test_invalid_range_is_repaired_not_crashed():
    r = rec([sess(3, 80, [10, 10, 10])], rep_min=10, rep_max=6)
    assert r.rep_min <= r.rep_max


def test_reasons_never_embed_a_unit_of_weight():
    cases = [[sess(3, 80, [10] * 3)], [sess(3, 80, [8, 7, 6])], [sess(3, 80, [9] * 3)], [sess(40, 80, [10] * 3)]]
    for c in cases:
        assert " kg" not in rec(c).reason and " lb" not in rec(c).reason


def test_fuzz_outputs_are_always_sane():
    rng = random.Random(42)
    for _ in range(400):
        sessions = [sess(3 * (i + 1), rng.choice([None, 20, 47.5, 80, 100]),
                         [rng.randint(0, 25) for _ in range(rng.randint(1, 6))],
                         rir=rng.choice([None, 0, 2, 5]))
                    for i in range(rng.randint(0, 8))]
        lo = rng.randint(1, 12)
        r = rec(sessions, rep_min=lo, rep_max=lo + rng.randint(0, 8), sets=rng.randint(1, 6),
                increment_kg=rng.choice([None, 1.0, 2.5, 5.0]), is_bodyweight=rng.random() < 0.3)
        assert r.rep_min <= r.rep_max and r.sets >= 1 and r.reason
        assert r.weight_kg is None or r.weight_kg >= 0
        assert r.reps_goal is None or r.reps_goal >= 1
