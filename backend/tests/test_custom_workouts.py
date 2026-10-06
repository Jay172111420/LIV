"""Custom workout creator: create, add, remove, reorder, edit sets/reps/rest, rename, save, reuse."""
import pytest

from tests.conftest import exercise_id, first_training_day, generate, onboard


def create(client, name="Push day", names=("Push-up", "Dumbbell shoulder press", "Dumbbell lateral raise")):
    res = client.post("/api/workouts/custom", json={
        "name": name, "exercises": [{"exercise_id": exercise_id(client, n)} for n in names]})
    assert res.status_code == 201, res.text
    return res.json()


def url(plan, suffix=""):
    return f"/api/workouts/{plan['id']}/days/{plan['days'][0]['id']}{suffix}"


def test_create_custom_workout_with_defaults_from_exercise_metadata(alice):
    plan = create(alice)
    assert plan["kind"] == "custom" and plan["name"] == "Push day" and plan["workout_count"] == 1
    day = plan["days"][0]
    assert day["name"] == "Push day" and [e["position"] for e in day["exercises"]] == [1, 2, 3]
    push_up = day["exercises"][0]
    assert (push_up["sets"], push_up["rep_min"], push_up["rep_max"]) == (3, 8, 20)
    assert push_up["rest_seconds"] > 0 and day["estimated_minutes"] > 0


def test_create_with_explicit_prescription_and_empty_workouts(alice):
    res = alice.post("/api/workouts/custom", json={"name": "Heavy", "exercises": [
        {"exercise_id": exercise_id(alice, "Push-up"), "sets": 5, "rep_min": 3, "rep_max": 5, "rest_seconds": 200}]})
    ex = res.json()["days"][0]["exercises"][0]
    assert (ex["sets"], ex["rep_min"], ex["rep_max"], ex["rest_seconds"]) == (5, 3, 5, 200)
    empty = alice.post("/api/workouts/custom", json={"name": "Blank"})
    assert empty.status_code == 201 and empty.json()["days"][0]["exercises"] == []


def test_add_exercise(alice):
    plan = create(alice, names=("Push-up",))
    res = alice.post(url(plan, "/exercises"), json={"exercise_id": exercise_id(alice, "Plank"), "sets": 2})
    assert res.status_code == 201
    exercises = res.json()["exercises"]
    assert [e["exercise"]["name"] for e in exercises] == ["Push-up", "Plank"] and exercises[1]["sets"] == 2
    again = alice.post(url(plan, "/exercises"), json={"exercise_id": exercise_id(alice, "Plank")})
    assert again.status_code == 400 and again.json()["error"]["code"] == "duplicate_exercise_in_day"


def test_remove_exercise_renumbers_positions(alice):
    plan = create(alice)
    ids = [e["id"] for e in plan["days"][0]["exercises"]]
    res = alice.delete(url(plan, f"/exercises/{ids[0]}"))
    assert res.status_code == 200
    assert [(e["id"], e["position"]) for e in res.json()["exercises"]] == [(ids[1], 1), (ids[2], 2)]
    assert alice.delete(url(plan, f"/exercises/{ids[0]}")).status_code == 404


def test_reorder_exercises(alice):
    plan = create(alice)
    a, b, c = [e["id"] for e in plan["days"][0]["exercises"]]
    res = alice.put(url(plan, "/order"), json={"plan_exercise_ids": [c, a, b]})
    assert [e["id"] for e in res.json()["exercises"]] == [c, a, b]
    assert [e["position"] for e in res.json()["exercises"]] == [1, 2, 3]
    saved = alice.get(f"/api/workouts/{plan['id']}").json()["days"][0]["exercises"]
    assert [e["id"] for e in saved] == [c, a, b]
    for bad in ([a, b], [a, a, b], [a, b, c, 999], [a, b, 999]):
        r = alice.put(url(plan, "/order"), json={"plan_exercise_ids": bad})
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_order", bad


def test_change_sets_reps_and_rest(alice):
    plan = create(alice)
    item = plan["days"][0]["exercises"][0]
    res = alice.patch(url(plan, f"/exercises/{item['id']}"),
                      json={"sets": 4, "rep_min": 6, "rep_max": 8, "rest_seconds": 150, "notes": "Slow negatives"})
    got = res.json()["exercises"][0]
    assert (got["sets"], got["rep_min"], got["rep_max"], got["rest_seconds"], got["notes"]) == (4, 6, 8, 150, "Slow negatives")
    only_rest = alice.patch(url(plan, f"/exercises/{item['id']}"), json={"rest_seconds": 45}).json()["exercises"][0]
    assert only_rest["rest_seconds"] == 45 and only_rest["sets"] == 4  # untouched fields stay
    assert alice.patch(url(plan, f"/exercises/{item['id']}"), json={"notes": None}).json()["exercises"][0]["notes"] is None


