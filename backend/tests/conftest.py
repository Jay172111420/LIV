import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import get_db, make_engine
from app.main import create_app
from app.models import Base
from app.seed import seed_reference_data

PASSWORD = "correct-horse-battery"


@pytest.fixture()
def session_factory():
    engine = make_engine("sqlite://", poolclass=StaticPool)  # one shared in-memory DB per test
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        seed_reference_data(db)
    yield factory
    engine.dispose()


@pytest.fixture()
def app(session_factory):
    application = create_app()

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = _get_db
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def other_client(app):
    """A second, independent browser (own cookie jar)."""
    return TestClient(app)


def register(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/auth/register", json={"email": email, "password": password})


@pytest.fixture()
def alice(client):
    assert register(client, "alice@example.com").status_code == 201
    return client


@pytest.fixture()
def bob(other_client):
    assert register(other_client, "bob@example.com").status_code == 201
    return other_client


@pytest.fixture()
def settings():
    return get_settings()


# ---------------------------------------------------------------- Phase 1 helpers
@pytest.fixture(scope="session")
def pool():
    """The built-in library as engine objects, for tests that don't need a database."""
    from app.engine import ExerciseInfo
    from app.seed_data.exercise_library import EXERCISE_LIBRARY

    return [
        ExerciseInfo(
            id=i, name=e["name"], primary_muscle=e["primary"], secondary_muscles=tuple(e["secondary"]),
            movement_pattern=e["pattern"].value, equipment=frozenset(e["equipment"]),
            difficulty=e["difficulty"].value, min_experience=e["min_level"].value,
            exercise_type=e["type"].value, is_compound=e["is_compound"], is_timed=e["is_timed"],
            rep_min=e["rep_min"], rep_max=e["rep_max"], sets=e["sets"],
        )
        for i, e in enumerate(EXERCISE_LIBRARY, 1)
    ]


def lookups(client):
    gear = {e["slug"]: e["id"] for e in client.get("/api/equipment").json()}
    goals = {g["slug"]: g["id"] for g in client.get("/api/goals").json()}
    return gear, goals


def onboard(client, *, goal="muscle_gain", experience="intermediate", days=4, minutes=60,
            location="commercial_gym", equipment="all"):
    """Fills in a complete profile. `equipment` is 'all' or a list of equipment slugs."""
    gear, goals = lookups(client)
    slugs = list(gear) if equipment == "all" else equipment
    res = client.put("/api/profile", json={
        "age": 30, "height_cm": 178, "weight_kg": 80, "sex": "male", "experience_level": experience,
        "goal_id": goals[goal], "training_days_per_week": days, "preferred_workout_minutes": minutes,
        "training_location": location, "equipment_ids": [gear[s] for s in slugs]})
    assert res.status_code == 200, res.text
    return res.json()


def generate(client, **overrides):
    res = client.post("/api/workouts/generate", json=overrides)
    assert res.status_code == 201, res.text
    return res.json()


def first_training_day(plan):
    return next(d for d in plan["days"] if not d["is_rest"])


def exercise_id(client, name):
    items = client.get("/api/exercises", params={"q": name, "limit": 100}).json()
    return next(i["id"] for i in items if i["name"] == name)
