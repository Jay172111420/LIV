from fastapi import APIRouter, Query, Response, status

from app.deps import CurrentUser, DbSession
from app.models.enums import PlanKind
from app.schemas.exercise import SubstituteOut
from app.schemas.plan import (
    CustomWorkoutCreate,
    DayUpdate,
    GeneratePlanIn,
    PlanCreate,
    PlanDayOut,
    PlanDetailOut,
    PlanExerciseIn,
    PlanExerciseUpdate,
    PlanOut,
    PlanUpdate,
    ReorderIn,
    ReplaceIn,
)
from app.services import plan_service

router = APIRouter(prefix="/workouts", tags=["workouts"])


@router.get("", response_model=list[PlanOut])
def list_plans(user: CurrentUser, db: DbSession, kind: PlanKind | None = None):
    return plan_service.list_plans(db, user.id, kind)


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(data: PlanCreate, user: CurrentUser, db: DbSession):
    return plan_service.create_plan(db, user.id, data)


@router.post("/generate", response_model=PlanDetailOut, status_code=status.HTTP_201_CREATED)
def generate_plan(data: GeneratePlanIn, user: CurrentUser, db: DbSession):
    return plan_service.generate_plan(db, user, data)


@router.post("/custom", response_model=PlanDetailOut, status_code=status.HTTP_201_CREATED)
def create_custom_workout(data: CustomWorkoutCreate, user: CurrentUser, db: DbSession):
    return plan_service.create_custom_workout(db, user.id, data)


@router.get("/{plan_id}", response_model=PlanDetailOut)
def get_plan(plan_id: int, user: CurrentUser, db: DbSession):
    return plan_service.get_plan(db, user.id, plan_id)


@router.patch("/{plan_id}", response_model=PlanDetailOut)
def update_plan(plan_id: int, data: PlanUpdate, user: CurrentUser, db: DbSession):
    return plan_service.update_plan(db, user.id, plan_id, data)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, user: CurrentUser, db: DbSession):
    plan_service.delete_plan(db, user.id, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{plan_id}/days/{day_id}", response_model=PlanDayOut)
def rename_day(plan_id: int, day_id: int, data: DayUpdate, user: CurrentUser, db: DbSession):
    return plan_service.rename_day(db, user.id, plan_id, day_id, data.name)


@router.post("/{plan_id}/days/{day_id}/exercises", response_model=PlanDayOut,
             status_code=status.HTTP_201_CREATED)
def add_exercise(plan_id: int, day_id: int, data: PlanExerciseIn, user: CurrentUser, db: DbSession):
    return plan_service.add_exercise(db, user.id, plan_id, day_id, data)


@router.put("/{plan_id}/days/{day_id}/order", response_model=PlanDayOut)
def reorder(plan_id: int, day_id: int, data: ReorderIn, user: CurrentUser, db: DbSession):
    return plan_service.reorder(db, user.id, plan_id, day_id, data.plan_exercise_ids)


@router.patch("/{plan_id}/days/{day_id}/exercises/{plan_exercise_id}", response_model=PlanDayOut)
def update_exercise(plan_id: int, day_id: int, plan_exercise_id: int, data: PlanExerciseUpdate,
                    user: CurrentUser, db: DbSession):
    return plan_service.update_exercise(db, user.id, plan_id, day_id, plan_exercise_id, data)


@router.delete("/{plan_id}/days/{day_id}/exercises/{plan_exercise_id}", response_model=PlanDayOut)
def remove_exercise(plan_id: int, day_id: int, plan_exercise_id: int, user: CurrentUser, db: DbSession):
    return plan_service.remove_exercise(db, user.id, plan_id, day_id, plan_exercise_id)


@router.get("/{plan_id}/days/{day_id}/exercises/{plan_exercise_id}/substitutes",
            response_model=list[SubstituteOut])
def substitutes(plan_id: int, day_id: int, plan_exercise_id: int, user: CurrentUser, db: DbSession,
                limit: int = Query(8, ge=1, le=20)):
    return plan_service.substitutes_for(db, user, plan_id, day_id, plan_exercise_id, limit)


@router.post("/{plan_id}/days/{day_id}/exercises/{plan_exercise_id}/replace", response_model=PlanDayOut)
def replace_exercise(plan_id: int, day_id: int, plan_exercise_id: int, data: ReplaceIn,
                     user: CurrentUser, db: DbSession):
    return plan_service.replace_exercise(db, user, plan_id, day_id, plan_exercise_id, data.exercise_id)
