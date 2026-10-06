"""Workout plans/sessions, body metrics and nutrition profile basics."""


def test_workout_plan_roundtrip(alice):
    gear = {e["slug"]: e["id"] for e in alice.get("/api/equipment").json()}
    goal = alice.get("/api/goals").json()[0]["id"]
    res = alice.post("/api/workouts", json={
        "name": "Upper / lower", "goal_id": goal, "days_per_week": 4,
        "experience_level": "beginner", "duration_minutes": 45,
        "equipment_ids": [gear["dumbbells"], gear["bench"]]})
    assert res.status_code == 201
    plan = res.json()
    assert plan["is_active"] is True and len(plan["equipment"]) == 2
    assert [p["id"] for p in alice.get("/api/workouts").json()] == [plan["id"]]
    assert alice.post("/api/workouts", json={"name": " "}).status_code == 422
    assert alice.post("/api/workouts", json={"name": "x", "goal_id": 999}).status_code == 400


def test_workout_session_with_sets(alice):
    exercises = alice.get("/api/exercises?limit=2").json()
    res = alice.post("/api/workout-sessions", json={
        "performed_on": "2026-10-01", "status": "completed", "duration_minutes": 50, "notes": "Felt good",
        "exercises": [
            {"exercise_id": exercises[0]["id"], "sets": [
                {"weight_kg": 60, "reps": 8, "rpe": 8, "rir": 2, "rest_seconds": 120, "is_completed": True},
                {"weight_kg": 60, "reps": 7, "is_completed": True}]},
            {"exercise_id": exercises[1]["id"]},
        ]})
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "completed" and [e["position"] for e in body["exercises"]] == [1, 2]
    assert [s["set_number"] for s in body["exercises"][0]["sets"]] == [1, 2]
    assert alice.get(f"/api/workout-sessions/{body['id']}").json()["notes"] == "Felt good"
    assert len(alice.get("/api/workout-sessions").json()) == 1


def test_workout_session_validation(alice):
    ex = alice.get("/api/exercises").json()[0]["id"]
    bad_set = {"exercises": [{"exercise_id": ex, "sets": [{"rpe": 11}]}]}
    assert alice.post("/api/workout-sessions", json=bad_set).status_code == 422
    assert alice.post("/api/workout-sessions", json={"status": "done"}).status_code == 422
    missing = alice.post("/api/workout-sessions", json={"exercises": [{"exercise_id": 999999}]})
    assert missing.json()["error"]["code"] == "invalid_exercise"


def test_body_metrics(alice):
    assert alice.post("/api/body-metrics", json={"metric_type": "weight", "value": 80.5}).json()["unit"] == "kg"
    waist = alice.post("/api/body-metrics", json={"metric_type": "waist", "value": 84}).json()
    assert waist["unit"] == "cm"
    custom = alice.post("/api/body-metrics", json={
        "metric_type": "custom", "custom_label": "Calf", "unit": "cm", "value": 38})
    assert custom.status_code == 201 and custom.json()["custom_label"] == "Calf"

    only_weight = alice.get("/api/body-metrics?metric_type=weight").json()
    assert [m["value"] for m in only_weight] == [80.5]
    assert alice.delete(f"/api/body-metrics/{waist['id']}").status_code == 204
    assert len(alice.get("/api/body-metrics").json()) == 2


def test_body_metric_validation(alice):
    for bad in ({"metric_type": "weight", "value": 900}, {"metric_type": "weight", "value": -5},
                {"metric_type": "custom", "value": 5}, {"metric_type": "bogus", "value": 5},
                {"metric_type": "body_fat", "value": 95}):
        assert alice.post("/api/body-metrics", json=bad).status_code == 422, bad


def test_nutrition_profile(alice):
    assert alice.get("/api/nutrition/profile").json()["dietary_preference"] == "no_preference"
    res = alice.put("/api/nutrition/profile", json={
        "calorie_target": 2300, "protein_g": 170, "carbs_g": 250, "fat_g": 70,
        "dietary_preference": "vegetarian", "allergies": ["Peanuts", " peanuts ", ""],
        "restrictions": ["No pork"]})
    assert res.status_code == 200
    body = alice.get("/api/nutrition/profile").json()
    assert body["calorie_target"] == 2300 and body["allergies"] == ["Peanuts"]
    # Updating only restrictions leaves allergies alone.
    alice.put("/api/nutrition/profile", json={"restrictions": []})
    body = alice.get("/api/nutrition/profile").json()
    assert body["allergies"] == ["Peanuts"] and body["restrictions"] == []
    assert alice.put("/api/nutrition/profile", json={"calorie_target": 50}).status_code == 422
