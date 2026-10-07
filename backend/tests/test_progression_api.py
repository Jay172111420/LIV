"""Phase 2 end to end: recommendations from stored data, user responses, history, records, volume, flags."""
from datetime import date, timedelta

import pytest

from app.models import PersonalRecord
from app.services import history_service
from tests.conftest import exercise_id, register

DB = "Barbell bench press"  # 2.5 kg steps, like the examples in the spec
DUMB = "Dumbbell shoulder press"  # 1 kg steps
PUSHUP = "Push-up"


def make_plan(client, name=DB, sets=3, rep_min=8, rep_max=10):
    plan = client.post("/api/workouts/custom", json={"name": "Day", "exercises": [
        {"exercise_id": exercise_id(client, name), "sets": sets, "rep_min": rep_min, "rep_max": rep_max,
         "rest_seconds": 90}]}).json()
    return plan["days"][0]["id"], exercise_id(client, name)


def start(client, day_id):
    res = client.post("/api/workout-sessions/start", json={"plan_day_id": day_id})
    assert res.status_code == 201, res.text
    return res.json()


def do_workout(client, day_id, weight, reps, rir=None):
    """Start, log every set as done, finish: exactly what the app does."""
    s = start(client, day_id)
    sets = s["exercises"][0]["sets"]
    for target, r in zip(sets, reps):
        body = {"weight_kg": weight, "reps": r, "is_completed": True}
        if rir is not None:
            body["rir"] = rir
        assert client.patch(f"/api/workout-sessions/{s['id']}/sets/{target['id']}", json=body).status_code == 200
    done = client.post(f"/api/workout-sessions/{s['id']}/complete", json={})
    assert done.status_code == 200, done.text
    return done.json()


def backfill(client, ex_id, days_ago, sets):
    """A workout logged after the fact: (weight, reps) pairs."""
    res = client.post("/api/workout-sessions", json={
        "performed_on": (date.today() - timedelta(days=days_ago)).isoformat(), "status": "completed",
        "exercises": [{"exercise_id": ex_id, "sets": [
            {"weight_kg": w, "reps": r, "is_completed": True} for w, r in sets]}]})
    assert res.status_code == 201, res.text
    return res.json()


def rec_for(session):
    return session["exercises"][0]["recommendation"]


# ------------------------------------------------------------------ the Phase 2 completion criteria
def test_completing_a_workout_produces_a_recommendation_next_time_from_real_data(alice):
    day, _ = make_plan(alice)
    first = start(alice, day)
    assert rec_for(first)["action"] == "start" and rec_for(first)["weight_kg"] is None  # nothing stored yet
    alice.delete(f"/api/workout-sessions/{first['id']}")

    do_workout(alice, day, 80, [10, 10, 10])
    second = start(alice, day)
    rec = rec_for(second)
    assert (rec["action"], rec["weight_kg"], rec["rep_min"], rec["rep_max"], rec["sets"]) == \
        ("increase_weight", 82.5, 8, 10, 3)
    assert "top of your target range" in rec["reason"]
    assert [(s["weight_kg"], s["reps"]) for s in rec["last_session"]["sets"]] == [(80, 10)] * 3
    assert rec["user_choice"] == "pending"


def test_the_recommendation_is_frozen_for_the_whole_workout(alice):
    day, ex = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    s = start(alice, day)
    before = rec_for(s)
    backfill(alice, ex, 0, [(100, 5)])  # new data arrives mid-workout
    after = alice.get(f"/api/workout-sessions/{s['id']}").json()
    assert rec_for(after) == before


def test_phase_1_prefill_from_the_last_session_still_works(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 9, 8])
    s = start(alice, day)
    assert [(x["weight_kg"], x["reps"]) for x in s["exercises"][0]["sets"]] == [(80, 10), (80, 9), (80, 8)]


def test_failed_workout_holds_the_weight(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [8, 7, 6])
    rec = rec_for(start(alice, day))
    assert rec["action"] == "maintain" and rec["weight_kg"] == 80


def test_two_failures_reduce_the_weight_then_recovery_resumes_progression(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [8, 7, 6])
    do_workout(alice, day, 80, [8, 7, 6])
    rec = rec_for(start(alice, day))
    assert rec["action"] == "reduce_weight" and rec["weight_kg"] == 75.0


