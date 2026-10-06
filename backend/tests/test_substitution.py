"""Substitutions keep the target muscle and movement intent, and respect equipment and experience."""
from app.engine import EquipmentFilter, ExerciseSubstitutionService
from tests.conftest import exercise_id, generate, onboard

ALL_GEAR = {"dumbbells", "barbell", "kettlebell", "bench", "squat_rack", "pull_up_bar",
            "cable_machine", "machines", "resistance_bands"}


def service(pool, gear=ALL_GEAR, level="intermediate", location=None):
    return ExerciseSubstitutionService(pool, EquipmentFilter(gear, location), level)


def names(subs):
    return [s.exercise.name for s in subs]


def test_bench_press_alternatives_match_the_spec_example(pool):
    by_name = {e.name: e for e in pool}
    subs = names(service(pool).candidates(by_name["Barbell bench press"], limit=20))
    for expected in ("Dumbbell bench press", "Push-up", "Machine chest press"):
        assert expected in subs


def test_every_substitute_keeps_muscle_classification_and_pattern(pool):
    svc = service(pool)
    for target in pool:
        for s in svc.candidates(target, limit=50):
            c = s.exercise
            assert c.primary_muscle == target.primary_muscle and c.id != target.id
            assert c.is_compound == target.is_compound
            if target.movement_pattern in ("squat", "hinge", "lunge", "push", "pull") and any(
                    o.exercise.movement_pattern == target.movement_pattern for o in svc.candidates(target, limit=50)):
                assert c.movement_pattern == target.movement_pattern, (target.name, c.name)


def test_substitutes_never_need_unavailable_equipment(pool):
    gear = {"dumbbells", "bench"}
    svc = service(pool, gear)
    for target in pool:
        for s in svc.candidates(target, limit=50):
            assert (s.exercise.equipment - {"bodyweight"}) <= gear


def test_substitutes_respect_experience_and_exclusions(pool):
    by_name = {e.name: e for e in pool}
    beginner = names(service(pool, level="beginner").candidates(by_name["Barbell back squat"], limit=50))
    assert "Barbell back squat" not in beginner and "Goblet squat" in beginner
    subs = service(pool).candidates(by_name["Barbell bench press"], exclude_ids=[by_name["Push-up"].id], limit=50)
    assert "Push-up" not in names(subs)


def test_best_matches_rank_first_and_results_are_deterministic(pool):
    by_name = {e.name: e for e in pool}
    first = service(pool).candidates(by_name["Lat pulldown"], limit=10)
    assert first == service(pool).candidates(by_name["Lat pulldown"], limit=10)
    assert [s.score for s in first] == sorted((s.score for s in first), reverse=True)
    assert all(s.reasons for s in first)


def test_is_valid_substitute_matches_candidates(pool):
    by_name = {e.name: e for e in pool}
    svc = service(pool)
    bench = by_name["Barbell bench press"]
    assert svc.is_valid_substitute(bench, by_name["Dumbbell bench press"])
    assert not svc.is_valid_substitute(bench, by_name["Barbell row"])  # different muscle
    assert not svc.is_valid_substitute(bench, by_name["Dumbbell fly"])  # isolation for a compound
    assert not svc.is_valid_substitute(bench, bench)
    assert not service(pool, {"dumbbells"}).is_valid_substitute(bench, by_name["Dumbbell bench press"])  # no bench


# ---------------------------------------------------------------- API
def _first_with(plan, muscle):
    for d in plan["days"]:
        for e in d["exercises"]:
            if e["exercise"]["primary_muscle_group"]["slug"] == muscle:
                return d, e
    raise AssertionError(muscle)


def test_substitutes_endpoint_for_plan_exercise(alice):
    onboard(alice, equipment=["dumbbells", "bench"], location="home_gym")
    plan = generate(alice)
    day, item = _first_with(plan, "chest")
    res = alice.get(f"/api/workouts/{plan['id']}/days/{day['id']}/exercises/{item['id']}/substitutes")
    assert res.status_code == 200
    subs = res.json()
    assert subs and all(s["exercise"]["primary_muscle_group"]["slug"] == "chest" for s in subs)
    assert all({g["slug"] for g in s["exercise"]["equipment"]} <= {"dumbbells", "bench"} for s in subs)
    assert item["exercise"]["id"] not in {s["exercise"]["id"] for s in subs}
    assert all(s["reasons"] for s in subs)


def test_replace_preserves_workout_intent(alice):
    onboard(alice)
    plan = generate(alice)
    day, item = _first_with(plan, "chest")
    subs = alice.get(f"/api/workouts/{plan['id']}/days/{day['id']}/exercises/{item['id']}/substitutes").json()
    new = subs[0]["exercise"]
    res = alice.post(f"/api/workouts/{plan['id']}/days/{day['id']}/exercises/{item['id']}/replace",
                     json={"exercise_id": new["id"]})
    assert res.status_code == 200
    updated = next(e for e in res.json()["exercises"] if e["id"] == item["id"])
    assert updated["exercise"]["id"] == new["id"]
    for key in ("position", "sets", "rep_min", "rep_max", "rest_seconds"):
        assert updated[key] == item[key], key
    assert [e["position"] for e in res.json()["exercises"]] == list(range(1, len(res.json()["exercises"]) + 1))


def test_replace_rejects_unsuitable_exercises(alice):
    onboard(alice, equipment=["dumbbells", "bench"], location="home_gym")
    plan = generate(alice)
    day, item = _first_with(plan, "chest")
    url = f"/api/workouts/{plan['id']}/days/{day['id']}/exercises/{item['id']}/replace"
    for bad in ("Barbell row", "Cable crossover", "Barbell bench press"):  # wrong muscle / no cable / no barbell
        res = alice.post(url, json={"exercise_id": exercise_id(alice, bad)})
        assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_substitute", bad
    assert alice.post(url, json={"exercise_id": 99999}).json()["error"]["code"] == "invalid_exercise"


def test_replace_switching_between_reps_and_seconds_uses_the_new_defaults(alice):
    onboard(alice, equipment="all")
    plan = generate(alice)
    core_day = next(d for d in plan["days"] if any(e["exercise"]["name"] in ("Plank", "Cable crunch", "Hanging knee raise")
                                                   for e in d["exercises"]))
    item = next(e for e in core_day["exercises"] if e["exercise"]["name"] in ("Plank", "Cable crunch", "Hanging knee raise"))
    target = "Plank" if not item["exercise"]["is_timed"] else "Cable crunch"
    res = alice.post(f"/api/workouts/{plan['id']}/days/{core_day['id']}/exercises/{item['id']}/replace",
                     json={"exercise_id": exercise_id(alice, target)})
    if res.status_code == 200:
        new = next(e for e in res.json()["exercises"] if e["id"] == item["id"])
        assert (new["rep_min"], new["rep_max"]) == (new["exercise"]["rep_min"], new["exercise"]["rep_max"])


def test_exercise_library_substitutes_endpoint(alice):
    onboard(alice, equipment=["dumbbells", "bench", "resistance_bands"], location="home_gym")
    res = alice.get(f"/api/exercises/{exercise_id(alice, 'Barbell bench press')}/substitutes")
    got = {s["exercise"]["name"] for s in res.json()}
    assert {"Dumbbell bench press", "Push-up"} <= got and "Machine chest press" not in got
    assert alice.get("/api/exercises/99999/substitutes").status_code == 404
