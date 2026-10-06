"""Users can never read or change another user's plans, edits, sessions or sets."""
import pytest

from tests.conftest import exercise_id, first_training_day, generate, onboard


@pytest.fixture()
def world(alice, bob):
    onboard(alice)
    plan = generate(alice)
    day = first_training_day(plan)
    custom = alice.post("/api/workouts/custom", json={
        "name": "Alice custom", "exercises": [{"exercise_id": exercise_id(alice, "Push-up")}]}).json()
    session = alice.post("/api/workout-sessions/start", json={"plan_day_id": day["id"]}).json()
    return {"plan": plan, "day": day, "custom": custom, "session": session}


def test_plans_and_days_are_invisible_to_other_users(world, bob):
    plan, day = world["plan"], world["day"]
    assert bob.get(f"/api/workouts/{plan['id']}").status_code == 404
    assert bob.get("/api/workouts").json() == []
    assert bob.patch(f"/api/workouts/{plan['id']}", json={"name": "hacked"}).status_code == 404
    assert bob.delete(f"/api/workouts/{plan['id']}").status_code == 404
    assert bob.patch(f"/api/workouts/{plan['id']}/days/{day['id']}", json={"name": "x"}).status_code == 404


def test_other_users_cannot_edit_exercises(world, bob):
    plan, day = world["plan"], world["day"]
    item = day["exercises"][0]
    base = f"/api/workouts/{plan['id']}/days/{day['id']}"
    ex = exercise_id(bob, "Plank")
    assert bob.post(f"{base}/exercises", json={"exercise_id": ex}).status_code == 404
    assert bob.patch(f"{base}/exercises/{item['id']}", json={"sets": 1}).status_code == 404
    assert bob.delete(f"{base}/exercises/{item['id']}").status_code == 404
    assert bob.put(f"{base}/order", json={"plan_exercise_ids": [item["id"]]}).status_code == 404
    assert bob.get(f"{base}/exercises/{item['id']}/substitutes").status_code == 404
    assert bob.post(f"{base}/exercises/{item['id']}/replace", json={"exercise_id": ex}).status_code == 404


def test_nothing_changed_after_the_attempts(world, alice, bob):
    plan, day = world["plan"], world["day"]
    bob.patch(f"/api/workouts/{plan['id']}", json={"name": "hacked"})
    bob.delete(f"/api/workouts/{plan['id']}/days/{day['id']}/exercises/{day['exercises'][0]['id']}")
    assert alice.get(f"/api/workouts/{plan['id']}").json() == plan


def test_a_plan_id_from_one_user_cannot_be_combined_with_anothers_day(alice, bob, world):
    mine = bob.post("/api/workouts/custom", json={"name": "Bob"}).json()
    other_day = world["day"]["id"]
    assert bob.get(f"/api/workouts/{mine['id']}/days/{other_day}/exercises/1/substitutes").status_code == 404
    assert bob.post(f"/api/workouts/{mine['id']}/days/{other_day}/exercises",
                    json={"exercise_id": exercise_id(bob, "Plank")}).status_code == 404


def test_other_users_cannot_start_from_my_workout(world, bob):
    for day in (world["day"], world["custom"]["days"][0]):
        assert bob.post("/api/workout-sessions/start", json={"plan_day_id": day["id"]}).status_code == 404


def test_sessions_and_sets_are_private(world, bob):
    s = world["session"]
    target = s["exercises"][0]["sets"][0]
    we = s["exercises"][0]
    assert bob.get(f"/api/workout-sessions/{s['id']}").status_code == 404
    assert bob.get("/api/workout-sessions/active").json() is None
    assert bob.get("/api/workout-sessions").json() == []
    assert bob.patch(f"/api/workout-sessions/{s['id']}/sets/{target['id']}", json={"reps": 99}).status_code == 404
    assert bob.post(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets").status_code == 404
    assert bob.delete(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets/{target['id']}").status_code == 404
    assert bob.post(f"/api/workout-sessions/{s['id']}/complete", json={}).status_code == 404
    assert bob.delete(f"/api/workout-sessions/{s['id']}").status_code == 404


def test_set_ids_cannot_be_used_across_sessions(alice, bob, world):
    onboard(bob)
    bobs = bob.post("/api/workouts/custom", json={"name": "B", "exercises": [{"exercise_id": exercise_id(bob, "Push-up")}]}).json()
    bsession = bob.post("/api/workout-sessions/start", json={"plan_day_id": bobs["days"][0]["id"]}).json()
    alices_set = world["session"]["exercises"][0]["sets"][0]["id"]
    # Bob's own session id with Alice's set id must not touch Alice's set.
    assert bob.patch(f"/api/workout-sessions/{bsession['id']}/sets/{alices_set}", json={"reps": 1}).status_code == 404
    still = world["session"]["id"]
    assert world and alice.get(f"/api/workout-sessions/{still}").json()["exercises"][0]["sets"][0]["reps"] != 1


def test_completed_history_is_private_and_untouched(world, alice, bob):
    s = world["session"]
    alice.patch(f"/api/workout-sessions/{s['id']}/sets/{s['exercises'][0]['sets'][0]['id']}",
                json={"reps": 5, "is_completed": True})
    alice.post(f"/api/workout-sessions/{s['id']}/complete", json={})
    assert bob.get("/api/workout-sessions?status=completed").json() == []
    assert len(alice.get("/api/workout-sessions?status=completed").json()) == 1


def test_both_users_can_have_a_workout_in_progress(alice, bob, world):
    onboard(bob)
    bplan = bob.post("/api/workouts/custom", json={"name": "B", "exercises": [{"exercise_id": exercise_id(bob, "Push-up")}]}).json()
    assert bob.post("/api/workout-sessions/start", json={"plan_day_id": bplan["days"][0]["id"]}).status_code == 201


def test_custom_exercises_of_another_user_cannot_enter_a_workout(alice, bob):
    muscle = alice.get("/api/exercises/muscle-groups").json()[0]["id"]
    secret = alice.post("/api/exercises", json={"name": "Secret lift", "primary_muscle_group_id": muscle}).json()
    res = bob.post("/api/workouts/custom", json={"name": "Steal", "exercises": [{"exercise_id": secret["id"]}]})
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_exercise"


def test_all_new_endpoints_require_login(client):
    calls = [
        ("get", "/api/workouts/1"), ("post", "/api/workouts/generate"), ("post", "/api/workouts/custom"),
        ("patch", "/api/workouts/1"), ("delete", "/api/workouts/1"), ("get", "/api/workout-sessions/active"),
        ("post", "/api/workout-sessions/start"), ("patch", "/api/workout-sessions/1/sets/1"),
        ("post", "/api/workout-sessions/1/complete"), ("get", "/api/exercises/1/substitutes"),
    ]
    for method, path in calls:
        res = getattr(client, method)(path, **({"json": {}} if method in ("post", "patch") else {}))
        assert res.status_code == 401, (method, path)
