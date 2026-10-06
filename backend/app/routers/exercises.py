from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import MuscleGroup
from app.schemas.exercise import ExerciseCreate, ExerciseOut, SubstituteOut
from app.schemas.reference import MuscleGroupOut
from app.services import exercise_service

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
