def _lookup(client):
    muscles = {m["slug"]: m["id"] for m in client.get("/api/exercises/muscle-groups").json()}
    gear = {e["slug"]: e["id"] for e in client.get("/api/equipment").json()}
    return muscles, gear


def test_library_is_seeded_and_retrievable(alice):
    items = alice.get("/api/exercises?limit=100").json()
    assert len(items) >= 20 and all(not i["is_custom"] for i in items)
    one = alice.get(f"/api/exercises/{items[0]['id']}")
    assert one.status_code == 200 and one.json()["name"] == items[0]["name"]
    assert alice.get("/api/exercises/999999").status_code == 404


def test_exercises_support_zero_one_and_many_equipment(alice):
    by_name = {i["name"]: i for i in alice.get("/api/exercises?limit=100").json()}
    assert by_name["Push-up"]["equipment"] == []
    assert [e["slug"] for e in by_name["Goblet squat"]["equipment"]] == ["dumbbells"]
    assert {e["slug"] for e in by_name["Barbell bench press"]["equipment"]} == {"barbell", "bench"}


def test_filters(alice):
    muscles, gear = _lookup(alice)
    chest = alice.get(f"/api/exercises?muscle_group_id={muscles['chest']}").json()
    assert chest and all(i["primary_muscle_group"]["slug"] == "chest" for i in chest)
    barbell = alice.get(f"/api/exercises?equipment_id={gear['barbell']}").json()
    assert barbell and all("barbell" in {e["slug"] for e in i["equipment"]} for i in barbell)
    assert [i["name"] for i in alice.get("/api/exercises?q=pull-up").json()] == ["Pull-up"]
    assert alice.get("/api/exercises?q=%25").json() == []  # wildcard is escaped, not matched
    assert alice.get("/api/exercises?limit=0").status_code == 422


def test_create_custom_exercise(alice):
    muscles, gear = _lookup(alice)
    payload = {
        "name": "  Banded push-up ", "primary_muscle_group_id": muscles["chest"],
        "secondary_muscle_group_ids": [muscles["triceps"], muscles["chest"]],
        "movement_pattern": "push", "difficulty": "advanced",
        "equipment_ids": [gear["resistance_bands"]], "instructions": "Loop the band over your back.",
    }
    res = alice.post("/api/exercises", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Banded push-up" and body["is_custom"] is True
    assert [m["slug"] for m in body["secondary_muscle_groups"]] == ["triceps"]
    assert alice.get(f"/api/exercises/{body['id']}").json()["id"] == body["id"]
    assert alice.post("/api/exercises", json=payload).json()["error"]["code"] == "duplicate_exercise"


def test_create_exercise_validation(alice):
    muscles, _ = _lookup(alice)
    assert alice.post("/api/exercises", json={"name": "x"}).status_code == 422
    bad = {"name": "Mystery lift", "primary_muscle_group_id": 9999}
    assert alice.post("/api/exercises", json=bad).json()["error"]["code"] == "invalid_muscle_group"
    bad = {"name": "Mystery lift", "primary_muscle_group_id": muscles["chest"], "equipment_ids": [9999]}
    assert alice.post("/api/exercises", json=bad).json()["error"]["code"] == "invalid_equipment"
    bad = {"name": "Mystery lift", "primary_muscle_group_id": muscles["chest"], "movement_pattern": "teleport"}
    assert alice.post("/api/exercises", json=bad).status_code == 422
