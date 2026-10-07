from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.errors import AppError
from app.models import MuscleGroup
from app.schemas.exercise import ExerciseCreate, ExerciseOut, SubstituteOut
from app.schemas.progression import (
    ExerciseHistoryOut,
    FlagOut,
    ProgressionSettingsIn,
    ProgressionSettingsOut,
    RecommendationOut,
)
from app.schemas.reference import MuscleGroupOut
from app.services import exercise_service, history_service
from app.services.progression_service import ProgressionService

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("/muscle-groups", response_model=list[MuscleGroupOut])
def muscle_groups(_: CurrentUser, db: DbSession):
    return db.scalars(select(MuscleGroup).order_by(MuscleGroup.id)).all()


@router.get("", response_model=list[ExerciseOut])
def list_exercises(
    user: CurrentUser, db: DbSession,
    q: str | None = Query(None, max_length=100),
    muscle_group_id: int | None = None,
    equipment_id: int | None = None,
    available_only: bool = Query(False, description="Only exercises doable with your equipment and location"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return exercise_service.list_exercises(
        db, user.id, q=q, muscle_group_id=muscle_group_id, equipment_id=equipment_id,
        limit=limit, offset=offset, available_for=user if available_only else None)


@router.post("", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
def create_exercise(data: ExerciseCreate, user: CurrentUser, db: DbSession):
    return exercise_service.create_exercise(db, user.id, data)


@router.get("/{exercise_id}/substitutes", response_model=list[SubstituteOut])
def exercise_substitutes(exercise_id: int, user: CurrentUser, db: DbSession,
                         limit: int = Query(8, ge=1, le=20)):
    return exercise_service.substitutes(db, user, exercise_id, limit=limit)


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(exercise_id: int, user: CurrentUser, db: DbSession):
    return exercise_service.get_exercise(db, user.id, exercise_id)


# ---- Phase 2: history, recommendation preview and per-exercise progression settings -------------
@router.get("/{exercise_id}/history", response_model=ExerciseHistoryOut)
def exercise_history(exercise_id: int, user: CurrentUser, db: DbSession, limit: int = Query(10, ge=1, le=50)):
    return history_service.exercise_history(db, user.id, exercise_id, limit)


@router.get("/{exercise_id}/recommendation", response_model=RecommendationOut)
def exercise_recommendation(exercise_id: int, user: CurrentUser, db: DbSession,
                            sets: int | None = Query(None, ge=1, le=20), rep_min: int | None = Query(None, ge=1, le=100),
                            rep_max: int | None = Query(None, ge=1, le=100)):
    """What Liv would suggest right now. A preview: nothing is stored.

    Without sets/rep_min/rep_max it uses the target from your last workout with this exercise.
    """
    exercise = exercise_service.get_exercise(db, user.id, exercise_id)
    if rep_min and rep_max and rep_max < rep_min:
        raise AppError("The maximum reps can't be lower than the minimum.", code="invalid_rep_range")
    service = ProgressionService(db, user.id)
    if sets is None and rep_min is None and rep_max is None:  # no target given: use how the user last trained it
        sets, rep_min, rep_max = service.last_prescription(exercise_id)
    rec, last, _ = service.recommend(exercise, sets=sets, rep_min=rep_min, rep_max=rep_max)
    return RecommendationOut(
        exercise_id=exercise.id, strategy=rec.strategy.value, action=rec.action.value, weight_kg=rec.weight_kg,
        rep_min=rec.rep_min, rep_max=rec.rep_max, reps_goal=rec.reps_goal, sets=rec.sets,
        increment_kg=rec.increment_kg, reason=rec.reason, confidence=rec.confidence, last_session=last,
        flags=[FlagOut(code=f.code, message=f.message, level=f.level, detail=f.detail) for f in rec.flags])


@router.get("/{exercise_id}/progression-settings", response_model=ProgressionSettingsOut)
def get_progression_settings(exercise_id: int, user: CurrentUser, db: DbSession):
    return ProgressionService(db, user.id).get_settings(exercise_id)


@router.put("/{exercise_id}/progression-settings", response_model=ProgressionSettingsOut)
def put_progression_settings(exercise_id: int, data: ProgressionSettingsIn, user: CurrentUser, db: DbSession):
    return ProgressionService(db, user.id).update_settings(exercise_id, data)
