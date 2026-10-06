"""Running a workout: start, log sets, validation, completion, history."""
import pytest

from tests.conftest import exercise_id

PLAN = ("Push-up", "Dumbbell shoulder press")


def make_plan(client, names=PLAN):
    plan = client.post("/api/workouts/custom", json={"name": "Upper", "exercises": [
        {"exercise_id": exercise_id(client, n), "sets": 3, "rep_min": 8, "rep_max": 12, "rest_seconds": 90}
        for n in names]}).json()
    return plan, plan["days"][0]["id"]


def start(client, names=PLAN):
    _, day_id = make_plan(client, names)
    res = client.post("/api/workout-sessions/start", json={"plan_day_id": day_id})
    assert res.status_code == 201, res.text
    return res.json()


def set_url(session, s):
    return f"/api/workout-sessions/{session['id']}/sets/{s['id']}"


def log(client, session, s, **fields):
    return client.patch(set_url(session, s), json=fields)


def test_start_copies_the_plan_into_a_session_with_targets(alice):
    s = start(alice)
    assert s["status"] == "in_progress" and s["name"] == "Upper" and s["started_at"] and s["ended_at"] is None
    assert [e["exercise"]["name"] for e in s["exercises"]] == list(PLAN)
    first = s["exercises"][0]
    assert first["rest_seconds"] == 90 and [x["set_number"] for x in first["sets"]] == [1, 2, 3]
    assert all(x["is_completed"] is False and (x["target_reps_min"], x["target_reps_max"]) == (8, 12) for x in first["sets"])
    assert alice.get("/api/workout-sessions/active").json()["id"] == s["id"]


def test_no_active_session_returns_null(alice):
    assert alice.get("/api/workout-sessions/active").json() is None


def test_log_weight_reps_rpe_rir_notes_and_complete_a_set(alice):
    s = start(alice)
    target = s["exercises"][0]["sets"][0]
    res = log(alice, s, target, weight_kg=82.5, reps=8, rpe=8.5, rir=1, notes="Felt strong", is_completed=True)
    assert res.status_code == 200
    saved = res.json()["exercises"][0]["sets"][0]
    assert (saved["weight_kg"], saved["reps"], saved["rpe"], saved["rir"], saved["notes"], saved["is_completed"]) == (
        82.5, 8, 8.5, 1, "Felt strong", True)
    again = alice.get(f"/api/workout-sessions/{s['id']}").json()["exercises"][0]["sets"][0]
    assert again == saved
    assert log(alice, s, target, is_completed=False).json()["exercises"][0]["sets"][0]["is_completed"] is False


def test_partial_updates_keep_other_fields_and_null_clears(alice):
    s = start(alice)
    target = s["exercises"][0]["sets"][0]
    log(alice, s, target, weight_kg=60, reps=10, rpe=7)
    got = log(alice, s, target, reps=9).json()["exercises"][0]["sets"][0]
    assert (got["weight_kg"], got["reps"], got["rpe"]) == (60, 9, 7)
    cleared = log(alice, s, target, rpe=None).json()["exercises"][0]["sets"][0]
    assert cleared["rpe"] is None and cleared["weight_kg"] == 60


@pytest.mark.parametrize("payload,field", [
    ({"weight_kg": -5}, "weight_kg"), ({"weight_kg": 5000}, "weight_kg"), ({"reps": -1}, "reps"),
    ({"reps": 5000}, "reps"), ({"rpe": 0}, "rpe"), ({"rpe": 11}, "rpe"), ({"rpe": 7.3}, "rpe"),
    ({"rir": -1}, "rir"), ({"rir": 11}, "rir"), ({"notes": "x" * 501}, "notes"), ({"is_completed": None}, "is_completed"),
    ({"weight_kg": "heavy"}, "weight_kg"),
])
def test_invalid_set_values_are_rejected(alice, payload, field):
    s = start(alice)
    target = s["exercises"][0]["sets"][0]
    res = log(alice, s, target, **payload)
    assert res.status_code == 422
    assert field in {d["field"] for d in res.json()["error"]["details"]}
    assert alice.get(f"/api/workout-sessions/{s['id']}").json()["exercises"][0]["sets"][0]["weight_kg"] is None


def test_a_set_cannot_be_completed_without_reps(alice):
    s = start(alice)
    target = s["exercises"][0]["sets"][0]
    for payload in ({"is_completed": True}, {"reps": 0, "is_completed": True}):
        res = log(alice, s, target, **payload)
        assert res.status_code == 400 and res.json()["error"]["code"] == "set_incomplete"
    assert log(alice, s, target, reps=5, is_completed=True).status_code == 200
    assert log(alice, s, target, reps=0).status_code == 400  # can't zero the reps of a completed set


