"""Plan generation: structure by goal, frequency, split, session length, determinism, and the API."""
import pytest

from app.engine import GenerationInput, SplitGenerator, WorkoutGenerator
from app.engine.prescription import WARMUP_MINUTES, estimate_seconds
from tests.conftest import first_training_day, generate, onboard

ALL_GEAR = frozenset({"dumbbells", "barbell", "kettlebell", "bench", "squat_rack", "pull_up_bar",
                      "cable_machine", "machines", "resistance_bands"})


def make(pool, goal="muscle_gain", level="intermediate", days=4, minutes=60, gear=ALL_GEAR, split="auto"):
    return WorkoutGenerator(pool).generate(
        GenerationInput(goal, level, days, minutes, gear, "commercial_gym", split))


def day_names(plan):
    return [d.name for d in plan.days]


# ---------------------------------------------------------------- frequency
@pytest.mark.parametrize("days", [1, 2, 3, 4, 5, 6, 7])
def test_every_frequency_is_handled(pool, days):
    plan = make(pool, days=days)
    assert len(plan.days) == 7 and [d.day_index for d in plan.days] == list(range(1, 8))
    assert len(plan.training_days) == days
    assert all(len(d.exercises) >= 3 for d in plan.training_days)
    assert all(not d.exercises for d in plan.days if d.is_rest)


def test_four_day_week_matches_the_spec_example(pool):
    plan = make(pool, days=4)
    assert [("rest" if d.is_rest else d.name.split()[0]) for d in plan.days][:5] == [
        "Upper", "Lower", "rest", "Upper", "Lower"]


def test_rest_days_sit_between_blocks(pool):
    assert [d.is_rest for d in make(pool, days=3).days] == [False, True, False, True, False, True, True]
    assert [d.is_rest for d in make(pool, days=6).days] == [False] * 6 + [True]


def test_seven_days_warns_about_recovery(pool):
    assert any("rest day" in w for w in make(pool, days=7).warnings)


# ---------------------------------------------------------------- splits
@pytest.mark.parametrize("days,level,goal,expected", [
    (2, "beginner", "fat_loss", "full_body"),
    (3, "beginner", "muscle_gain", "full_body"),
    (3, "intermediate", "muscle_gain", "push_pull_legs"),
    (3, "intermediate", "strength", "full_body"),
    (4, "advanced", "muscle_gain", "upper_lower"),
    (5, "beginner", "general_fitness", "upper_lower"),
    (5, "advanced", "muscle_gain", "push_pull_legs"),
    (6, "intermediate", "muscle_gain", "push_pull_legs"),
    (6, "beginner", "muscle_gain", "upper_lower"),
])
def test_auto_split_choice(days, level, goal, expected):
    assert SplitGenerator().choose(days, goal, level)[0] == expected


def test_each_supported_split_builds_correct_days(pool):
    assert day_names(make(pool, days=3, split="push_pull_legs"))[:5] == ["Push", "rest".replace("rest", "Rest"), "Pull", "Rest", "Legs"]
    assert [d.name for d in make(pool, days=4, split="upper_lower").training_days] == [
        "Upper A", "Lower A", "Upper B", "Lower B"]
    assert [d.name for d in make(pool, days=2, split="push_pull").training_days] == ["Push", "Pull"]
    assert [d.name for d in make(pool, days=5, split="bro_split").training_days] == [
        "Chest", "Back", "Shoulders", "Arms", "Legs"]
    assert [d.name for d in make(pool, days=3, split="full_body").training_days] == [
        "Full body A", "Full body B", "Full body C"]


def test_unsuitable_split_preference_falls_back_with_a_warning(pool):
    plan = make(pool, days=2, split="bro_split")
    assert plan.split == "full_body" and any("Body-part split" in w for w in plan.warnings)


def test_muscle_groups_per_day_are_sensible(pool):
    plan = make(pool, days=3, split="push_pull_legs")
    muscles = {d.name: {e.primary_muscle for e in d.exercises} for d in plan.training_days}
    assert muscles["Push"] <= {"chest", "shoulders", "triceps"}
    assert muscles["Pull"] <= {"back", "biceps", "shoulders", "core"}
    assert muscles["Legs"] <= {"quads", "hamstrings", "glutes", "calves", "core"}


def test_new_splits_can_be_registered_without_touching_the_generator(pool):
    from app.engine.split_generator import C, DayTemplate, SplitSpec

    arms_and_legs = [[DayTemplate("Legs", "Legs", (C("quads", "squat"), C("hamstrings", "hinge"), C("glutes", "hinge")))],
                     [DayTemplate("Press", "Chest", (C("chest", "push"), C("shoulders", "push"), C("back", "pull")))]]
    splits = SplitGenerator()
    splits.register(SplitSpec("legs_press", "Legs and press", 2, 2, lambda n: arms_and_legs))
    plan = WorkoutGenerator(pool, splits).generate(
        GenerationInput("strength", "intermediate", 2, 45, ALL_GEAR, "commercial_gym", "legs_press"))
    assert [d.name for d in plan.training_days] == ["Legs", "Press"]