def test_rir_is_used_when_logged_and_optional_when_not(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10], rir=4)
    assert rec_for(start(alice, day))["weight_kg"] == 85.0


def test_bodyweight_exercise_recommends_reps_not_weight(alice):
    day, _ = make_plan(alice, PUSHUP, rep_min=8, rep_max=20)
    s = start(alice, day)
    for t in s["exercises"][0]["sets"]:
        alice.patch(f"/api/workout-sessions/{s['id']}/sets/{t['id']}", json={"reps": 10, "is_completed": True})
    alice.post(f"/api/workout-sessions/{s['id']}/complete", json={})
    rec = rec_for(start(alice, day))
    assert rec["weight_kg"] is None and rec["action"] == "increase_reps" and rec["reps_goal"] == 11
    assert rec["strategy"] == "rep_progression"


# ------------------------------------------------------------------ preview endpoint
def test_preview_uses_stored_history_and_the_exercise_defaults(alice):
    ex = exercise_id(alice, DUMB)
    empty = alice.get(f"/api/exercises/{ex}/recommendation").json()
    assert empty["action"] == "start" and empty["weight_kg"] is None and empty["last_session"] is None
    assert empty["id"] is None
    backfill(alice, ex, 3, [(30, 12)] * 3)
    rec = alice.get(f"/api/exercises/{ex}/recommendation").json()
    assert rec["weight_kg"] == 31.0 and rec["increment_kg"] == 1.0  # dumbbell step, rep range 8-12 default


def test_preview_accepts_a_custom_target_and_validates_it(alice):
    ex = exercise_id(alice, DUMB)
    backfill(alice, ex, 3, [(30, 10)] * 3)
    rec = alice.get(f"/api/exercises/{ex}/recommendation", params={"rep_min": 6, "rep_max": 10, "sets": 4}).json()
    assert (rec["rep_min"], rec["rep_max"], rec["sets"], rec["weight_kg"]) == (6, 10, 4, 30)  # only 3 sets: short
    assert alice.get(f"/api/exercises/{ex}/recommendation", params={"rep_min": 10, "rep_max": 6}).status_code == 400
    assert alice.get("/api/exercises/999999/recommendation").status_code == 404


def test_preview_defaults_to_how_the_user_last_trained_the_exercise(alice):
    day, ex = make_plan(alice, DB, sets=3, rep_min=6, rep_max=7)  # differs from the library default for this lift
    do_workout(alice, day, 80, [7, 7, 7])
    rec = alice.get(f"/api/exercises/{ex}/recommendation").json()
    assert (rec["rep_min"], rec["rep_max"], rec["sets"], rec["weight_kg"], rec["action"]) == (6, 7, 3, 82.5, "increase_weight")


# ------------------------------------------------------------------ user control
def respond(client, s, body):
    we = s["exercises"][0]
    return client.post(f"/api/workout-sessions/{s['id']}/exercises/{we['id']}/recommendation", json=body)