def test_add_and_remove_sets(alice):
    s = start(alice)
    we = s["exercises"][0]
    log(alice, s, we["sets"][-1], weight_kg=40, reps=10)
    added = alice.post(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets")
    assert added.status_code == 201
    sets = added.json()["exercises"][0]["sets"]
    assert [x["set_number"] for x in sets] == [1, 2, 3, 4] and (sets[3]["weight_kg"], sets[3]["reps"]) == (40, 10)
    removed = alice.delete(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets/{sets[1]['id']}")
    assert [x["set_number"] for x in removed.json()["exercises"][0]["sets"]] == [1, 3, 4]
    nxt = alice.post(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets").json()["exercises"][0]["sets"]
    assert nxt[-1]["set_number"] == 5  # numbers never collide


def test_cannot_remove_the_last_set_or_exceed_the_limit(alice):
    s = start(alice)
    we = s["exercises"][0]
    for x in we["sets"][:2]:
        alice.delete(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets/{x['id']}")
    last = alice.get(f"/api/workout-sessions/{s['id']}").json()["exercises"][0]["sets"][0]
    res = alice.delete(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets/{last['id']}")
    assert res.status_code == 400 and res.json()["error"]["code"] == "last_set"
    for _ in range(19):
        alice.post(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets")
    over = alice.post(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/sets")
    assert over.status_code == 400 and over.json()["error"]["code"] == "too_many_sets"


def test_only_one_workout_can_be_in_progress(alice):
    s = start(alice)
    res = alice.post("/api/workout-sessions/start", json={"plan_day_id": s["plan_day_id"]})
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "workout_in_progress" and err["details"] == {"session_id": s["id"]}


def test_complete_workout_saves_history(alice):
    s = start(alice)
    a, b = s["exercises"]
    log(alice, s, a["sets"][0], weight_kg=0, reps=12, is_completed=True)
    log(alice, s, a["sets"][1], weight_kg=0, reps=10, is_completed=True)
    log(alice, s, b["sets"][0], weight_kg=20, reps=8, rpe=8, is_completed=True)
    res = alice.post(f"/api/workout-sessions/{s['id']}/complete", json={"notes": "Good one"})
    assert res.status_code == 200
    done = res.json()
    assert done["status"] == "completed" and done["ended_at"] and done["duration_minutes"] >= 1 and done["notes"] == "Good one"
    # Skipped (uncompleted) sets are dropped; history holds only what was actually done.
    assert [len(e["sets"]) for e in done["exercises"]] == [2, 1]
    assert all(x["is_completed"] for e in done["exercises"] for x in e["sets"])
    history = alice.get("/api/workout-sessions?status=completed").json()
    assert [h["id"] for h in history] == [s["id"]]
    h = history[0]
    assert h["performed_on"] and h["name"] == "Upper" and h["exercises"][1]["sets"][0]["weight_kg"] == 20
    assert alice.get("/api/workout-sessions/active").json() is None
    assert alice.get("/api/workout-sessions?status=in_progress").json() == []


def test_exercises_with_no_completed_sets_are_left_out_of_history(alice):
    s = start(alice)
    log(alice, s, s["exercises"][1]["sets"][0], reps=8, is_completed=True)
    done = alice.post(f"/api/workout-sessions/{s['id']}/complete", json={}).json()
    assert [e["exercise"]["name"] for e in done["exercises"]] == ["Dumbbell shoulder press"]


def test_cannot_complete_without_any_completed_set(alice):
    s = start(alice)
    res = alice.post(f"/api/workout-sessions/{s['id']}/complete", json={})
    assert res.status_code == 400 and res.json()["error"]["code"] == "no_completed_sets"
    assert alice.get("/api/workout-sessions/active").json()["id"] == s["id"]


@pytest.mark.parametrize("duration,status", [(0, 422), (-5, 422), (601, 422), (300, 400), (1, 200), (None, 200)])
def test_impossible_durations_are_rejected(alice, duration, status):
    s = start(alice)
    log(alice, s, s["exercises"][0]["sets"][0], reps=8, is_completed=True)
    body = {} if duration is None else {"duration_minutes": duration}
    res = alice.post(f"/api/workout-sessions/{s['id']}/complete", json=body)
    assert res.status_code == status, res.text
    if status == 400:
        assert res.json()["error"]["code"] == "invalid_duration" and "since you started" in res.json()["error"]["message"]


def test_finished_workouts_cannot_be_changed(alice):
    s = start(alice)
    target = s["exercises"][0]["sets"][0]
    log(alice, s, target, reps=8, is_completed=True)
    alice.post(f"/api/workout-sessions/{s['id']}/complete", json={})
    for res in (log(alice, s, target, reps=99),
                alice.post(f"/api/workout-sessions/{s['id']}/complete", json={}),
                alice.post(f"/api/workout-sessions/{s['id']}/exercises/{s['exercises'][0]['id']}/sets"),
                alice.delete(f"/api/workout-sessions/{s['id']}")):
        assert res.status_code == 409 and res.json()["error"]["code"] == "workout_not_active"
    assert alice.get(f"/api/workout-sessions/{s['id']}").json()["exercises"][0]["sets"][0]["reps"] == 8


def test_discard_removes_an_in_progress_workout(alice):
    s = start(alice)
    assert alice.delete(f"/api/workout-sessions/{s['id']}").status_code == 204
    assert alice.get(f"/api/workout-sessions/{s['id']}").status_code == 404
    assert alice.get("/api/workout-sessions/active").json() is None
    start_again = alice.post("/api/workout-sessions/start", json={"plan_day_id": s["plan_day_id"]})
    assert start_again.status_code == 201


def test_next_session_is_prefilled_from_last_time(alice):
    s = start(alice)
    a = s["exercises"][0]
    log(alice, s, a["sets"][0], weight_kg=50, reps=12, is_completed=True)
    log(alice, s, a["sets"][1], weight_kg=52.5, reps=10, is_completed=True)
    alice.post(f"/api/workout-sessions/{s['id']}/complete", json={})
    nxt = alice.post("/api/workout-sessions/start", json={"plan_day_id": s["plan_day_id"]}).json()
    sets = nxt["exercises"][0]["sets"]
    assert [(x["weight_kg"], x["reps"]) for x in sets] == [(50, 12), (52.5, 10), (52.5, 10)]
    assert all(x["is_completed"] is False for x in sets)


def test_start_validation(alice):
    assert alice.post("/api/workout-sessions/start", json={}).status_code == 422
    assert alice.post("/api/workout-sessions/start", json={"plan_day_id": 999}).status_code == 404
    empty = alice.post("/api/workouts/custom", json={"name": "Empty"}).json()
    res = alice.post("/api/workout-sessions/start", json={"plan_day_id": empty["days"][0]["id"]})
    assert res.status_code == 400 and res.json()["error"]["code"] == "empty_workout"
    _, day = make_plan(alice)
    assert alice.post("/api/workout-sessions/start", json={"plan_day_id": day, "performed_on": "2001-01-01"}).json()[
        "error"]["code"] == "invalid_date"


def test_cannot_start_a_rest_day(alice):
    from tests.conftest import generate, onboard

    onboard(alice)
    plan = generate(alice)
    rest = next(d for d in plan["days"] if d["is_rest"])
    res = alice.post("/api/workout-sessions/start", json={"plan_day_id": rest["id"]})
    assert res.status_code == 400 and res.json()["error"]["code"] == "rest_day"


def test_phase0_bulk_session_endpoint_enforces_the_same_rules(alice):
    ex = exercise_id(alice, "Push-up")
    bad = alice.post("/api/workout-sessions", json={"exercises": [{"exercise_id": ex, "sets": [{"is_completed": True}]}]})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "set_incomplete"
    negative = alice.post("/api/workout-sessions", json={"exercises": [{"exercise_id": ex, "sets": [{"reps": -2}]}]})
    assert negative.status_code == 422


def test_full_flow_generate_start_log_complete_history(alice):
    from tests.conftest import first_training_day, generate, onboard

    onboard(alice, days=3, experience="beginner", goal="general_fitness")
    plan = generate(alice)
    day = first_training_day(plan)
    s = alice.post("/api/workout-sessions/start", json={"plan_day_id": day["id"]}).json()
    assert len(s["exercises"]) == len(day["exercises"])
    for we, planned in zip(s["exercises"], day["exercises"]):
        assert len(we["sets"]) == planned["sets"] and we["rest_seconds"] == planned["rest_seconds"]
    for we in s["exercises"][:2]:
        for x in we["sets"]:
            assert log(alice, s, x, weight_kg=20, reps=10, is_completed=True).status_code == 200
    done = alice.post(f"/api/workout-sessions/{s['id']}/complete", json={}).json()
    assert done["status"] == "completed" and len(done["exercises"]) == 2
    assert alice.get("/api/workout-sessions?status=completed").json()[0]["id"] == s["id"]
