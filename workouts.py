from fastapi import APIRouter, status

from app.deps import CurrentUser, DbSession
from app.schemas.workout import PlanCreate, PlanOut
from app.services import workout_service

router = APIRouter(prefix="/workouts", tags=["workouts"])


@router.get("", response_model=list[PlanOut])
def list_plans(user: CurrentUser, db: DbSession):
    return workout_service.list_plans(db, user.id)


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(data: PlanCreate, user: CurrentUser, db: DbSession):
    return workout_service.create_plan(db, user.id, data)


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, user: CurrentUser, db: DbSession):
    return workout_service.get_plan(db, user.id, plan_id)
