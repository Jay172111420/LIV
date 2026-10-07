"""Phase 2: personal records, volume, performance flags and progression defaults."""
from fastapi import APIRouter, Query

from app.deps import CurrentUser, DbSession
from app.schemas.progression import (
    FlagReportOut,
    IncrementPreferenceIn,
    IncrementPreferenceOut,
    RecordOut,
    TrainedExerciseOut,
    VolumeReportOut,
)
from app.services import history_service
from app.services.progression_service import ProgressionService

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/exercises", response_model=list[TrainedExerciseOut])
def trained_exercises(user: CurrentUser, db: DbSession):
    """Exercises with logged history, most recently trained first."""
    return history_service.trained_exercises(db, user.id)


@router.get("/records", response_model=list[RecordOut])
def records(user: CurrentUser, db: DbSession, exercise_id: int | None = None, limit: int = Query(30, ge=1, le=100)):
    return [RecordOut.model_validate(r) for r in
            history_service.list_records(db, user.id, exercise_id=exercise_id, limit=limit)]


@router.get("/volume", response_model=VolumeReportOut)
def volume(user: CurrentUser, db: DbSession, weeks: int = Query(8, ge=1, le=52)):
    return history_service.volume_report(db, user.id, weeks)


@router.get("/flags", response_model=FlagReportOut)
def flags(user: CurrentUser, db: DbSession):
    return history_service.flag_report(db, user.id)


@router.get("/increments", response_model=list[IncrementPreferenceOut])
def increments(user: CurrentUser, db: DbSession):
    return ProgressionService(db, user.id).list_increments()


@router.put("/increments/{category}", response_model=list[IncrementPreferenceOut])
def set_increment(category: str, data: IncrementPreferenceIn, user: CurrentUser, db: DbSession):
    return ProgressionService(db, user.id).set_increment(category, data.increment_kg)
