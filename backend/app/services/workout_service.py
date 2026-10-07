import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError, NotFoundError
from app.models import Exercise, PersonalRecord, WorkoutExercise, WorkoutSession, WorkoutSet
from app.models.enums import WorkoutStatus
from app.schemas.workout import SessionCreate
from app.services.exercise_service import _visible_to
from app.services.plan_service import get_plan

# ---- sessions -------------------------------------------------------------

_SESSION_EAGER = (
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.sets),
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise)
    .selectinload(Exercise.primary_muscle_group),
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise)
    .selectinload(Exercise.secondary_muscle_groups),
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise)
    .selectinload(Exercise.equipment),
    selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.recommendation),
    selectinload(WorkoutSession.records).selectinload(PersonalRecord.exercise),
)


def create_session(db: Session, user_id: int, data: SessionCreate) -> WorkoutSession:
    if data.plan_id is not None:
        get_plan(db, user_id, data.plan_id)  # raises 404 for someone else's plan

    wanted = {e.exercise_id for e in data.exercises}
    usable = set(db.scalars(select(Exercise.id).where(Exercise.id.in_(wanted), *_visible_to(user_id))))
    if wanted - usable:
        raise AppError("One or more exercises don't exist.", code="invalid_exercise",
                       details=sorted(wanted - usable))

    for item in data.exercises:
        for s in item.sets:
            if s.is_completed and (s.reps is None or s.reps < 1):
                raise AppError("A completed set needs at least 1 rep.", code="set_incomplete")

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
    if session.status == WorkoutStatus.completed:  # logged after the fact: it counts towards records too
        try:
            from app.services import history_service  # local import: history_service reads this module's data
            history_service.recompute_records(db, user_id, wanted)
            db.commit()
        except Exception:  # noqa: BLE001 - the workout is saved; records can be rebuilt later
            db.rollback()
            logging.getLogger(__name__).exception("Could not update personal records")
    return get_session(db, user_id, session.id)


def get_session(db: Session, user_id: int, session_id: int) -> WorkoutSession:
    session = db.scalar(select(WorkoutSession).where(WorkoutSession.id == session_id,
                                                     WorkoutSession.user_id == user_id)
                        .options(*_SESSION_EAGER).execution_options(populate_existing=True))
    if session is None:
        raise NotFoundError("Workout session not found.")
    return session


def list_sessions(db: Session, user_id: int, limit: int, offset: int,
                  status: WorkoutStatus | None = None) -> list[WorkoutSession]:
    stmt = select(WorkoutSession).where(WorkoutSession.user_id == user_id)
    if status:
        stmt = stmt.where(WorkoutSession.status == status)
    return list(db.scalars(
        stmt.options(*_SESSION_EAGER)
        .order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc())
        .limit(limit).offset(offset)
    ))
