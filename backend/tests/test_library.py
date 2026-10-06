"""The exercise library: complete metadata on every exercise, and a safe, repeatable seed."""
from sqlalchemy import select

from app.models import Exercise
from app.models.enums import ExperienceLevel
from app.seed import seed_reference_data
from app.seed_data.exercise_library import EXERCISE_LIBRARY

ORDER = [ExperienceLevel.beginner, ExperienceLevel.intermediate, ExperienceLevel.advanced]


def test_every_library_exercise_has_valid_metadata():
    from app.seed import EQUIPMENT, MUSCLES

    muscles = {slug for slug, _ in MUSCLES}
    gear = {slug for slug, *_ in EQUIPMENT}
    names = [e["name"] for e in EXERCISE_LIBRARY]
    assert len(names) == len(set(names)), "duplicate exercise names"
    assert len(EXERCISE_LIBRARY) >= 80
    for e in EXERCISE_LIBRARY:
        where = e["name"]
        assert e["description"].strip() and e["instructions"].strip(), where
        assert e["primary"] in muscles and set(e["secondary"]) <= muscles, where
        assert e["primary"] not in e["secondary"], where
        assert set(e["equipment"]) <= gear and "bodyweight" not in e["equipment"], where
        assert 1 <= e["rep_min"] <= e["rep_max"] <= 300, where
        assert 1 <= e["sets"] <= 10, where
        assert ORDER.index(e["min_level"]) <= ORDER.index(e["difficulty"]), where
        if e["type"].value == "compound":
            assert e["is_compound"] and e["secondary"], f"{where}: compound lifts work other muscles too"
        if e["type"].value == "isolation":
            assert not e["is_compound"], where
        if e["is_timed"]:
            assert e["rep_min"] >= 10, f"{where}: timed ranges are seconds"


def test_library_covers_every_main_muscle_group_and_split_pattern():
    primaries = {e["primary"] for e in EXERCISE_LIBRARY}
    assert {"chest", "back", "shoulders", "biceps", "triceps", "quads", "hamstrings", "glutes",
            "calves", "core"} <= primaries
    patterns = {e["pattern"].value for e in EXERCISE_LIBRARY}
    assert {"squat", "hinge", "lunge", "push", "pull", "core", "carry", "rotation"} <= patterns


def test_seed_is_idempotent_and_syncs_library_changes(session_factory):
    with session_factory() as db:
        before = db.scalars(select(Exercise).where(Exercise.owner_user_id.is_(None))).all()
        count = len(before)
        bench = next(e for e in before if e.name == "Barbell bench press")
        bench.rep_min, bench.recommended_sets, bench.is_active = 1, 9, False  # drift from the library
        db.commit()

        seed_reference_data(db)
        seed_reference_data(db)
        after = db.scalars(select(Exercise).where(Exercise.owner_user_id.is_(None))).all()
        assert len(after) == count == len(EXERCISE_LIBRARY)
        bench = next(e for e in after if e.name == "Barbell bench press")
        assert (bench.rep_min, bench.rep_max, bench.recommended_sets, bench.is_active) == (5, 8, 4, True)


def test_api_exposes_full_exercise_metadata(alice):
    ex = next(i for i in alice.get("/api/exercises?q=Barbell bench press").json())
    assert ex["primary_muscle_group"]["slug"] == "chest"
    assert {m["slug"] for m in ex["secondary_muscle_groups"]} == {"triceps", "shoulders"}
    assert ex["movement_pattern"] == "push" and ex["exercise_type"] == "compound"
    assert ex["is_compound"] is True and ex["is_timed"] is False
    assert ex["min_experience_level"] == "intermediate" and ex["difficulty"] == "intermediate"
    assert (ex["rep_min"], ex["rep_max"], ex["recommended_sets"]) == (5, 8, 4)
    assert ex["description"] and ex["instructions"] and ex["is_active"] is True
    assert {e["slug"] for e in ex["equipment"]} == {"barbell", "bench"}


def test_custom_exercise_accepts_new_metadata_and_validates_it(alice):
    muscles = {m["slug"]: m["id"] for m in alice.get("/api/exercises/muscle-groups").json()}
    base = {"name": "Tempo push-up", "primary_muscle_group_id": muscles["chest"]}
    ok = alice.post("/api/exercises", json={**base, "rep_min": 6, "rep_max": 10, "recommended_sets": 4,
                                            "min_experience_level": "advanced", "difficulty": "advanced"})
    assert ok.status_code == 201
    body = ok.json()
    assert (body["rep_min"], body["rep_max"], body["recommended_sets"]) == (6, 10, 4)
    assert body["min_experience_level"] == "advanced" and body["is_compound"] is True
    bad = alice.post("/api/exercises", json={**base, "name": "Bad range", "rep_min": 12, "rep_max": 6})
    assert bad.status_code == 422
    assert "lower than min" in str(bad.json()["error"]["details"])
    assert alice.post("/api/exercises", json={**base, "name": "Zero sets", "recommended_sets": 0}).status_code == 422


def test_available_only_filters_by_equipment_and_location(alice):
    from tests.conftest import onboard

    onboard(alice, equipment=["dumbbells", "bench"])
    names = {i["name"] for i in alice.get("/api/exercises?available_only=true&limit=100").json()}
    assert "Dumbbell bench press" in names and "Push-up" in names
    assert "Barbell bench press" not in names and "Lat pulldown" not in names
    # Bodyweight location ignores the dumbbells/bench the user ticked.
    onboard(alice, location="home_bodyweight", equipment=["dumbbells", "bench", "resistance_bands"])
    names = {i["name"] for i in alice.get("/api/exercises?available_only=true&limit=100").json()}
    assert "Resistance band row" in names and "Dumbbell bench press" not in names
