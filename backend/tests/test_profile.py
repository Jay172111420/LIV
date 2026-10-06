ONBOARDING = {
    "age": 29, "height_cm": 178.5, "weight_kg": 76.2, "sex": "male",
    "experience_level": "intermediate", "training_location": "home_gym",
    "training_days_per_week": 4, "preferred_workout_minutes": 60,
}


def _ids(client, path):
    return {item["slug"]: item["id"] for item in client.get(path).json()}


def test_new_profile_is_empty_and_incomplete(alice):
    body = alice.get("/api/profile").json()
    assert body["age"] is None and body["equipment"] == [] and body["onboarding_complete"] is False
    assert body["unit_preference"] == "metric"


def test_onboarding_persists_everything(alice):
    goals, gear = _ids(alice, "/api/goals"), _ids(alice, "/api/equipment")
    payload = {**ONBOARDING, "goal_id": goals["recomposition"],
               "equipment_ids": [gear["dumbbells"], gear["bench"]],
               "preferred_training_days": [4, 0, 2, 0]}
    res = alice.put("/api/profile", json=payload)
    assert res.status_code == 200
    body = alice.get("/api/profile").json()
    assert body["onboarding_complete"] is True
    assert body["goal"]["slug"] == "recomposition"
    assert {e["slug"] for e in body["equipment"]} == {"dumbbells", "bench"}
    assert body["preferred_training_days"] == [0, 2, 4]
    assert body["height_cm"] == 178.5


def test_profile_update_is_partial(alice):
    goals = _ids(alice, "/api/goals")
    alice.put("/api/profile", json={**ONBOARDING, "goal_id": goals["strength"]})
    alice.put("/api/profile", json={"weight_kg": 80, "unit_preference": "imperial"})
    body = alice.get("/api/profile").json()
    assert body["weight_kg"] == 80 and body["age"] == 29 and body["unit_preference"] == "imperial"
    alice.put("/api/profile", json={"activity_level": "moderate"})
    alice.put("/api/profile", json={"activity_level": None})
    assert alice.get("/api/profile").json()["activity_level"] is None


def test_equipment_can_be_replaced_and_cleared(alice):
    gear = _ids(alice, "/api/equipment")
    alice.put("/api/profile", json={"equipment_ids": [gear["barbell"], gear["squat_rack"]]})
    alice.put("/api/profile", json={"equipment_ids": [gear["bodyweight"]]})
    assert [e["slug"] for e in alice.get("/api/profile").json()["equipment"]] == ["bodyweight"]
    alice.put("/api/profile", json={"equipment_ids": []})
    assert alice.get("/api/profile").json()["equipment"] == []


def test_profile_validation(alice):
    for bad in ({"age": 5}, {"age": "old"}, {"height_cm": 5000}, {"weight_kg": -1},
                {"sex": "robot"}, {"training_days_per_week": 9}, {"preferred_training_days": [7]},
                {"unknown_field": 1}):
        res = alice.put("/api/profile", json=bad)
        assert res.status_code == 422, bad
        assert res.json()["error"]["code"] == "validation_error"


def test_invalid_goal_and_equipment_rejected(alice):
    assert alice.put("/api/profile", json={"goal_id": 9999}).json()["error"]["code"] == "invalid_goal"
    res = alice.put("/api/profile", json={"equipment_ids": [9999]})
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_equipment"


def test_reference_lists_seeded(alice):
    assert {"fat_loss", "muscle_gain", "recomposition", "strength", "general_fitness"} == set(
        _ids(alice, "/api/goals"))
    assert {"barbell", "dumbbells", "cable_machine", "bench", "squat_rack", "pull_up_bar",
            "resistance_bands", "kettlebell", "machines", "bodyweight"} == set(
        _ids(alice, "/api/equipment"))
