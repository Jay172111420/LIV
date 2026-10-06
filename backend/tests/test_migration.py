"""Existing Phase 0 databases gain the new columns without losing data."""
from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool

from app.database import make_engine
from app.migrate import upgrade_schema

PHASE0_EXERCISES = """CREATE TABLE exercises (
    id INTEGER PRIMARY KEY, owner_user_id INTEGER, name VARCHAR(120), description TEXT,
    primary_muscle_group_id INTEGER, movement_pattern VARCHAR(32), difficulty VARCHAR(32),
    exercise_type VARCHAR(32), instructions TEXT, is_active BOOLEAN, created_at DATETIME, updated_at DATETIME)"""


def test_upgrade_adds_missing_columns_and_keeps_rows():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as c:
        c.execute(text(PHASE0_EXERCISES))
        c.execute(text("CREATE TABLE workout_sets (id INTEGER PRIMARY KEY, workout_exercise_id INTEGER, set_number INTEGER)"))
        c.execute(text("INSERT INTO exercises (id, owner_user_id, name, exercise_type, is_active) "
                       "VALUES (1, 5, 'My lift', 'compound', 1), (2, 5, 'My curl', 'isolation', 1)"))
        c.execute(text("INSERT INTO workout_sets (id, workout_exercise_id, set_number) VALUES (1, 1, 1)"))

    added = upgrade_schema(engine)
    assert "exercises.rep_min" in added and "workout_sets.notes" in added
    cols = {c["name"] for c in inspect(engine).get_columns("exercises")}
    assert {"min_experience_level", "is_compound", "is_timed", "rep_min", "rep_max", "recommended_sets"} <= cols
    with engine.connect() as c:
        rows = c.execute(text("SELECT name, rep_min, rep_max, recommended_sets, min_experience_level, is_compound "
                              "FROM exercises ORDER BY id")).all()
        assert rows == [("My lift", 8, 12, 3, "beginner", 1), ("My curl", 8, 12, 3, "beginner", 0)]
        assert c.execute(text("SELECT COUNT(*) FROM workout_sets")).scalar() == 1
    assert upgrade_schema(engine) == []  # idempotent


def test_app_boots_on_a_phase0_database_and_reseeds(tmp_path):
    """create_all + upgrade + seed on an old file DB, as happens when a Phase 0 user pulls Phase 1."""
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from app.models import Base, Exercise
    from app.seed import seed_reference_data

    url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = make_engine(url)
    with engine.begin() as c:
        c.execute(text(PHASE0_EXERCISES))
    Base.metadata.create_all(engine)  # creates the missing tables, leaves `exercises` alone
    assert "rep_min" not in {c["name"] for c in inspect(engine).get_columns("exercises")}
    upgrade_schema(engine)
    with sessionmaker(bind=engine)() as db:
        seed_reference_data(db)
        bench = db.scalar(select(Exercise).where(Exercise.name == "Barbell bench press"))
        assert bench.rep_min == 5 and bench.recommended_sets == 4 and bench.is_compound
