"""Equipment filtering is critical: an exercise needing unavailable equipment must NEVER be prescribed."""
import itertools

import pytest

from app.engine import EquipmentFilter, GenerationInput, WorkoutGenerator

HOME_KIT = frozenset({"dumbbells", "bench", "resistance_bands"})
ALL_GEAR = frozenset({"dumbbells", "barbell", "kettlebell", "bench", "squat_rack", "pull_up_bar",
                      "cable_machine", "machines", "resistance_bands"})
GOALS = ["fat_loss", "muscle_gain", "recomposition", "strength", "general_fitness"]
LEVELS = ["beginner", "intermediate", "advanced"]


def names(plan):
    return {e.name for d in plan.days for e in d.exercises}


def test_filter_requires_every_piece_of_equipment(pool):
    by_name = {e.name: e for e in pool}
    squat = by_name["Barbell back squat"]  # barbell + squat rack
    assert not EquipmentFilter({"barbell"}).allows(squat)
    assert not EquipmentFilter({"squat_rack"}).allows(squat)
    assert EquipmentFilter({"barbell", "squat_rack"}).allows(squat)
    assert EquipmentFilter(set()).allows(by_name["Push-up"])  # bodyweight is always available


def test_home_bodyweight_location_ignores_heavy_gear(pool):
    f = EquipmentFilter({"dumbbells", "barbell", "resistance_bands"}, "home_bodyweight")
    assert f.available == {"bodyweight", "resistance_bands"}
    assert f.ignored == {"dumbbells", "barbell"}


def test_spec_example_dumbbells_bench_bands_never_get_gym_exercises(pool):
    gen = WorkoutGenerator(pool)
    for goal, level, days in itertools.product(GOALS, LEVELS, range(1, 8)):
        plan = gen.generate(GenerationInput(goal, level, days, 60, HOME_KIT, "home_gym"))
        used = names(plan)
        assert used, (goal, level, days)
        assert not used & {"Barbell back squat", "Cable crossover", "Leg press", "Lat pulldown",
                           "Barbell bench press", "Pull-up"}


@pytest.mark.parametrize("gear", [
    frozenset(), frozenset({"dumbbells"}), HOME_KIT, frozenset({"resistance_bands", "pull_up_bar"}),
    frozenset({"machines", "cable_machine"}), frozenset({"barbell"}), ALL_GEAR,
])
@pytest.mark.parametrize("split", ["auto", "full_body", "upper_lower", "push_pull_legs", "push_pull", "bro_split"])
def test_no_plan_ever_uses_unavailable_equipment(pool, gear, split):
    by_id = {e.id: e for e in pool}
    gen = WorkoutGenerator(pool)
    for goal, level, days in itertools.product(GOALS, LEVELS, (2, 4, 5, 6)):
        plan = gen.generate(GenerationInput(goal, level, days, 60, gear, "commercial_gym", split))
        for d in plan.days:
            for e in d.exercises:
                assert (by_id[e.exercise_id].equipment - {"bodyweight"}) <= gear, (e.name, gear)


def test_experience_limits_are_never_exceeded(pool):
    by_id = {e.id: e for e in pool}
    order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    gen = WorkoutGenerator(pool)
    for level in LEVELS:
        plan = gen.generate(GenerationInput("strength", level, 4, 60, ALL_GEAR, "commercial_gym"))
        for d in plan.days:
            for e in d.exercises:
                assert order[by_id[e.exercise_id].min_experience] <= order[level], (level, e.name)


def test_beginners_get_no_barbell_squat_but_still_get_a_squat(pool):
    plan = WorkoutGenerator(pool).generate(GenerationInput("strength", "beginner", 3, 60, ALL_GEAR, "commercial_gym"))
    used = names(plan)
    assert "Barbell back squat" not in used
    assert used & {"Goblet squat", "Leg press", "Bodyweight squat", "Hack squat"}


def test_missing_equipment_is_reported_not_faked(pool):
    plan = WorkoutGenerator(pool).generate(GenerationInput("muscle_gain", "intermediate", 3, 60, frozenset(),
                                                           "home_bodyweight", "push_pull_legs"))
    assert any("biceps" in w for w in plan.warnings)  # no bodyweight biceps exercise exists
    assert "Dumbbell biceps curl" not in names(plan)


def test_api_plan_respects_equipment(alice):
    from tests.conftest import generate, onboard

    onboard(alice, equipment=["dumbbells", "bench", "resistance_bands"], location="home_gym")
    plan = generate(alice)
    seen = {e["exercise"]["name"] for d in plan["days"] for e in d["exercises"]}
    assert seen
    allowed = {"dumbbells", "bench", "resistance_bands"}
    for d in plan["days"]:
        for e in d["exercises"]:
            assert {g["slug"] for g in e["exercise"]["equipment"]} <= allowed
    assert not seen & {"Barbell back squat", "Cable crossover", "Leg press"}