def test_accepting_applies_the_suggestion_to_unfinished_sets_and_records_it(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    s = start(alice, day)
    res = respond(alice, s, {"choice": "accepted"})
    assert res.status_code == 200
    ex = res.json()["exercises"][0]
    assert all(x["weight_kg"] == 82.5 and x["reps"] == 8 for x in ex["sets"])
    assert (ex["recommendation"]["user_choice"], ex["recommendation"]["chosen_weight_kg"]) == ("accepted", 82.5)


def test_editing_applies_the_users_numbers_and_records_the_edit(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    s = start(alice, day)
    ex = respond(alice, s, {"choice": "edited", "weight_kg": 81, "reps": 9}).json()["exercises"][0]
    assert all((x["weight_kg"], x["reps"]) == (81, 9) for x in ex["sets"])
    r = ex["recommendation"]
    assert (r["user_choice"], r["chosen_weight_kg"], r["chosen_reps"], r["weight_kg"]) == ("edited", 81, 9, 82.5)


def test_ignoring_changes_nothing_but_is_recorded(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    s = start(alice, day)
    ex = respond(alice, s, {"choice": "ignored"}).json()["exercises"][0]
    assert all(x["weight_kg"] == 80 for x in ex["sets"])
    assert ex["recommendation"]["user_choice"] == "ignored"


def test_completed_sets_are_never_overwritten_by_accepting(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    s = start(alice, day)
    first = s["exercises"][0]["sets"][0]
    alice.patch(f"/api/workout-sessions/{s['id']}/sets/{first['id']}", json={"weight_kg": 80, "reps": 10, "is_completed": True})
    sets = respond(alice, s, {"choice": "accepted"}).json()["exercises"][0]["sets"]
    assert sets[0]["weight_kg"] == 80 and sets[1]["weight_kg"] == 82.5


def test_accepting_a_deload_removes_the_extra_unfinished_set(alice):
    day, _ = make_plan(alice)
    for _ in range(3):
        do_workout(alice, day, 80, [7, 6, 6])
    s = start(alice, day)
    assert rec_for(s)["action"] == "deload" and rec_for(s)["sets"] == 2
    ex = respond(alice, s, {"choice": "accepted"}).json()["exercises"][0]
    assert len(ex["sets"]) == 2 and all(x["weight_kg"] == 72.5 for x in ex["sets"])


@pytest.mark.parametrize("body", [
    {"choice": "edited"}, {"choice": "accepted", "weight_kg": 50}, {"choice": "ignored", "reps": 5},
    {"choice": "maybe"}, {"choice": "edited", "weight_kg": -1}, {"choice": "edited", "reps": 0},
    {"choice": "edited", "weight_kg": 1, "extra": 1}])
def test_invalid_responses_are_rejected(alice, body):
    day, _ = make_plan(alice)
    s = start(alice, day)
    assert respond(alice, s, body).status_code == 422


def test_cannot_respond_after_finishing_or_for_someone_elses_workout(alice, bob):
    day, _ = make_plan(alice)
    finished = do_workout(alice, day, 80, [10, 10, 10])
    assert respond(alice, finished, {"choice": "ignored"}).status_code == 409
    day2, _ = make_plan(alice)
    s = start(alice, day2)
    assert respond(bob, s, {"choice": "ignored"}).status_code == 404
    assert alice.post(f"/api/workout-sessions/{s['id']}/exercises/999999/recommendation",
                      json={"choice": "ignored"}).status_code == 404


def test_the_choice_and_outcome_are_stored_when_the_workout_finishes(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    s = start(alice, day)
    respond(alice, s, {"choice": "accepted"})
    for t in alice.get(f"/api/workout-sessions/{s['id']}").json()["exercises"][0]["sets"]:
        alice.patch(f"/api/workout-sessions/{s['id']}/sets/{t['id']}", json={"reps": 9, "is_completed": True})
    r = rec_for(alice.post(f"/api/workout-sessions/{s['id']}/complete", json={}).json())
    assert (r["user_choice"], r["performed_weight_kg"], r["followed"]) == ("accepted", 82.5, True)


def test_overriding_a_suggestion_is_respected_and_the_next_recommendation_follows_the_real_lift(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    s = start(alice, day)
    respond(alice, s, {"choice": "ignored"})
    for t in s["exercises"][0]["sets"]:  # lifts 80 again instead of the suggested 82.5
        alice.patch(f"/api/workout-sessions/{s['id']}/sets/{t['id']}", json={"weight_kg": 80, "reps": 9, "is_completed": True})
    done = rec_for(alice.post(f"/api/workout-sessions/{s['id']}/complete", json={}).json())
    assert done["followed"] is False and done["performed_weight_kg"] == 80
    nxt = rec_for(start(alice, day))
    assert nxt["weight_kg"] == 80 and nxt["action"] == "increase_reps"  # based on 80 x 9, not on 82.5
    assert any(f["code"] == "override_noted" for f in nxt["flags"])


def test_workouts_without_a_recommendation_still_work(alice):
    ex = exercise_id(alice, DB)
    s = backfill(alice, ex, 2, [(30, 10)])
    assert rec_for(s) is None and s["records"] == []


# ------------------------------------------------------------------ settings
def test_strategy_and_increment_can_be_set_per_exercise(alice):
    day, ex = make_plan(alice, DUMB)
    assert alice.get(f"/api/exercises/{ex}/progression-settings").json() == {
        "strategy": "auto", "increment_kg": None, "effective_increment_kg": 1.0, "default_increment_kg": 1.0,
        "category": "dumbbells", "uses_weight": True}
    res = alice.put(f"/api/exercises/{ex}/progression-settings", json={"increment_kg": 2})
    assert res.json()["effective_increment_kg"] == 2 and res.json()["increment_kg"] == 2
    do_workout(alice, day, 20, [10, 10, 10])
    assert rec_for(start(alice, day))["weight_kg"] == 22


def test_hold_strategy_turns_progression_off(alice):
    day, ex = make_plan(alice, DUMB)
    alice.put(f"/api/exercises/{ex}/progression-settings", json={"strategy": "hold"})
    do_workout(alice, day, 20, [10, 10, 10])
    rec = rec_for(start(alice, day))
    assert rec["action"] == "hold" and rec["weight_kg"] == 20


def test_settings_reset_with_auto_and_validate(alice):
    ex = exercise_id(alice, DB)
    alice.put(f"/api/exercises/{ex}/progression-settings", json={"strategy": "hold", "increment_kg": 3})
    reset = alice.put(f"/api/exercises/{ex}/progression-settings", json={"strategy": "auto"}).json()
    assert reset["strategy"] == "auto" and reset["increment_kg"] is None
    assert alice.put(f"/api/exercises/{ex}/progression-settings", json={"increment_kg": 0}).status_code == 422
    assert alice.put(f"/api/exercises/{ex}/progression-settings", json={"strategy": "nope"}).status_code == 422
    assert alice.put("/api/exercises/999999/progression-settings", json={}).status_code == 404


def test_equipment_category_increments_are_configurable(alice):
    items = {i["category"]: i for i in alice.get("/api/progress/increments").json()}
    assert items["barbell"]["effective_kg"] == 2.5 and items["dumbbells"]["effective_kg"] == 1.0
    assert items["machines"]["custom_kg"] is None
    res = alice.put("/api/progress/increments/machines", json={"increment_kg": 5}).json()
    assert next(i for i in res if i["category"] == "machines")["effective_kg"] == 5
    ex = exercise_id(alice, "Machine chest press")
    backfill(alice, ex, 3, [(50, 12)] * 3)
    assert alice.get(f"/api/exercises/{ex}/recommendation").json()["weight_kg"] == 55
    reset = alice.put("/api/progress/increments/machines", json={"increment_kg": None}).json()
    assert next(i for i in reset if i["category"] == "machines")["custom_kg"] is None
    assert alice.put("/api/progress/increments/spaceship", json={"increment_kg": 1}).status_code == 404


def test_exercise_setting_beats_the_category_default(alice):
    alice.put("/api/progress/increments/dumbbells", json={"increment_kg": 2})
    ex = exercise_id(alice, DUMB)
    backfill(alice, ex, 3, [(20, 12)] * 3)
    assert alice.get(f"/api/exercises/{ex}/recommendation").json()["weight_kg"] == 22
    alice.put(f"/api/exercises/{ex}/progression-settings", json={"increment_kg": 4})
    assert alice.get(f"/api/exercises/{ex}/recommendation").json()["weight_kg"] == 24


def test_imperial_users_get_plate_friendly_defaults(alice):
    assert alice.put("/api/profile", json={"unit_preference": "imperial"}).status_code == 200
    items = {i["category"]: i["default_kg"] for i in alice.get("/api/progress/increments").json()}
    assert items["barbell"] == 2.27


# ------------------------------------------------------------------ history
def test_exercise_history_summarises_real_sessions(alice):
    ex = exercise_id(alice, DB)
    backfill(alice, ex, 14, [(30, 10), (30, 10), (30, 9)])
    backfill(alice, ex, 7, [(32, 8), (32, 8), (32, 7)])
    h = alice.get(f"/api/exercises/{ex}/history").json()
    assert (h["session_count"], h["total_sets"], h["uses_weight"]) == (2, 6, True)
    assert h["best"]["weight_kg"] == 32 and h["best"]["weight_reps"] == 8 and h["best"]["reps"] == 10
    assert h["best"]["estimated_1rm_kg"] == 40.5  # 32 x (1 + 8/30), rounded
    assert h["total_volume_kg"] == 3 * 30 * 10 - 30 + 32 * 8 * 2 + 32 * 7  # 870 + 480... computed from sets
    recent = h["recent_sessions"]
    assert recent[0]["performed_on"] > recent[1]["performed_on"]  # newest first
    assert recent[0]["volume_kg"] == 32 * 8 * 2 + 32 * 7
    assert any("estimate" in n.lower() for n in h["notes"])


def test_history_for_an_exercise_never_done_is_empty_not_invented(alice):
    h = alice.get(f"/api/exercises/{exercise_id(alice, DB)}/history").json()
    assert h["session_count"] == 0 and h["recent_sessions"] == [] and h["best"]["weight_kg"] is None
    assert h["trend"]["direction"] == "insufficient_data"


def test_history_trend_improving(alice):
    ex = exercise_id(alice, DB)
    for i, w in enumerate([20, 21, 22, 24, 25, 27]):
        backfill(alice, ex, 42 - i * 7, [(w, 10)] * 3)
    t = alice.get(f"/api/exercises/{ex}/history").json()["trend"]
    assert t["direction"] == "improving" and len(t["points"]) == 6 and t["metric"] == "estimated_1rm_kg"


def test_history_is_private_to_each_user(alice, bob):
    ex = exercise_id(alice, DB)
    backfill(alice, ex, 3, [(30, 10)] * 3)
    assert bob.get(f"/api/exercises/{ex}/history").json()["session_count"] == 0
    assert bob.get("/api/progress/records").json() == []
    assert bob.get("/api/progress/exercises").json() == []


def test_trained_exercise_list(alice):
    ex = exercise_id(alice, DB)
    backfill(alice, ex, 9, [(30, 10)] * 3)
    backfill(alice, ex, 2, [(32, 10)] * 3)
    items = alice.get("/api/progress/exercises").json()
    assert [(i["name"], i["session_count"], i["best_weight_kg"]) for i in items] == [(DB, 2, 32)]


# ------------------------------------------------------------------ records
def test_records_are_stored_and_returned_with_the_completed_workout(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    done = do_workout(alice, day, 82.5, [8, 8, 8])
    kinds = {r["record_type"]: r for r in done["records"]}
    assert (kinds["weight"]["value"], kinds["weight"]["reps"], kinds["weight"]["previous_value"]) == (82.5, 8, 80)
    assert kinds["weight"]["exercise_name"] == DB
    feed = alice.get("/api/progress/records").json()
    assert {r["record_type"] for r in feed} == {r["record_type"] for r in done["records"]}


def test_first_workout_is_a_baseline(alice):
    day, _ = make_plan(alice)
    assert do_workout(alice, day, 80, [10, 10, 10])["records"] == []


def test_rep_and_volume_records(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    done = do_workout(alice, day, 80, [11, 10, 10])
    assert {r["record_type"] for r in done["records"]} == {"reps", "volume"}


def test_backdated_workouts_recompute_records_in_date_order(alice):
    ex = exercise_id(alice, DB)
    backfill(alice, ex, 5, [(30, 10)] * 3)
    backfill(alice, ex, 20, [(25, 10)] * 3)  # older, logged later: the 30 kg session is now the record
    feed = alice.get("/api/progress/records", params={"exercise_id": ex}).json()
    assert [r["record_type"] for r in feed if r["record_type"] == "weight"] == ["weight"]
    assert next(r for r in feed if r["record_type"] == "weight")["value"] == 30


def test_record_feed_filters_and_limits(alice):
    day, _ = make_plan(alice)
    do_workout(alice, day, 80, [10, 10, 10])
    do_workout(alice, day, 82.5, [8, 8, 8])
    assert len(alice.get("/api/progress/records", params={"limit": 1}).json()) == 1
    assert alice.get("/api/progress/records", params={"exercise_id": exercise_id(alice, PUSHUP)}).json() == []
    assert alice.get("/api/progress/records", params={"limit": 0}).status_code == 422


def test_backfill_builds_records_for_phase_1_data_once(alice, session_factory):
    ex = exercise_id(alice, DB)
    backfill(alice, ex, 14, [(30, 10)] * 3)
    backfill(alice, ex, 7, [(32, 8)] * 3)
    with session_factory() as db:
        db.query(PersonalRecord).delete()
        db.commit()
        assert history_service.backfill_records(db) > 0
        assert db.query(PersonalRecord).count() > 0
        before = db.query(PersonalRecord).count()
        assert history_service.backfill_records(db) == 0  # already populated: nothing to do
        assert db.query(PersonalRecord).count() == before


# ------------------------------------------------------------------ volume
def test_volume_report_aggregates_by_week_muscle_exercise_and_workout(alice):
    ex = exercise_id(alice, DB)
    backfill(alice, ex, 0, [(30, 10)] * 3)
    backfill(alice, ex, 1, [(20, 10)] * 2)
    r = alice.get("/api/progress/volume", params={"weeks": 4}).json()
    assert len(r["by_week"]) == 4
    assert sum(w["volume_kg"] for w in r["by_week"]) == 900 + 400
    assert sum(w["sets"] for w in r["by_week"]) == 5
    assert r["by_exercise"][0]["label"] == DB and r["by_exercise"][0]["volume_kg"] == 1300
    assert r["by_muscle_group"][0]["volume_kg"] == 1300 and len(r["by_workout"]) == 2
    assert "rough measure" in r["note"]


def test_volume_ignores_workouts_outside_the_window_and_counts_bodyweight_sets(alice):
    ex, pu = exercise_id(alice, DB), exercise_id(alice, PUSHUP)
    backfill(alice, ex, 200, [(30, 10)] * 3)
    backfill(alice, pu, 1, [(None, 12)] * 3)
    r = alice.get("/api/progress/volume", params={"weeks": 4}).json()
    assert [e["label"] for e in r["by_exercise"]] == [PUSHUP]
    assert (r["by_exercise"][0]["volume_kg"], r["by_exercise"][0]["sets"], r["by_exercise"][0]["reps"]) == (0, 3, 36)


def test_volume_validates_the_window(alice):
    assert alice.get("/api/progress/volume", params={"weeks": 0}).status_code == 422
    assert alice.get("/api/progress/volume", params={"weeks": 100}).status_code == 422


# ------------------------------------------------------------------ flags
def test_decline_flag_appears_in_neutral_language(alice):
    ex = exercise_id(alice, DB)
    for ago, w in [(35, 40), (28, 40), (21, 40), (14, 40), (7, 33), (2, 32)]:
        backfill(alice, ex, ago, [(w, 10)] * 3)
    report = alice.get("/api/progress/flags").json()
    assert [e["name"] for e in report["exercises"]] == [DB]
    assert report["exercises"][0]["flag"]["message"] == "Your recent performance is below your normal trend."
    assert alice.get(f"/api/exercises/{ex}/history").json()["flags"][0]["code"] == "performance_decline"
    assert alice.get("/api/progress/exercises").json()[0]["flagged"] is True
    assert report["overall"] is None  # one exercise is not a broad pattern


def test_no_flags_with_steady_numbers_or_stale_data(alice):
    ex = exercise_id(alice, DB)
    for ago in (30, 23, 16, 9, 2):
        backfill(alice, ex, ago, [(30, 10)] * 3)
    assert alice.get("/api/progress/flags").json() == {"exercises": [], "overall": None}
    old = exercise_id(alice, PUSHUP)
    for ago, r in [(200, 20), (190, 20), (180, 20), (170, 12), (160, 12)]:
        backfill(alice, old, ago, [(None, r)] * 3)
    assert alice.get("/api/progress/flags").json()["exercises"] == []  # not trained recently: no flag


def test_endpoints_require_login(client):
    for path in ("/api/progress/records", "/api/progress/volume", "/api/progress/flags", "/api/progress/exercises",
                 "/api/progress/increments", "/api/exercises/1/history", "/api/exercises/1/recommendation"):
        assert client.get(path).status_code == 401