def test_custom_day_templates_are_supported(pool):
    from app.engine.split_generator import C, DayTemplate

    days = (DayTemplate("Day X", "Chest", (C("chest", "push"), C("chest", "push"), C("chest", "push"))),)
    plan = WorkoutGenerator(pool).generate(GenerationInput(
        "muscle_gain", "intermediate", 1, 45, ALL_GEAR, "commercial_gym", "custom", days))
    assert plan.split == "custom" and plan.training_days[0].name == "Day X"


# ---------------------------------------------------------------- goals
def avg(values):
    return sum(values) / len(values)


def main_lifts(plan):
    return [e for d in plan.training_days for e in d.exercises if e.role == "compound"]


def test_strength_uses_low_reps_long_rest_and_few_isolation_exercises(pool):
    plan, gain = make(pool, goal="strength"), make(pool, goal="muscle_gain")
    assert avg([e.rep_max for e in main_lifts(plan)]) < avg([e.rep_max for e in main_lifts(gain)])
    assert avg([e.rep_min for e in main_lifts(plan)]) <= 7
    assert avg([e.rest_seconds for e in main_lifts(plan)]) >= 150
    lead = [d.exercises[0] for d in plan.training_days]
    assert all(e.rep_max <= 8 for e in lead)  # the lead lift of every day is genuinely heavy
    for d in plan.training_days:
        assert sum(1 for e in d.exercises if e.role == "isolation") <= 2


def test_muscle_gain_uses_moderate_reps_and_more_accessories(pool):
    gain, strength = make(pool, goal="muscle_gain"), make(pool, goal="strength")
    assert 6 <= avg([e.rep_max for e in main_lifts(gain)]) <= 12
    count = lambda p: sum(1 for d in p.days for e in d.exercises if e.role == "isolation")  # noqa: E731
    assert count(gain) > count(strength)


def test_fat_loss_has_conditioning_short_rests_and_higher_reps(pool):
    loss, gain = make(pool, goal="fat_loss"), make(pool, goal="muscle_gain")
    assert all(any(e.role == "conditioning" for e in d.exercises) for d in loss.training_days)
    assert not any(e.role == "conditioning" for d in gain.days for e in d.exercises)
    assert avg([e.rest_seconds for e in main_lifts(loss)]) < avg([e.rest_seconds for e in main_lifts(gain)])


def test_goals_produce_distinct_prescriptions(pool):
    shapes = {g: tuple((e.sets, e.rep_min, e.rep_max, e.rest_seconds) for e in main_lifts(make(pool, goal=g)))
              for g in ["fat_loss", "muscle_gain", "recomposition", "strength", "general_fitness"]}
    assert len(set(shapes.values())) == 5


def test_prescriptions_stay_inside_each_exercises_own_range(pool):
    by_id = {e.id: e for e in pool}
    for goal in ["fat_loss", "muscle_gain", "strength", "general_fitness", "recomposition"]:
        for level in ["beginner", "intermediate", "advanced"]:
            for d in make(pool, goal=goal, level=level, days=5).days:
                for e in d.exercises:
                    src = by_id[e.exercise_id]
                    assert src.rep_min <= e.rep_min <= e.rep_max <= src.rep_max
                    assert 2 <= e.sets <= 5 and 15 <= e.rest_seconds <= 300


def test_experience_changes_volume(pool):
    # 120-minute sessions so no sets are trimmed to fit the time budget
    sets = lambda lvl: sum(e.sets for d in make(pool, level=lvl, minutes=120).days for e in d.exercises)  # noqa: E731
    assert sets("beginner") < sets("intermediate") < sets("advanced")


# ---------------------------------------------------------------- duration
def test_session_length_controls_the_number_of_exercises(pool):
    short, long = make(pool, minutes=30), make(pool, minutes=90)
    assert max(len(d.exercises) for d in short.training_days) < min(len(d.exercises) for d in long.training_days)


@pytest.mark.parametrize("minutes", [30, 45, 60, 75, 90])
def test_days_fit_within_the_session_length(pool, minutes):
    by_id = {e.id: e for e in pool}
    for d in make(pool, minutes=minutes).training_days:
        seconds = sum(estimate_seconds(e.sets, e.rep_min, e.rep_max, e.rest_seconds, by_id[e.exercise_id].is_timed)
                      for e in d.exercises)
        assert seconds <= (minutes - WARMUP_MINUTES) * 60 or len(d.exercises) <= 3
        assert d.estimated_minutes == round(seconds / 60)