@pytest.mark.parametrize("payload,status", [
    ({"sets": 0}, 422), ({"sets": 11}, 422), ({"sets": -1}, 422), ({"rep_min": 0}, 422), ({"rep_min": -3}, 422),
    ({"rest_seconds": -10}, 422), ({"rest_seconds": 9999}, 422), ({"rep_min": 10, "rep_max": 5}, 422),
    ({"rep_min": 50}, 400),  # crosses the stored max (20 for push-ups)
    ({"sets": None}, 400), ({"colour": "red"}, 422),
])
def test_invalid_edits_are_rejected_with_clear_messages(alice, payload, status):
    plan = create(alice)
    item = plan["days"][0]["exercises"][0]
    res = alice.patch(url(plan, f"/exercises/{item['id']}"), json=payload)
    assert res.status_code == status and res.json()["error"]["message"]
    after = alice.get(f"/api/workouts/{plan['id']}").json()["days"][0]["exercises"][0]
    assert after == item  # nothing was saved


def test_validation_messages_are_plain_language(alice):
    plan = create(alice)
    item = plan["days"][0]["exercises"][0]
    details = alice.patch(url(plan, f"/exercises/{item['id']}"), json={"sets": 0}).json()["error"]["details"]
    assert details == [{"field": "sets", "message": "Must be 1 or more."}]


def test_rename_workout_and_day(alice):
    plan = create(alice)
    renamed = alice.patch(f"/api/workouts/{plan['id']}", json={"name": "  Monday push "}).json()
    assert renamed["name"] == "Monday push" and renamed["days"][0]["name"] == "Monday push"
    day = alice.patch(url(plan), json={"name": "Push A"}).json()
    assert day["name"] == "Push A" and alice.get(f"/api/workouts/{plan['id']}").json()["name"] == "Push A"
    assert alice.patch(f"/api/workouts/{plan['id']}", json={"name": "  "}).status_code == 422


def test_saved_custom_workouts_are_listed_and_reusable(alice):
    plan = create(alice)
    listed = alice.get("/api/workouts?kind=custom").json()
    assert [p["id"] for p in listed] == [plan["id"]] and listed[0]["workout_count"] == 1
    assert listed[0]["exercise_count"] == 3 and listed[0]["start_day_id"] == plan["days"][0]["id"]
    blank = alice.post("/api/workouts/custom", json={"name": "Blank"}).json()
    summary = next(p for p in alice.get("/api/workouts?kind=custom").json() if p["id"] == blank["id"])
    assert summary["exercise_count"] == 0 and summary["start_day_id"] is None
    assert alice.get("/api/workouts?kind=generated").json() == []
    assert alice.get(f"/api/workouts/{plan['id']}").json()["days"][0]["exercises"][0]["exercise"]["name"] == "Push-up"


def test_delete_workout_keeps_logged_history(alice):
    plan = create(alice)
    session = alice.post("/api/workout-sessions/start", json={"plan_day_id": plan["days"][0]["id"]}).json()
    s = session["exercises"][0]["sets"][0]
    alice.patch(f"/api/workout-sessions/{session['id']}/sets/{s['id']}", json={"reps": 8, "is_completed": True})
    alice.post(f"/api/workout-sessions/{session['id']}/complete", json={})
    assert alice.delete(f"/api/workouts/{plan['id']}").status_code == 204
    assert alice.get(f"/api/workouts/{plan['id']}").status_code == 404
    history = alice.get("/api/workout-sessions?status=completed").json()
    assert len(history) == 1 and history[0]["plan_id"] is None and history[0]["name"] == "Push day"


def test_creation_validation(alice):
    ex = exercise_id(alice, "Push-up")
    assert alice.post("/api/workouts/custom", json={"name": " "}).status_code == 422
    assert alice.post("/api/workouts/custom", json={"name": "x" * 121}).status_code == 422
    dup = alice.post("/api/workouts/custom", json={"name": "Dup", "exercises": [{"exercise_id": ex}, {"exercise_id": ex}]})
    assert dup.json()["error"]["code"] == "duplicate_exercise_in_day"
    ghost = alice.post("/api/workouts/custom", json={"name": "Ghost", "exercises": [{"exercise_id": 99999}]})
    assert ghost.json()["error"]["code"] == "invalid_exercise"
    assert alice.get("/api/workouts").json() == []  # failed creations leave nothing behind


def test_generated_plans_can_be_edited_too(alice):
    onboard(alice)
    plan = generate(alice)
    day = first_training_day(plan)
    before = len(day["exercises"])
    added = alice.post(f"/api/workouts/{plan['id']}/days/{day['id']}/exercises",
                       json={"exercise_id": exercise_id(alice, "Plank")})
    if added.status_code == 201:
        assert len(added.json()["exercises"]) == before + 1
    rest = next(d for d in plan["days"] if d["is_rest"])
    res = alice.post(f"/api/workouts/{plan['id']}/days/{rest['id']}/exercises", json={"exercise_id": exercise_id(alice, "Plank")})
    assert res.status_code == 400 and res.json()["error"]["code"] == "rest_day"


def test_exercise_limit_per_workout(alice):
    ids = [i["id"] for i in alice.get("/api/exercises?limit=30").json()][:21]
    plan = alice.post("/api/workouts/custom", json={"name": "Big", "exercises": [{"exercise_id": i} for i in ids[:20]]}).json()
    res = alice.post(url(plan, "/exercises"), json={"exercise_id": ids[20]})
    assert res.status_code == 400 and res.json()["error"]["code"] == "too_many_exercises"
