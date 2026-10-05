from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError, NotFoundError
from app.models import (
    Exercise,
    FitnessGoal,
    WorkoutExercise,
    WorkoutPlan,
    WorkoutSession,
    WorkoutSet,
)
from app.schemas.workout import PlanCreate, SessionCreate
from app.services.exercise_service import _visible_to
from app.services.profile_service import load_equipment

# ---- plans ----------------------------------------------------------------


def create_plan(db: Session, user_id: int, data: PlanCreate) -> WorkoutPlan:
    if data.goal_id is not None and not db.get(FitnessGoal, data.goal_id):
        raise AppError("That fitness goal doesn't exist.", code="invalid_goal")
    plan = WorkoutPlan(
        user_id=user_id,
        name=data.name,
        goal_id=data.goal_id,
        days_per_week=data.days_per_week,
        experience_level=data.experience_level,
        duration_minutes=data.duration_minutes,
        equipment=load_equipment(db, data.equipment_ids),
    )
    db.add(plan)
    db.commit()
    return plan


def list_plans(db: Session, user_id: int) -> list[WorkoutPlan]:
    return list(db.scalars(
        select(WorkoutPlan).where(WorkoutPlan.user_id == user_id)
        .order_by(WorkoutPlan.created_at.desc())
    ))


def get_plan(db: Session, user_id: int, plan_id: int) -> WorkoutPlan:
    plan = db.scalar(select(WorkoutPlan).where(WorkoutPlan.id == plan_id,
                                               WorkoutPlan.user_id == user_id))
    if plan is None:
        raise NotFoundError("Workout plan not found.")
    return plan


# ---- sessions -------------------------------------------------------------

_SESSION_EAGER = (
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.sets),
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise)
    .selectinload(Exercise.primary_muscle_group),
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise)
    .selectinload(Exercise.secondary_muscle_groups),
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise)
    .selectinload(Exercise.equipment),
)


def create_session(db: Session, user_id: int, data: SessionCreate) -> WorkoutSession:
    if data.plan_id is not None:
        get_plan(db, user_id, data.plan_id)  # raises 404 for someone else's plan

    wanted = {e.exercise_id for e in data.exercises}
    usable = set(db.scalars(select(Exercise.id).where(Exercise.id.in_(wanted), *_visible_to(user_id))))
    if wanted - usable:
        raise AppError("One or more exercises don't exist.", code="invalid_exercise",
                       details=sorted(wanted - usable))

    session = WorkoutSession(
        user_id=user_id,
        plan_id=data.plan_id,
        performed_on=data.performed_on or date.today(),
        duration_minutes=data.duration_minutes,
        status=data.status,
        notes=data.notes,
        exercises=[
            WorkoutExercise(
                exercise_id=item.exercise_id,
                position=pos,
                notes=item.notes,
                sets=[WorkoutSet(set_number=n, **s.model_dump()) for n, s in enumerate(item.sets, 1)],
            )
            for pos, item in enumerate(data.exercises, 1)
        ],
    )
    db.add(session)
    db.commit()
    return get_session(db, user_id, session.id)


def get_session(db: Session, user_id: int, session_id: int) -> WorkoutSession:
    session = db.scalar(select(WorkoutSession).where(WorkoutSession.id == session_id,
                                                     WorkoutSession.user_id == user_id)
                        .options(*_SESSION_EAGER))
    if session is None:
        raise NotFoundError("Workout session not found.")
    return session


def list_sessions(db: Session, user_id: int, limit: int, offset: int) -> list[WorkoutSession]:
    return list(db.scalars(
        select(WorkoutSession).where(WorkoutSession.user_id == user_id)
        .options(*_SESSION_EAGER)
        .order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc())
        .limit(limit).offset(offset)
    ))