def test_big_lifts_come_first_and_core_conditioning_last(pool):
    day = make(pool, goal="fat_loss", days=3).training_days[0]
    roles = [e.role for e in day.exercises]
    assert roles[0] == "compound" and roles[-1] in ("conditioning", "isolation")
    assert roles == sorted(roles, key=lambda r: {"compound": 0, "isolation": 1, "conditioning": 3}[r]) or \
        day.exercises[-1].role == "conditioning"


# ---------------------------------------------------------------- determinism & validation
def test_generation_is_deterministic(pool):
    assert make(pool) == make(pool)


def test_repeated_day_types_use_different_exercises(pool):
    plan = make(pool, days=4)
    upper_a, upper_b = [{e.exercise_id for e in d.exercises} for d in plan.training_days if d.name.startswith("Upper")]
    assert upper_a != upper_b and len(upper_a & upper_b) < len(upper_a)


def test_no_exercise_repeats_within_a_day(pool):
    for days in range(1, 8):
        for d in make(pool, days=days).days:
            ids = [e.exercise_id for e in d.exercises]
            assert len(ids) == len(set(ids))


@pytest.mark.parametrize("bad", [dict(days=0), dict(days=8), dict(minutes=5), dict(minutes=500)])
def test_engine_rejects_impossible_inputs(pool, bad):
    with pytest.raises(ValueError):
        make(pool, **bad)


# ---------------------------------------------------------------- API
def test_generate_from_profile_saves_a_complete_plan(alice):
    onboard(alice, goal="muscle_gain", experience="intermediate", days=4, minutes=60)
    plan = generate(alice)
    assert plan["kind"] == "generated" and plan["split_type"] == "upper_lower"
    assert plan["name"] == "Upper / lower: Muscle gain" and plan["goal"]["slug"] == "muscle_gain"
    assert plan["days_per_week"] == 4 and plan["duration_minutes"] == 60 and plan["workout_count"] == 4
    assert len(plan["days"]) == 7 and plan["days"][2]["is_rest"] is True
    ex = first_training_day(plan)["exercises"][0]
    assert {"sets", "rep_min", "rep_max", "rest_seconds", "position"} <= ex.keys()
    assert ex["exercise"]["primary_muscle_group"]["slug"] and first_training_day(plan)["estimated_minutes"] > 0
    assert alice.get(f"/api/workouts/{plan['id']}").json() == plan


def test_generate_overrides_profile_values(alice):
    onboard(alice, days=4)
    plan = generate(alice, days_per_week=3, goal_id=alice.get("/api/goals").json()[3]["id"],
                    split_preference="full_body", name="  My plan ", duration_minutes=45)
    assert plan["workout_count"] == 3 and plan["split_type"] == "full_body"
    assert plan["name"] == "My plan" and plan["duration_minutes"] == 45


def test_generate_requires_a_complete_profile(alice):
    res = alice.post("/api/workouts/generate", json={})
    assert res.status_code == 400 and res.json()["error"]["code"] == "profile_incomplete"
    assert "goal" in res.json()["error"]["details"]


@pytest.mark.parametrize("payload", [
    {"days_per_week": 0}, {"days_per_week": 9}, {"duration_minutes": 5}, {"duration_minutes": 999},
    {"split_preference": "custom"}, {"split_preference": "nonsense"}, {"experience_level": "god"},
    {"equipment_ids": "dumbbells"}, {"unknown": 1},
])
def test_generate_validates_input(alice, payload):
    onboard(alice)
    assert alice.post("/api/workouts/generate", json=payload).status_code == 422


def test_generate_rejects_unknown_goal_and_equipment(alice):
    onboard(alice)
    assert alice.post("/api/workouts/generate", json={"goal_id": 9999}).json()["error"]["code"] == "invalid_goal"
    assert alice.post("/api/workouts/generate", json={"equipment_ids": [9999]}).json()["error"]["code"] == "invalid_equipment"


def test_only_the_newest_generated_plan_is_active(alice):
    onboard(alice)
    first, second = generate(alice), generate(alice, days_per_week=3)
    plans = {p["id"]: p for p in alice.get("/api/workouts").json()}
    assert plans[first["id"]]["is_active"] is False and plans[second["id"]]["is_active"] is True


def test_plan_warnings_are_returned(alice):
    onboard(alice, equipment=["bodyweight"], location="home_bodyweight", days=3)
    plan = generate(alice, split_preference="push_pull_legs")
    assert any("biceps" in w for w in plan["warnings"])
