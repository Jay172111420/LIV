"""A user must never read or change another user's data."""


def _custom_exercise(client, name="Alice secret lift"):
    muscle = client.get("/api/exercises/muscle-groups").json()[0]["id"]
    return client.post("/api/exercises", json={"name": name, "primary_muscle_group_id": muscle}).json()


def test_profiles_are_separate(alice, bob):
    alice.put("/api/profile", json={"age": 33, "weight_kg": 70})
    assert bob.get("/api/profile").json()["age"] is None
    bob.put("/api/profile", json={"age": 41})
    assert alice.get("/api/profile").json()["age"] == 33


def test_custom_exercises_are_private(alice, bob):
    mine = _custom_exercise(alice)
    assert bob.get(f"/api/exercises/{mine['id']}").status_code == 404
    assert "Alice secret lift" not in {i["name"] for i in bob.get("/api/exercises?limit=100").json()}
    assert "Alice secret lift" in {i["name"] for i in alice.get("/api/exercises?limit=100").json()}
    # Bob may reuse the name for his own exercise.
    assert _custom_exercise(bob)["is_custom"] is True


def test_workout_plans_are_private(alice, bob):
    plan = alice.post("/api/workouts", json={"name": "Alice plan", "days_per_week": 3}).json()
    assert alice.get(f"/api/workouts/{plan['id']}").status_code == 200
    assert bob.get(f"/api/workouts/{plan['id']}").status_code == 404
    assert bob.get("/api/workouts").json() == []


def test_workout_sessions_are_private(alice, bob):
    ex = alice.get("/api/exercises").json()[0]["id"]
    session = alice.post("/api/workout-sessions", json={
        "exercises": [{"exercise_id": ex, "sets": [{"weight_kg": 60, "reps": 8}]}]}).json()
    assert bob.get(f"/api/workout-sessions/{session['id']}").status_code == 404
    assert bob.get("/api/workout-sessions").json() == []


def test_cannot_reference_another_users_records(alice, bob):
    plan = alice.post("/api/workouts", json={"name": "Alice plan"}).json()
    secret = _custom_exercise(alice)
    res = bob.post("/api/workout-sessions", json={"plan_id": plan["id"]})
    assert res.status_code == 404
    res = bob.post("/api/workout-sessions", json={"exercises": [{"exercise_id": secret["id"]}]})
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_exercise"


def test_body_metrics_are_private(alice, bob):
    metric = alice.post("/api/body-metrics", json={"metric_type": "weight", "value": 70}).json()
    assert bob.get("/api/body-metrics").json() == []
    assert bob.delete(f"/api/body-metrics/{metric['id']}").status_code == 404
    assert len(alice.get("/api/body-metrics").json()) == 1  # still there


def test_nutrition_profiles_are_separate(alice, bob):
    alice.put("/api/nutrition/profile", json={"calorie_target": 2400, "allergies": ["Peanuts"]})
    body = bob.get("/api/nutrition/profile").json()
    assert body["calorie_target"] is None and body["allergies"] == []


def test_session_cookie_only_grants_own_data(alice, bob):
    assert alice.get("/api/auth/me").json()["email"] == "alice@example.com"
    assert bob.get("/api/auth/me").json()["email"] == "bob@example.com"
